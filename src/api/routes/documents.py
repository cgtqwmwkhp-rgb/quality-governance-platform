"""Document Management API Routes.

Enterprise document management with:
- Upload & processing
- AI-powered analysis
- Semantic search
- Version control
- Access control
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.document_campaign import SpawnReackCampaignResponse
from src.api.utils.tenant import require_tenant_id
from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.document import (
    Document,
    DocumentAnnotation,
    DocumentChunk,
    DocumentSearchLog,
    DocumentStatus,
    DocumentType,
    FileType,
    IndexJob,
    SensitivityLevel,
)
from src.domain.models.location import Location
from src.domain.models.user import User
from src.domain.services.document_ai_service import VectorSearchService
from src.domain.services.document_campaign_service import DocumentCampaignService
from src.domain.services.document_category_service import allocate_pel_doc_ref
from src.domain.services.document_extraction_service import ExtractedDocumentContent as ServiceExtractedDocumentContent
from src.domain.services.document_extraction_service import extract_document_content as shared_extract_document_content
from src.domain.services.document_version_service import (
    assert_library_metadata_editable,
    document_version_service,
    parse_filename_version_hint,
)
from src.domain.services.index_job_service import IndexJobService, dispatch_index_job, vector_index_configured
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.monitoring.azure_monitor import track_metric
from src.infrastructure.storage import StorageError, storage_service

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# SCHEMAS
# =============================================================================


class DocumentResponse(BaseModel):
    """Document response schema."""

    id: int
    reference_number: str
    title: str
    description: Optional[str]
    file_name: str
    file_type: str
    file_size: int
    document_type: str
    category: Optional[str]
    category_id: Optional[int] = None
    pel_doc_ref: Optional[str] = None
    site_location_id: Optional[int] = None
    department: Optional[str]
    sensitivity: str
    status: str
    version: str
    ai_summary: Optional[str]
    ai_tags: Optional[list]
    ai_keywords: Optional[list]
    page_count: Optional[int]
    word_count: Optional[int]
    view_count: int
    download_count: int
    is_public: bool
    created_at: datetime
    indexed_at: Optional[datetime]
    chunk_count: Optional[int] = None
    indexing_error: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Paginated document list."""

    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int
    pages: int


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    return value.value if hasattr(value, "value") else str(value)


def _coerce_json_list(value: Any) -> Optional[list]:
    """Coerce JSON metadata to a list; drop invalid shapes instead of 500ing the list."""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return None


def _document_reference_number(document: Document) -> str:
    """Return a string reference for API responses (legacy rows may have NULL)."""
    ref = getattr(document, "reference_number", None)
    if isinstance(ref, str) and ref.strip():
        return ref
    doc_id = getattr(document, "id", None)
    if doc_id is not None:
        return f"DOC-{doc_id}"
    return "DOC-UNKNOWN"


def _document_to_response(document: Document) -> DocumentResponse:
    """Serialize a document row without failing the whole list on legacy JSON shapes."""
    return DocumentResponse(
        id=document.id,
        reference_number=_document_reference_number(document),
        title=document.title,
        description=document.description,
        file_name=document.file_name,
        file_type=_enum_value(document.file_type),
        file_size=document.file_size,
        document_type=_enum_value(document.document_type),
        category=document.category,
        category_id=getattr(document, "category_id", None),
        pel_doc_ref=getattr(document, "pel_doc_ref", None),
        site_location_id=getattr(document, "site_location_id", None),
        department=document.department,
        sensitivity=_enum_value(document.sensitivity),
        status=_enum_value(document.status),
        version=document.version,
        ai_summary=document.ai_summary,
        ai_tags=_coerce_json_list(document.ai_tags),
        ai_keywords=_coerce_json_list(document.ai_keywords),
        page_count=document.page_count,
        word_count=document.word_count,
        view_count=document.view_count,
        download_count=document.download_count,
        is_public=document.is_public,
        created_at=document.created_at,
        indexed_at=document.indexed_at,
        chunk_count=getattr(document, "chunk_count", None),
        indexing_error=getattr(document, "indexing_error", None),
    )


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""

    id: int
    reference_number: str
    title: str
    status: str
    message: str
    index_job_id: Optional[int] = None
    filename_version_hint: Optional[str] = None
    pel_doc_ref: Optional[str] = None


class DocumentReprocessResponse(BaseModel):
    """Response after queueing document reprocessing."""

    document_id: int
    index_job_id: int
    status: str
    message: str


class IndexJobResponse(BaseModel):
    """Background indexing job status."""

    id: int
    job_type: str
    status: str
    document_ids: list[int]
    documents_total: int
    documents_processed: int
    documents_succeeded: int
    documents_failed: int
    chunk_count: int
    chunks_processed: int
    chunks_succeeded: int
    chunks_failed: int
    vector_index_configured: bool
    vector_index_warning: Optional[str] = None
    error_log: Optional[list[dict[str, Any]]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BulkReprocessRequest(BaseModel):
    """Admin request to bulk-reprocess library documents into Pinecone."""

    document_ids: Optional[list[int]] = None
    confirm_full_tenant: bool = False
    resume_from_job_id: Optional[int] = None
    limit: int = 500


class BulkReprocessResponse(BaseModel):
    """Response after queueing a tenant bulk reindex job."""

    index_job_id: int
    job_type: str
    documents_total: int
    vector_index_configured: bool
    vector_index_warning: Optional[str] = None
    dispatched: bool
    message: str


class SearchResult(BaseModel):
    """Semantic search result."""

    document_id: int
    reference_number: str
    title: str
    score: float
    chunk_preview: str
    page_number: Optional[int]
    heading: Optional[str]


class SearchResponse(BaseModel):
    """Search response."""

    query: str
    results: list[SearchResult]
    total: int
    latency_ms: int


class AnnotationCreate(BaseModel):
    """Create annotation request."""

    page_number: Optional[int] = None
    section_id: Optional[str] = None
    highlight_text: Optional[str] = None
    annotation_text: str
    color: str = "yellow"
    annotation_type: str = "note"
    is_shared: bool = False


class AnnotationResponse(BaseModel):
    """Annotation response."""

    id: int
    document_id: int
    page_number: Optional[int]
    section_id: Optional[str]
    highlight_text: Optional[str]
    annotation_text: str
    color: str
    annotation_type: str
    status: str
    is_shared: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentSignedUrlResponse(BaseModel):
    """Time-limited document download URL."""

    document_id: int
    signed_url: str
    expires_in_seconds: int
    filename: str
    content_type: Optional[str]


class LibraryVersionCreate(BaseModel):
    """Open a library document revision draft (JSON fallback when no file upload)."""

    change_notes: str
    change_type: str = "revision"
    is_major_version: bool = False


class LibraryDocumentPatch(BaseModel):
    """Patch library metadata on draft/working rows without a version bump."""

    title: Optional[str] = None
    description: Optional[str] = None


class LibraryVersionResponse(BaseModel):
    """Library document version row."""

    id: int
    version_number: str
    change_notes: Optional[str] = None
    change_type: str
    status: str
    is_immutable: bool
    read_only: bool
    file_name: str
    file_size: int
    filename_version_hint: Optional[str] = None
    index_job_id: Optional[int] = None
    created_by_id: Optional[int] = None
    created_at: Optional[str] = None
    published_at: Optional[str] = None
    published_by_id: Optional[int] = None


class LibraryVersionHistoryResponse(BaseModel):
    """Version history for a library document."""

    document_id: int
    current_version: str
    status: str
    published_version: Optional[str] = None
    working_version: Optional[str] = None
    versions: list[LibraryVersionResponse]


@dataclass
class ExtractedDocumentContent:
    """Structured extraction result before AI indexing."""

    text: str
    page_count: Optional[int] = None
    sheet_count: Optional[int] = None
    has_tables: bool = False
    note: Optional[str] = None
    page_texts: list[str] | None = None
    extraction_method: str = "native"


def _scope_stmt_to_current_tenant(stmt, tenant_column, current_user: CurrentUser):
    """Apply tenant scoping unless the caller is a superuser; require tenant for others."""
    if current_user.is_superuser:
        return stmt
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    return stmt.where(tenant_column == tenant_id)


async def _get_document_or_404(
    db: DbSession,
    document_id: int,
    current_user: CurrentUser,
) -> Document:
    """Load a document visible to the current user or raise 404."""
    query = select(Document).where(Document.id == document_id)
    query = _scope_stmt_to_current_tenant(query, Document.tenant_id, current_user)
    result = await db.execute(query)
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document not found")
    return document


def _safe_filename(filename: Optional[str]) -> str:
    """Prevent path traversal within storage keys."""
    return (filename or "unnamed").replace("/", "_").replace("\\", "_")


def _coerce_extraction(result: ServiceExtractedDocumentContent) -> ExtractedDocumentContent:
    return ExtractedDocumentContent(
        text=result.text,
        page_count=result.page_count,
        sheet_count=result.sheet_count,
        has_tables=result.has_tables,
        note=result.note,
        page_texts=result.page_texts,
        extraction_method=result.extraction_method,
    )


def _extract_pdf_text(content: bytes, file_name: str) -> ExtractedDocumentContent:
    """Extract searchable text from PDF evidence."""
    return _coerce_extraction(shared_extract_document_content(FileType.PDF, file_name, content))


def _extract_docx_text(content: bytes, file_name: str) -> ExtractedDocumentContent:
    """Extract text from DOCX packages without optional dependencies."""
    return _coerce_extraction(shared_extract_document_content(FileType.DOCX, file_name, content))


def _extract_xlsx_text(content: bytes, file_name: str) -> ExtractedDocumentContent:
    """Extract text rows from XLSX packages for indexing."""
    return _coerce_extraction(shared_extract_document_content(FileType.XLSX, file_name, content))


def _extract_document_content(file_type: FileType, file_name: str, content: bytes) -> ExtractedDocumentContent:
    """Return searchable text for supported document formats."""
    return _coerce_extraction(shared_extract_document_content(file_type, file_name, content))


async def _process_uploaded_document(
    db: DbSession,
    doc: Document,
    content: bytes,
    file_name: str,
    file_ext: str,
    file_type: FileType,
    current_user: Optional[User] = None,
) -> IndexJob:
    """Create an index job and run it synchronously (test/dev fallback hook)."""
    del file_name, file_ext, file_type
    index_service = IndexJobService(db)
    job = await index_service.create_job(
        document_ids=[doc.id],
        job_type="single",
        tenant_id=doc.tenant_id,
        created_by_id=current_user.id if current_user else None,
    )
    await index_service.process_job(
        job.id,
        tenant_id=doc.tenant_id,
        content_cache={doc.id: content},
        current_user=current_user,
    )
    return job


async def _enqueue_document_index_job(
    db: DbSession,
    doc: Document,
    content: bytes,
    *,
    job_type: str,
    current_user: User,
) -> tuple[IndexJob, bool]:
    """Create an index job and dispatch Celery when available."""
    index_service = IndexJobService(db)
    job = await index_service.create_job(
        document_ids=[doc.id],
        job_type=job_type,
        tenant_id=doc.tenant_id,
        created_by_id=current_user.id,
    )
    dispatched = dispatch_index_job(job.id, doc.tenant_id, current_user.id)
    if not dispatched:
        await index_service.process_job(
            job.id,
            tenant_id=doc.tenant_id,
            content_cache={doc.id: content},
            current_user=current_user,
        )
    return job, dispatched


async def _enqueue_bulk_index_job(
    db: DbSession,
    *,
    job: IndexJob,
    tenant_id: int,
    current_user: User,
) -> tuple[IndexJob, bool]:
    """Dispatch a multi-document index job via Celery or synchronous fallback."""
    index_service = IndexJobService(db)
    dispatched = dispatch_index_job(job.id, tenant_id, current_user.id)
    if not dispatched:
        await index_service.process_job(
            job.id,
            tenant_id=tenant_id,
            current_user=current_user,
        )
    return job, dispatched


def _index_job_response(job: IndexJob) -> IndexJobResponse:
    configured, warning = vector_index_configured()
    document_ids = list(job.document_ids or [])
    return IndexJobResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        document_ids=document_ids,
        documents_total=len(document_ids),
        documents_processed=int(getattr(job, "documents_processed", 0) or 0),
        documents_succeeded=int(getattr(job, "documents_succeeded", 0) or 0),
        documents_failed=int(getattr(job, "documents_failed", 0) or 0),
        chunk_count=job.chunk_count,
        chunks_processed=job.chunks_processed,
        chunks_succeeded=job.chunks_succeeded,
        chunks_failed=job.chunks_failed,
        vector_index_configured=configured,
        vector_index_warning=warning,
        error_log=list(job.error_log or []) or None,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


# =============================================================================
# UPLOAD & CREATE
# =============================================================================


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:create"))],
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(None),
    document_type: str = Form("other"),
    category: str = Form(None),
    department: str = Form(None),
    sensitivity: str = Form("internal"),
    category_id: Optional[int] = Form(None),
    site_location_id: Optional[int] = Form(None),
):
    """Upload and process a new document.

    `category_id` (Governance Library taxonomy, Wave W0) is optional and
    separate from the legacy free-text `category` string: when provided, a
    `pel_doc_ref` (PEL-<SECTION>-<SUB>-<SEQ>) is atomically allocated
    alongside the existing `reference_number` (DOC-YYYY-####).
    `site_location_id` binds the document to an existing `Location`
    (site/workshop) — no separate Site table.
    """

    if current_user.tenant_id is None:
        raise BadRequestError("Tenant context required to upload documents")

    # `category_id`/`site_location_id` default to `Form(None)` sentinel objects
    # (not literal `None`) when this coroutine is invoked directly rather than
    # via FastAPI's request pipeline (e.g. in unit tests) — normalize with an
    # `isinstance` check rather than `is not None` so both call styles behave.
    category_id = category_id if isinstance(category_id, int) else None
    site_location_id = site_location_id if isinstance(site_location_id, int) else None

    if site_location_id is not None and await db.get(Location, site_location_id) is None:
        raise BadRequestError(f"Location {site_location_id} not found")

    # Validate file type
    file_ext = file.filename.split(".")[-1].lower() if file.filename else ""
    try:
        file_type = FileType(file_ext)
    except ValueError:
        raise BadRequestError(f"Unsupported file type: {file_ext}. Supported: {[f.value for f in FileType]}")

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

    # Read file content
    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise BadRequestError("Uploaded file is empty")

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({file_size // (1024*1024)}MB) exceeds maximum allowed size (50MB).",
        )

    safe_filename = _safe_filename(file.filename)
    file_name = file.filename or safe_filename
    file_path = f"documents/{datetime.now(timezone.utc).strftime('%Y/%m')}/{uuid.uuid4()}/{safe_filename}"

    try:
        reference_number = await ReferenceNumberService.generate(db, "document", Document)

        # Governance Library taxonomy (Wave W0): allocated only once file
        # validation above has passed, so a rejected upload never burns a
        # PEL sequence number. Gaps are acceptable (see reference_scheme in
        # specs/governance-library/taxonomy.json); duplicates are not.
        pel_doc_ref: Optional[str] = None
        if category_id is not None:
            pel_doc_ref = await allocate_pel_doc_ref(db, category_id)

        # Create document record
        doc = Document(
            title=title,
            description=description,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
            file_path=file_path,
            mime_type=file.content_type,
            document_type=(
                DocumentType(document_type) if document_type in [d.value for d in DocumentType] else DocumentType.OTHER
            ),
            category=category,
            department=department,
            sensitivity=(
                SensitivityLevel(sensitivity)
                if sensitivity in [s.value for s in SensitivityLevel]
                else SensitivityLevel.INTERNAL
            ),
            status=DocumentStatus.PROCESSING,
            version="1.0",
            reference_number=reference_number,
            category_id=category_id,
            pel_doc_ref=pel_doc_ref,
            site_location_id=site_location_id,
            created_by_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )

        db.add(doc)
        await db.flush()

        # Honest create: initial draft version row matches document.version tip
        db.add(
            document_version_service.build_initial_library_version(
                doc,
                created_by_id=current_user.id,
                change_notes="Initial upload",
            )
        )

        try:
            await storage_service().upload(
                storage_key=file_path,
                content=content,
                content_type=file.content_type or "application/octet-stream",
                metadata={
                    "document_id": str(doc.id),
                    "tenant_id": str(current_user.tenant_id or ""),
                    "uploaded_by": str(current_user.id),
                    "file_name": file_name,
                },
            )
        except StorageError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store document content: {exc}",
            ) from exc

        try:
            index_job, dispatched = await _enqueue_document_index_job(
                db,
                doc,
                content,
                job_type="single",
                current_user=current_user,
            )
            await db.commit()
        except Exception as e:
            doc.status = DocumentStatus.FAILED
            doc.indexing_error = str(e)
            await db.commit()
            index_job = None
            dispatched = False

        await db.refresh(doc)

        track_metric("documents.uploaded")

        hint = parse_filename_version_hint(file_name)

        return DocumentUploadResponse(
            id=doc.id,
            reference_number=_document_reference_number(doc),
            title=doc.title,
            status=doc.status.value,
            index_job_id=index_job.id if index_job else None,
            filename_version_hint=hint.label if hint else None,
            pel_doc_ref=getattr(doc, "pel_doc_ref", None),
            message=(
                "Document uploaded; indexing job queued" if dispatched else "Document uploaded and processing completed"
            ),
        )
    except HTTPException:
        raise
    except BadRequestError:
        raise
    except Exception as exc:
        logger.exception("Document upload failed unexpectedly")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document upload failed: {exc}",
        ) from exc


@router.post(
    "/{document_id}/reprocess",
    response_model=DocumentReprocessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reprocess_document(
    document_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
) -> DocumentReprocessResponse:
    """Re-run document intelligence and indexing for an existing library document."""
    doc = await _get_document_or_404(db, document_id, current_user)
    doc.status = DocumentStatus.PROCESSING
    doc.indexing_error = None

    content = await storage_service().download(doc.file_path)
    index_job, dispatched = await _enqueue_document_index_job(
        db,
        doc,
        content,
        job_type="reindex",
        current_user=current_user,
    )
    await db.commit()
    await db.refresh(doc)

    return DocumentReprocessResponse(
        document_id=doc.id,
        index_job_id=index_job.id,
        status=doc.status.value,
        message="Document reprocessing queued" if dispatched else "Document reprocessing completed",
    )


@router.get("/index-jobs/{job_id}", response_model=IndexJobResponse)
async def get_index_job(
    job_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> IndexJobResponse:
    """Return background indexing job status."""
    index_service = IndexJobService(db)
    job = await index_service.get_job(job_id, tenant_id=getattr(current_user, "tenant_id", None))
    if job is None:
        raise NotFoundError("Index job not found")
    return _index_job_response(job)


@router.post(
    "/admin/bulk-reprocess",
    response_model=BulkReprocessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def bulk_reprocess_documents(
    payload: BulkReprocessRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
) -> BulkReprocessResponse:
    """Admin-only bulk reindex of tenant library documents into Pinecone."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    index_service = IndexJobService(db)

    try:
        job = await index_service.create_bulk_reprocess_job(
            tenant_id=tenant_id,
            created_by_id=current_user.id,
            document_ids=payload.document_ids,
            confirm_full_tenant=payload.confirm_full_tenant,
            resume_from_job_id=payload.resume_from_job_id,
            limit=payload.limit,
        )
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc

    job, dispatched = await _enqueue_bulk_index_job(
        db,
        job=job,
        tenant_id=tenant_id,
        current_user=current_user,
    )
    await db.commit()
    await db.refresh(job)

    configured, warning = vector_index_configured()
    documents_total = len(job.document_ids or [])
    if not configured:
        message = (
            "Bulk reprocess queued; chunks and AI metadata will be rebuilt but semantic "
            "Pinecone upsert requires VOYAGE_API_KEY and PINECONE_API_KEY"
        )
    elif dispatched:
        message = f"Bulk reprocess queued for {documents_total} document(s)"
    else:
        message = f"Bulk reprocess completed synchronously for {documents_total} document(s)"

    return BulkReprocessResponse(
        index_job_id=job.id,
        job_type=job.job_type,
        documents_total=documents_total,
        vector_index_configured=configured,
        vector_index_warning=warning,
        dispatched=dispatched,
        message=message,
    )


# =============================================================================
# LIST & GET
# =============================================================================


@router.get("", response_model=DocumentListResponse, include_in_schema=False)
@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    document_type: Optional[str] = None,
    category: Optional[str] = None,
    category_id: Optional[int] = None,
    site_location_id: Optional[int] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    is_indexed: Optional[bool] = None,
):
    """List documents with filtering and pagination."""

    query = select(Document).where(Document.is_active == True)
    query = _scope_stmt_to_current_tenant(query, Document.tenant_id, current_user)

    # Apply filters
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                Document.title.ilike(search_filter),
                Document.description.ilike(search_filter),
                Document.reference_number.ilike(search_filter),
                Document.file_name.ilike(search_filter),
            )
        )

    if document_type:
        query = query.where(Document.document_type == document_type)
    if category:
        query = query.where(Document.category == category)
    if category_id is not None:
        query = query.where(Document.category_id == category_id)
    if site_location_id is not None:
        query = query.where(Document.site_location_id == site_location_id)
    if department:
        query = query.where(Document.department == department)
    if status:
        query = query.where(Document.status == status)
    if is_indexed is not None:
        if is_indexed:
            query = query.where(Document.indexed_at.isnot(None))
        else:
            query = query.where(Document.indexed_at.is_(None))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    query = query.order_by(Document.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    documents = result.scalars().all()

    return DocumentListResponse(
        items=[_document_to_response(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total else 0,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get document details."""

    document = await _get_document_or_404(db, document_id, current_user)

    # Increment view count
    document.view_count += 1
    document.last_accessed_at = datetime.now(timezone.utc)
    await db.commit()

    return _document_to_response(document)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def patch_document_metadata(
    document_id: int,
    payload: LibraryDocumentPatch,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Update title/description on draft/working rows without opening a new version."""
    document = await _get_document_or_404(db, document_id, current_user)
    assert_library_metadata_editable(document.status)

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise BadRequestError("Title cannot be empty")
        document.title = title
    if payload.description is not None:
        document.description = payload.description

    await db.commit()
    await db.refresh(document)
    return _document_to_response(document)


async def _read_and_validate_revision_file(
    file: UploadFile,
) -> tuple[bytes, str, FileType, str]:
    """Validate an uploaded revision file and return content + metadata."""
    file_ext = file.filename.split(".")[-1].lower() if file.filename else ""
    try:
        file_type = FileType(file_ext)
    except ValueError:
        raise BadRequestError(f"Unsupported file type: {file_ext}. Supported: {[f.value for f in FileType]}")

    content = await file.read()
    file_size = len(content)
    if file_size == 0:
        raise BadRequestError("Uploaded file is empty")

    max_file_size = 50 * 1024 * 1024
    if file_size > max_file_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({file_size // (1024 * 1024)}MB) exceeds maximum allowed size (50MB).",
        )

    safe_filename = _safe_filename(file.filename)
    file_name = file.filename or safe_filename
    return content, file_name, file_type, safe_filename


@router.get("/{document_id}/signed-url", response_model=DocumentSignedUrlResponse)
async def get_document_signed_url(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
    expires_in: int = Query(3600, ge=60, le=86400),
    download: bool = Query(True, description="Set attachment disposition when true."),
):
    """Get a signed document URL for inline viewing or download."""
    document = await _get_document_or_404(db, document_id, current_user)
    document.download_count += 1
    document.last_accessed_at = datetime.now(timezone.utc)
    await db.commit()

    filename = document.file_name or "download"
    content_disposition = f'attachment; filename="{filename}"' if download else None
    signed_url = storage_service().get_signed_url(
        storage_key=document.file_path,
        expires_in_seconds=expires_in,
        content_disposition=content_disposition,
    )
    return DocumentSignedUrlResponse(
        document_id=document.id,
        signed_url=signed_url,
        expires_in_seconds=expires_in,
        filename=filename,
        content_type=document.mime_type,
    )


# =============================================================================
# VERSION CONTROL
# =============================================================================


@router.get("/{document_id}/versions", response_model=LibraryVersionHistoryResponse)
async def list_document_versions(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List version history for a library document (immutable prior publishes)."""
    document = await _get_document_or_404(db, document_id, current_user)
    versions = await document_version_service.list_library_versions(
        db,
        document_id,
        tenant_id=getattr(current_user, "tenant_id", None),
        is_superuser=bool(getattr(current_user, "is_superuser", False)),
    )
    serialized = [document_version_service.serialize_library_version(v) for v in versions]
    return LibraryVersionHistoryResponse(
        document_id=document.id,
        current_version=document.version,
        status=document.status.value if hasattr(document.status, "value") else str(document.status),
        published_version=next((v["version_number"] for v in serialized if v["status"] == "published"), None),
        working_version=next((v["version_number"] for v in serialized if v["status"] == "draft"), None),
        versions=[LibraryVersionResponse(**v) for v in serialized],
    )


@router.post(
    "/{document_id}/versions",
    response_model=LibraryVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document_version(
    document_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    change_notes: str = Form(...),
    change_type: str = Form("revision"),
    is_major_version: bool = Form(False),
    file: UploadFile | None = File(None),
):
    """Open a revision draft with optional new file upload + re-index."""
    document = await _get_document_or_404(db, document_id, current_user)

    file_name: str | None = None
    file_path: str | None = None
    file_size: int | None = None
    index_job_id: int | None = None
    content: bytes | None = None

    if file is not None and file.filename:
        content, file_name, file_type, safe_filename = await _read_and_validate_revision_file(file)
        file_path = f"documents/{datetime.now(timezone.utc).strftime('%Y/%m')}/{uuid.uuid4()}/{safe_filename}"
        file_size = len(content)
        try:
            await storage_service().upload(
                storage_key=file_path,
                content=content,
                content_type=file.content_type or "application/octet-stream",
                metadata={
                    "document_id": str(document.id),
                    "tenant_id": str(document.tenant_id),
                    "uploaded_by": str(current_user.id),
                    "file_name": file_name,
                    "revision": "true",
                },
            )
        except StorageError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store revision file: {exc}",
            ) from exc
        document.file_type = file_type
        document.mime_type = file.content_type

    version = await document_version_service.revise_library(
        db,
        document,
        change_notes=change_notes,
        change_type=change_type,
        is_major_version=is_major_version,
        file_name=file_name,
        file_path=file_path,
        file_size=file_size,
        created_by_id=current_user.id,
    )

    if content is not None:
        document.status = DocumentStatus.PROCESSING
        document.indexing_error = None
        index_job, _dispatched = await _enqueue_document_index_job(
            db,
            document,
            content,
            job_type="reindex",
            current_user=current_user,
        )
        index_job_id = index_job.id

    await db.commit()
    await db.refresh(version)
    payload = document_version_service.serialize_library_version(version)
    payload["index_job_id"] = index_job_id
    return LibraryVersionResponse(**payload)


@router.post("/{document_id}/publish", response_model=LibraryVersionHistoryResponse)
async def publish_document_version(
    document_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    version_id: Optional[int] = Query(None),
):
    """Publish working draft; supersede prior published tip (immutable)."""
    document = await _get_document_or_404(db, document_id, current_user)
    await document_version_service.publish_library(
        db,
        document,
        published_by_id=current_user.id,
        version_id=version_id,
    )
    try:
        campaign_service = DocumentCampaignService(db)
        await campaign_service.spawn_reack_campaign(
            document_id=document_id,
            tenant_id=require_tenant_id(current_user.tenant_id),
            actor_id=current_user.id,
        )
    except Exception:  # noqa: BLE001 — publish must not fail on re-ack hook
        logger.warning(
            "spawn_reack_campaign failed after library publish for document %s",
            document_id,
            exc_info=True,
        )
    await db.commit()
    versions = await document_version_service.list_library_versions(
        db,
        document_id,
        tenant_id=getattr(current_user, "tenant_id", None),
        is_superuser=bool(getattr(current_user, "is_superuser", False)),
    )
    serialized = [document_version_service.serialize_library_version(v) for v in versions]
    return LibraryVersionHistoryResponse(
        document_id=document.id,
        current_version=document.version,
        status=document.status.value if hasattr(document.status, "value") else str(document.status),
        published_version=next((v["version_number"] for v in serialized if v["status"] == "published"), None),
        working_version=next((v["version_number"] for v in serialized if v["status"] == "draft"), None),
        versions=[LibraryVersionResponse(**v) for v in serialized],
    )


@router.post("/{document_id}/spawn-reack-campaign", response_model=SpawnReackCampaignResponse)
async def spawn_reack_campaign(
    document_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    auto_launch: bool = Query(False, description="Launch the spawned re-ack campaign immediately"),
):
    """Manually spawn a draft re-acknowledgment campaign after a document version change."""
    await _get_document_or_404(db, document_id, current_user)
    service = DocumentCampaignService(db)
    result = await service.spawn_reack_campaign(
        document_id=document_id,
        tenant_id=require_tenant_id(current_user.tenant_id),
        actor_id=current_user.id,
        auto_launch=auto_launch,
    )
    return SpawnReackCampaignResponse(**result)


# =============================================================================
# SEARCH
# =============================================================================


@router.get("/search/semantic", response_model=SearchResponse)
async def semantic_search(
    db: DbSession,
    current_user: CurrentUser,
    q: str = Query(..., min_length=3),
    top_k: int = Query(10, ge=1, le=50),
    document_type: Optional[str] = None,
):
    """Semantic search across documents using AI embeddings."""

    import time

    start_time = time.time()

    vector_service = VectorSearchService()

    # Build filter
    filter_dict: Optional[dict[str, Any]] = None
    if document_type:
        filter_dict = {"document_type": document_type}
    if not current_user.is_superuser:
        filter_dict = {**(filter_dict or {}), "tenant_id": current_user.tenant_id}

    # Search vectors
    matches = await vector_service.search(q, top_k=top_k, filter_dict=filter_dict)

    results = []
    doc_ids = set()

    for match in matches:
        doc_id = match.get("metadata", {}).get("document_id")
        if doc_id and doc_id not in doc_ids:
            doc_ids.add(doc_id)

            # Get document info
            try:
                doc = await _get_document_or_404(db, doc_id, current_user)
            except HTTPException:
                doc = None

            if doc:
                results.append(
                    SearchResult(
                        document_id=doc.id,
                        reference_number=_document_reference_number(doc),
                        title=doc.title,
                        score=match.get("score", 0.0),
                        chunk_preview=match.get("metadata", {}).get("content_preview", ""),
                        page_number=match.get("metadata", {}).get("page_number"),
                        heading=match.get("metadata", {}).get("heading"),
                    )
                )

    latency_ms = int((time.time() - start_time) * 1000)

    # Log search
    log = DocumentSearchLog(
        query=q,
        query_type="semantic",
        result_count=len(results),
        result_document_ids=[r.document_id for r in results],
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        latency_ms=latency_ms,
    )
    db.add(log)
    await db.commit()

    return SearchResponse(
        query=q,
        results=results,
        total=len(results),
        latency_ms=latency_ms,
    )


# =============================================================================
# ANNOTATIONS
# =============================================================================


@router.get("/{document_id}/annotations", response_model=list[AnnotationResponse])
async def list_annotations(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List annotations for a document."""
    document = await _get_document_or_404(db, document_id, current_user)

    query = select(DocumentAnnotation).where(DocumentAnnotation.document_id == document_id)
    query = query.where(DocumentAnnotation.tenant_id == document.tenant_id)

    # Show user's own annotations + shared annotations
    query = query.where(
        or_(
            DocumentAnnotation.user_id == current_user.id,
            DocumentAnnotation.is_shared == True,
        )
    )

    result = await db.execute(query.order_by(DocumentAnnotation.created_at.desc()))
    annotations = result.scalars().all()

    return [AnnotationResponse.model_validate(a) for a in annotations]


@router.post(
    "/{document_id}/annotations",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    document_id: int,
    annotation_data: AnnotationCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Create an annotation on a document."""

    # Verify document exists
    document = await _get_document_or_404(db, document_id, current_user)

    annotation = DocumentAnnotation(
        document_id=document_id,
        tenant_id=document.tenant_id,
        user_id=current_user.id,
        page_number=annotation_data.page_number,
        section_id=annotation_data.section_id,
        highlight_text=annotation_data.highlight_text,
        annotation_text=annotation_data.annotation_text,
        color=annotation_data.color,
        annotation_type=annotation_data.annotation_type,
        is_shared=annotation_data.is_shared,
    )

    db.add(annotation)
    await db.commit()
    await db.refresh(annotation)

    return AnnotationResponse.model_validate(annotation)


# =============================================================================
# STATS
# =============================================================================


@router.get("/stats/overview")
async def get_document_stats(
    db: DbSession,
    current_user: CurrentUser,
):
    """Get document library statistics."""

    # Total documents
    total_query = _scope_stmt_to_current_tenant(select(func.count(Document.id)), Document.tenant_id, current_user)
    total_result = await db.execute(total_query)
    total = total_result.scalar() or 0

    # By status
    status_query = _scope_stmt_to_current_tenant(
        select(Document.status, func.count(Document.id)).group_by(Document.status),
        Document.tenant_id,
        current_user,
    )
    status_result = await db.execute(status_query)
    by_status = {row[0].value if hasattr(row[0], "value") else row[0]: row[1] for row in status_result.all()}

    # By type
    type_query = _scope_stmt_to_current_tenant(
        select(Document.document_type, func.count(Document.id)).group_by(Document.document_type),
        Document.tenant_id,
        current_user,
    )
    type_result = await db.execute(type_query)
    by_type = {row[0].value if hasattr(row[0], "value") else row[0]: row[1] for row in type_result.all()}

    # Indexed count
    indexed_query = select(func.count(Document.id)).where(Document.indexed_at.isnot(None))
    indexed_query = _scope_stmt_to_current_tenant(indexed_query, Document.tenant_id, current_user)
    indexed_result = await db.execute(indexed_query)
    indexed = indexed_result.scalar() or 0

    # Total chunks
    chunk_query = _scope_stmt_to_current_tenant(
        select(func.count(DocumentChunk.id)), DocumentChunk.tenant_id, current_user
    )
    chunk_result = await db.execute(chunk_query)
    total_chunks = chunk_result.scalar() or 0

    return {
        "total_documents": total,
        "indexed_documents": indexed,
        "total_chunks": total_chunks,
        "by_status": by_status,
        "by_type": by_type,
    }
