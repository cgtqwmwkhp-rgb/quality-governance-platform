"""Document Management API Routes.

Enterprise document management with:
- Upload & processing
- AI-powered analysis
- Semantic search
- Version control
- Access control
"""

import io
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select, or_

from src.api.dependencies import CurrentUser, DbSession
from src.domain.models.document import (
    Document,
    DocumentAnnotation,
    DocumentChunk,
    DocumentSearchLog,
    DocumentStatus,
    DocumentType,
    DocumentVersion,
    FileType,
    IndexJob,
    IndexJobStatus,
    SensitivityLevel,
)
from src.domain.services.document_ai_service import (
    DocumentAIService,
    EmbeddingService,
    VectorSearchService,
)

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
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(None),
    document_type: str = Form("other"),
    category: str = Form(None),
    department: str = Form(None),
    sensitivity: str = Form("internal"),
    db: DbSession = None,
    current_user: CurrentUser = None,
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

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Generate unique file path (for Azure Blob Storage)
    file_path = f"documents/{datetime.utcnow().strftime('%Y/%m')}/{uuid.uuid4()}/{file.filename}"

    # Create document record
    doc = Document(
        title=title,
        description=description,
        file_name=file.filename,
        file_type=file_type,
        file_size=file_size,
        file_path=file_path,
        mime_type=file.content_type,
        document_type=(
            DocumentType(document_type)
            if document_type in [d.value for d in DocumentType]
            else DocumentType.OTHER
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

    # TODO: Upload to Azure Blob Storage
    # await azure_blob_service.upload(file_path, content)

    # Trigger AI processing (async background job)
    # For now, do inline processing
    try:
        ai_service = DocumentAIService()

        # Extract text content based on file type
        text_content = ""
        if file_type in [FileType.TXT, FileType.MD]:
            text_content = content.decode("utf-8", errors="ignore")
        elif file_type == FileType.PDF:
            # TODO: Use pdf-parse or similar
            text_content = f"[PDF content extraction not implemented for {file.filename}]"
        elif file_type in [FileType.DOCX, FileType.DOC]:
            # TODO: Use python-docx
            text_content = f"[Word content extraction not implemented for {file.filename}]"
        elif file_type in [FileType.XLSX, FileType.XLS, FileType.CSV]:
            # TODO: Use openpyxl/pandas
            text_content = f"[Spreadsheet content extraction not implemented for {file.filename}]"

        if text_content and not text_content.startswith("["):
            # Analyze with AI
            analysis = await ai_service.analyze_document(text_content, file.filename, file_ext)

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

            # Generate chunks
            chunks = await ai_service.generate_chunks(text_content)
            doc.chunk_count = len(chunks)

            # Save chunks
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

            # Generate embeddings and index
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

    except Exception as e:
        doc.status = DocumentStatus.FAILED
        doc.indexing_error = str(e)
        await db.commit()

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

    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Increment view count
    document.view_count += 1
    document.last_accessed_at = datetime.utcnow()
    await db.commit()

    return DocumentResponse.model_validate(document)


# =============================================================================
# SEARCH
# =============================================================================


@router.get("/search/semantic", response_model=SearchResponse)
async def semantic_search(
    q: str = Query(..., min_length=3),
    top_k: int = Query(10, ge=1, le=50),
    document_type: Optional[str] = None,
    db: DbSession = None,
    current_user: CurrentUser = None,
):
    """Semantic search across documents using AI embeddings."""

    import time

    start_time = time.time()

    vector_service = VectorSearchService()

    # Build filter
    filter_dict = None
    if document_type:
        filter_dict = {"document_type": document_type}

    # Search vectors
    matches = await vector_service.search(q, top_k=top_k, filter_dict=filter_dict)

    results = []
    doc_ids = set()

    for match in matches:
        doc_id = match.get("metadata", {}).get("document_id")
        if doc_id and doc_id not in doc_ids:
            doc_ids.add(doc_id)

            # Get document info
            doc_result = await db.execute(select(Document).where(Document.id == doc_id))
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

    # Log search
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


@router.get("/{document_id}/annotations", response_model=list[AnnotationResponse])
async def list_annotations(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List annotations for a document."""

    query = select(DocumentAnnotation).where(DocumentAnnotation.document_id == document_id)

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
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    if not doc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")

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


@router.get("/stats/overview")
async def get_document_stats(
    db: DbSession,
    current_user: CurrentUser,
):
    """Get document library statistics."""

    # Total documents
    total_result = await db.execute(select(func.count(Document.id)))
    total = total_result.scalar() or 0

    # By status
    status_result = await db.execute(
        select(Document.status, func.count(Document.id)).group_by(Document.status)
    )
    by_status = {
        row[0].value if hasattr(row[0], "value") else row[0]: row[1] for row in status_result.all()
    }

    # By type
    type_result = await db.execute(
        select(Document.document_type, func.count(Document.id)).group_by(Document.document_type)
    )
    by_type = {
        row[0].value if hasattr(row[0], "value") else row[0]: row[1] for row in type_result.all()
    }

    # Indexed count
    indexed_result = await db.execute(
        select(func.count(Document.id)).where(Document.indexed_at.isnot(None))
    )
    indexed = indexed_result.scalar() or 0

    # Total chunks
    chunk_result = await db.execute(select(func.count(DocumentChunk.id)))
    total_chunks = chunk_result.scalar() or 0

    return {
        "total_documents": total,
        "indexed_documents": indexed,
        "total_chunks": total_chunks,
        "by_status": by_status,
        "by_type": by_type,
    }
