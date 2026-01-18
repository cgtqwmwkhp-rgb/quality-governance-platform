"""Document Management System Models.

Enterprise-grade document management with AI-powered processing,
semantic search, and full governance integration.
"""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, ReferenceNumberMixin, TimestampMixin
from src.infrastructure.database import Base


# =============================================================================
# ENUMS
# =============================================================================

class DocumentType(str, enum.Enum):
    """Type of document."""
    POLICY = "policy"
    PROCEDURE = "procedure"
    SOP = "sop"
    FORM = "form"
    MANUAL = "manual"
    GUIDELINE = "guideline"
    FAQ = "faq"
    TEMPLATE = "template"
    RECORD = "record"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    """Document processing and approval status."""
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class FileType(str, enum.Enum):
    """Supported file types."""
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    XLSX = "xlsx"
    XLS = "xls"
    CSV = "csv"
    MD = "md"
    TXT = "txt"
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"


class SensitivityLevel(str, enum.Enum):
    """Document sensitivity classification."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class IndexJobStatus(str, enum.Enum):
    """Status of document indexing job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


# =============================================================================
# DOCUMENT MODEL
# =============================================================================

class Document(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Enterprise document with AI-powered metadata extraction."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Basic info
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # File info
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[FileType] = mapped_column(SQLEnum(FileType, native_enum=False), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)  # Azure Blob path
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Classification
    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType, native_enum=False), default=DocumentType.OTHER
    )
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sensitivity: Mapped[SensitivityLevel] = mapped_column(
        SQLEnum(SensitivityLevel, native_enum=False), default=SensitivityLevel.INTERNAL
    )
    
    # Status & workflow
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, native_enum=False), default=DocumentStatus.PENDING
    )
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Version control
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)
    parent_document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    
    # AI-extracted metadata
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # ["safety", "procedure"]
    ai_keywords: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    ai_topics: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    ai_entities: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {contacts: [], assets: []}
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0-1
    ai_processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Document structure
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sheet_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Excel
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    has_images: Mapped[bool] = mapped_column(Boolean, default=False)
    has_tables: Mapped[bool] = mapped_column(Boolean, default=False)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    # Indexing for RAG
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    indexing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vector_namespace: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Pinecone namespace
    
    # Governance dates
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Access control
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    restricted_to_roles: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    restricted_to_departments: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Usage analytics
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Module links (governance integration)
    linked_policy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("policies.id"), nullable=True)
    linked_standard_id: Mapped[Optional[int]] = mapped_column(ForeignKey("standards.id"), nullable=True)
    
    # Ownership
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Relationships
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )
    annotations: Mapped[List["DocumentAnnotation"]] = relationship(
        "DocumentAnnotation", back_populates="document", cascade="all, delete-orphan"
    )
    versions: Mapped[List["DocumentVersion"]] = relationship(
        "DocumentVersion", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, ref='{self.reference_number}', title='{self.title[:50]}')>"


# =============================================================================
# DOCUMENT CHUNKS (for RAG)
# =============================================================================

class DocumentChunk(Base, TimestampMixin):
    """Document chunk for vector search and RAG."""

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    # Chunk content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)  # Order in document
    
    # Metadata
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    heading: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Section heading
    
    # Location info (for deep linking)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sheet_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Excel
    char_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    char_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Vector info
    vector_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Pinecone vector ID
    embedding_model: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, doc_id={self.document_id}, index={self.chunk_index})>"


# =============================================================================
# DOCUMENT ANNOTATIONS
# =============================================================================

class DocumentAnnotation(Base, TimestampMixin):
    """User annotations and highlights on documents."""

    __tablename__ = "document_annotations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Location
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sheet_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Content
    highlight_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    annotation_text: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="yellow")
    
    # Sharing
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Workflow (for issue tracking)
    annotation_type: Mapped[str] = mapped_column(String(50), default="note")  # note, issue, suggestion
    status: Mapped[str] = mapped_column(String(50), default="open")  # open, resolved, rejected
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="annotations")

    def __repr__(self) -> str:
        return f"<DocumentAnnotation(id={self.id}, doc_id={self.document_id}, type='{self.annotation_type}')>"


# =============================================================================
# DOCUMENT VERSIONS
# =============================================================================

class DocumentVersion(Base, TimestampMixin):
    """Document version history."""

    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    # Version info
    version_number: Mapped[str] = mapped_column(String(20), nullable=False)
    change_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # File info
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Ownership
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="versions")

    def __repr__(self) -> str:
        return f"<DocumentVersion(id={self.id}, doc_id={self.document_id}, v='{self.version_number}')>"


# =============================================================================
# INDEX JOBS
# =============================================================================

class IndexJob(Base, TimestampMixin):
    """Background job for document indexing to vector DB."""

    __tablename__ = "index_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Job info
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)  # single, bulk, reindex
    status: Mapped[IndexJobStatus] = mapped_column(
        SQLEnum(IndexJobStatus, native_enum=False), default=IndexJobStatus.PENDING
    )
    
    # Scope
    document_ids: Mapped[list] = mapped_column(JSON, nullable=False)  # [1, 2, 3]
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Progress
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    chunks_processed: Mapped[int] = mapped_column(Integer, default=0)
    chunks_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    chunks_failed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Error tracking
    error_log: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Rollback
    previous_vector_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Ownership
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<IndexJob(id={self.id}, status='{self.status}', docs={len(self.document_ids)})>"


# =============================================================================
# DOCUMENT SEARCH LOG
# =============================================================================

class DocumentSearchLog(Base, TimestampMixin):
    """Log of document searches for analytics and improvement."""

    __tablename__ = "document_search_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Query
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_type: Mapped[str] = mapped_column(String(50), default="semantic")  # semantic, keyword, hybrid
    
    # Results
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    result_document_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Context
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Performance
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Feedback
    was_helpful: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    clicked_document_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<DocumentSearchLog(id={self.id}, query='{self.query[:30]}...')>"
