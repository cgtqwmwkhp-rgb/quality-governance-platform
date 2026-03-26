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
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from src.api.dependencies import CurrentUser, DbSession
from src.domain.models.document import (
    Document,
    DocumentAnnotation,
    DocumentChunk,
    DocumentSearchLog,
    DocumentStatus,
    DocumentType,
    FileType,
    SensitivityLevel,
)
from src.domain.services.document_extraction_service import (
    ExtractedDocumentContent as ServiceExtractedDocumentContent,
    extract_document_content as shared_extract_document_content,
)
from src.domain.services.document_ai_service import DocumentAIService, EmbeddingService, VectorSearchService
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

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Paginated document list."""

    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int
    pages: int


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""

    id: int
    reference_number: str
    title: str
    status: str
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
    """Apply tenant scoping unless the caller is a superuser."""
    if current_user.is_superuser:
        return stmt
    return stmt.where(tenant_column == current_user.tenant_id)


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
        raise HTTPException(status_code=404, detail="Document not found")
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
) -> None:
    """Isolate upload processing behind a single async boundary."""
    ai_service = DocumentAIService()
    extraction = _extract_document_content(file_type, file_name, content)

    doc.page_count = extraction.page_count
    doc.sheet_count = extraction.sheet_count
    doc.has_tables = extraction.has_tables
    doc.indexing_error = extraction.note

    text_content = extraction.text.strip()
    if not text_content:
        doc.status = DocumentStatus.APPROVED
        return

    analysis = await ai_service.analyze_document(text_content, file_name, file_ext)
    doc.ai_summary = analysis.summary
    doc.ai_tags = analysis.tags
    doc.ai_keywords = analysis.keywords
    doc.ai_topics = analysis.topics
    doc.ai_entities = analysis.entities
    doc.ai_confidence = analysis.confidence
    doc.ai_processed_at = datetime.now(timezone.utc)
    doc.has_tables = doc.has_tables or analysis.has_tables
    doc.has_images = analysis.has_images
    doc.word_count = len(text_content.split())

    chunks = await ai_service.generate_chunks(text_content)
    doc.chunk_count = len(chunks)

    for chunk in chunks:
        db.add(
            DocumentChunk(
                document_id=doc.id,
                tenant_id=doc.tenant_id,
                content=chunk.content,
                chunk_index=chunk.index,
                token_count=chunk.token_count,
                heading=chunk.heading,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
            )
        )

    embedding_service = EmbeddingService()
    vector_service = VectorSearchService()
    embeddings = await embedding_service.generate_embeddings([chunk.content for chunk in chunks])

    if embeddings and await vector_service.upsert_chunks(
        doc.id,
        chunks,
        embeddings,
        extra_metadata={
            "tenant_id": doc.tenant_id or 0,
            "document_type": doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type),
        },
    ):
        doc.indexed_at = datetime.now(timezone.utc)
        doc.status = DocumentStatus.INDEXED
        doc.indexing_error = None
    else:
        doc.status = DocumentStatus.APPROVED


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
    current_user: CurrentUser,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(None),
    document_type: str = Form("other"),
    category: str = Form(None),
    department: str = Form(None),
    sensitivity: str = Form("internal"),
):
    """Upload and process a new document."""

    # Validate file type
    file_ext = file.filename.split(".")[-1].lower() if file.filename else ""
    try:
        file_type = FileType(file_ext)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}. Supported: {[f.value for f in FileType]}",
        )

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

    # Read file content
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({file_size // (1024*1024)}MB) exceeds maximum allowed size (50MB).",
        )

    safe_filename = _safe_filename(file.filename)
    file_name = file.filename or safe_filename
    file_path = f"documents/{datetime.now(timezone.utc).strftime('%Y/%m')}/{uuid.uuid4()}/{safe_filename}"

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
        created_by_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )

    db.add(doc)
    await db.flush()

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
        await _process_uploaded_document(db, doc, content, file_name, file_ext, file_type)
        await db.commit()
    except Exception as e:
        doc.status = DocumentStatus.FAILED
        doc.indexing_error = str(e)
        await db.commit()

    await db.refresh(doc)

    return DocumentUploadResponse(
        id=doc.id,
        reference_number=doc.reference_number,
        title=doc.title,
        status=doc.status.value,
        message="Document uploaded and processing started",
    )


# =============================================================================
# LIST & GET
# =============================================================================


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    document_type: Optional[str] = None,
    category: Optional[str] = None,
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

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Document.created_at.desc())

    result = await db.execute(query)
    documents = result.scalars().all()

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
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

    return DocumentResponse.model_validate(document)


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
                        reference_number=doc.reference_number,
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
    current_user: CurrentUser,
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
