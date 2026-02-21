"""Document Management API Routes.

Enterprise document management with:
- Upload & processing
- AI-powered analysis
- Semantic search
- Version control
- Access control
"""

import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.pagination import DataListResponse
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
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
from src.domain.models.user import User
from src.domain.services.document_ai_service import DocumentAIService, EmbeddingService, VectorSearchService
from src.infrastructure.storage import StorageError, storage_service

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter()


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


class DocumentStatsResponse(BaseModel):
    total_documents: int
    indexed_documents: int
    total_chunks: int
    by_status: dict
    by_type: dict


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


# =============================================================================
# UPLOAD & CREATE
# =============================================================================


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
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
):
    """Upload and process a new document."""
    _span = tracer.start_span("upload_document") if tracer else None
    if _span:
        _span.set_attribute("tenant_id", str(getattr(current_user, "tenant_id", 0) or 0))

    file_ext = file.filename.split(".")[-1].lower() if file.filename else ""
    try:
        file_type = FileType(file_ext)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.VALIDATION_ERROR,
        )

    content = await file.read()
    file_size = len(content)

    file_path = f"documents/{datetime.utcnow().strftime('%Y/%m')}/{uuid.uuid4()}/{file.filename}"

    doc = Document(
        title=title,
        description=description,
        file_name=file.filename,
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
        created_by_id=current_user.id if current_user else None,
    )

    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    try:
        store = storage_service()
        await store.upload(
            storage_key=file_path,
            content=content,
            content_type=file.content_type or "application/octet-stream",
            metadata={"document_id": str(doc.id), "title": title},
        )
    except StorageError as e:
        doc.status = DocumentStatus.FAILED
        doc.indexing_error = f"Storage upload failed: {e}"
        await db.commit()
        return DocumentUploadResponse(
            id=doc.id,
            reference_number=doc.reference_number,
            title=doc.title,
            status=doc.status.value,
            message=f"Document record created but file upload failed: {e}",
        )

    try:
        ai_service = DocumentAIService()

        text_content = ""
        if file_type in [FileType.TXT, FileType.MD]:
            text_content = content.decode("utf-8", errors="ignore")
        elif file_type == FileType.CSV:
            text_content = content.decode("utf-8", errors="ignore")
        elif file_type == FileType.PDF:
            text_content = ""
        elif file_type in [FileType.DOCX, FileType.DOC]:
            text_content = ""
        elif file_type in [FileType.XLSX, FileType.XLS]:
            text_content = ""

        if text_content and not text_content.startswith("["):
            filename = file.filename or "document"
            analysis = await ai_service.analyze_document(text_content, filename, file_ext)

            doc.ai_summary = analysis.summary
            doc.ai_tags = analysis.tags
            doc.ai_keywords = analysis.keywords
            doc.ai_topics = analysis.topics
            doc.ai_entities = analysis.entities
            doc.ai_confidence = analysis.confidence
            doc.ai_processed_at = datetime.utcnow()
            doc.has_tables = analysis.has_tables
            doc.has_images = analysis.has_images
            doc.word_count = len(text_content.split())

            chunks = await ai_service.generate_chunks(text_content)
            doc.chunk_count = len(chunks)

            for chunk in chunks:
                db_chunk = DocumentChunk(
                    document_id=doc.id,
                    content=chunk.content,
                    chunk_index=chunk.index,
                    token_count=chunk.token_count,
                    heading=chunk.heading,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                )
                db.add(db_chunk)

            embedding_service = EmbeddingService()
            vector_service = VectorSearchService()

            chunk_texts = [c.content for c in chunks]
            embeddings = await embedding_service.generate_embeddings(chunk_texts)

            if embeddings:
                await vector_service.upsert_chunks(doc.id, chunks, embeddings)
                doc.indexed_at = datetime.utcnow()
                doc.status = DocumentStatus.INDEXED
            else:
                doc.status = DocumentStatus.APPROVED
        else:
            doc.status = DocumentStatus.APPROVED

        await db.commit()

    except (SQLAlchemyError, ValueError) as e:
        doc.status = DocumentStatus.FAILED
        doc.indexing_error = str(e)
        await db.commit()

    if _span:
        _span.end()
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
    params: PaginationParams = Depends(),
    search: Optional[str] = None,
    document_type: Optional[str] = None,
    category: Optional[str] = None,
    department: Optional[str] = None,
    doc_status: Optional[str] = Query(None, alias="status"),
    is_indexed: Optional[bool] = None,
):
    """List documents with filtering and pagination."""

    query = (
        select(Document)
        .options(
            selectinload(Document.annotations),
            selectinload(Document.versions),
        )
        .where(
            Document.is_active == True,
            Document.tenant_id == current_user.tenant_id,
        )
    )

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
    if doc_status:
        query = query.where(Document.status == doc_status)
    if is_indexed is not None:
        if is_indexed:
            query = query.where(Document.indexed_at.isnot(None))
        else:
            query = query.where(Document.indexed_at.is_(None))

    query = query.order_by(Document.created_at.desc())
    paginated = await paginate(db, query, params)

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in paginated.items],
        total=paginated.total,
        page=paginated.page,
        page_size=paginated.page_size,
        pages=paginated.pages,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get document details."""
    document = await get_or_404(db, Document, document_id, tenant_id=current_user.tenant_id)

    document.view_count += 1
    document.last_accessed_at = datetime.utcnow()
    await db.commit()

    return DocumentResponse.model_validate(document)


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

    filter_dict = None
    if document_type:
        filter_dict = {"document_type": document_type}

    matches = await vector_service.search(q, top_k=top_k, filter_dict=filter_dict)

    results = []
    doc_ids = set()

    for match in matches:
        doc_id = match.get("metadata", {}).get("document_id")
        if doc_id and doc_id not in doc_ids:
            doc_ids.add(doc_id)

            doc_result = await db.execute(
                select(Document).where(
                    Document.id == doc_id,
                    Document.tenant_id == current_user.tenant_id,
                )
            )
            doc = doc_result.scalar_one_or_none()

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

    log = DocumentSearchLog(
        query=q,
        query_type="semantic",
        result_count=len(results),
        result_document_ids=[r.document_id for r in results],
        user_id=current_user.id if current_user else None,
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


@router.get("/{document_id}/annotations", response_model=DataListResponse)
async def list_annotations(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List annotations for a document."""

    query = select(DocumentAnnotation).where(DocumentAnnotation.document_id == document_id)

    query = query.where(
        or_(
            DocumentAnnotation.user_id == current_user.id,
            DocumentAnnotation.is_shared == True,
        )
    )

    result = await db.execute(query.order_by(DocumentAnnotation.created_at.desc()))
    annotations = result.scalars().all()

    return {"data": [AnnotationResponse.model_validate(a) for a in annotations]}


@router.post(
    "/{document_id}/annotations",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    document_id: int,
    annotation_data: AnnotationCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:create"))],
):
    """Create an annotation on a document."""
    await get_or_404(db, Document, document_id, tenant_id=current_user.tenant_id)

    annotation = DocumentAnnotation(
        document_id=document_id,
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


@router.get("/stats/overview", response_model=DocumentStatsResponse)
async def get_document_stats(
    db: DbSession,
    current_user: CurrentUser,
):
    """Get document library statistics."""

    tenant_filter = Document.tenant_id == current_user.tenant_id

    total_result = await db.execute(select(func.count(Document.id)).where(tenant_filter))
    total = total_result.scalar() or 0

    status_result = await db.execute(
        select(Document.status, func.count(Document.id)).where(tenant_filter).group_by(Document.status)
    )
    by_status = {row[0].value if hasattr(row[0], "value") else row[0]: row[1] for row in status_result.all()}

    type_result = await db.execute(
        select(Document.document_type, func.count(Document.id)).where(tenant_filter).group_by(Document.document_type)
    )
    by_type = {row[0].value if hasattr(row[0], "value") else row[0]: row[1] for row in type_result.all()}

    indexed_result = await db.execute(
        select(func.count(Document.id)).where(Document.indexed_at.isnot(None), tenant_filter)
    )
    indexed = indexed_result.scalar() or 0

    chunk_result = await db.execute(select(func.count(DocumentChunk.id)))
    total_chunks = chunk_result.scalar() or 0

    return {
        "total_documents": total,
        "indexed_documents": indexed,
        "total_chunks": total_chunks,
        "by_status": by_status,
        "by_type": by_type,
    }
