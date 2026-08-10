"""Document Management System Models.

Enterprise-grade document management with AI-powered processing,
semantic search, and full governance integration.
"""

import enum
import functools
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    event,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, Base, CaseInsensitiveEnum, ReferenceNumberMixin, TimestampMixin
from src.domain.models.document_library import CASCADE_LEVEL_MAX, CASCADE_LEVEL_MIN
from src.domain.models.enums import DocumentStatus, DocumentType

# =============================================================================
# ENUMS
# =============================================================================


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
    __table_args__ = (
        # WC-1 — legal-hold enforcement always reads (tenant_id, matter).
        Index("ix_documents_tenant_legal_matter_reference", "tenant_id", "legal_matter_reference"),
        # NS-1 — a level outside 1..5 has no band to allocate from and no
        # meaning in the cascade. NULL stays legal: legacy rows predate the
        # cascade, and a document may be filed before its level is confirmed.
        CheckConstraint(
            f"cascade_level IS NULL OR (cascade_level >= {CASCADE_LEVEL_MIN} AND cascade_level <= {CASCADE_LEVEL_MAX})",
            name="ck_documents_cascade_level_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Basic info
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # File info
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[FileType] = mapped_column(CaseInsensitiveEnum(FileType), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)  # Azure Blob path
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # F-1 / L-41 — signed-URL gate. Legacy rows backfilled to "clean".
    malware_scan_status: Mapped[str] = mapped_column(String(32), nullable=False, default="clean")

    # Classification
    document_type: Mapped[DocumentType] = mapped_column(CaseInsensitiveEnum(DocumentType), default=DocumentType.OTHER)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sensitivity: Mapped[SensitivityLevel] = mapped_column(
        CaseInsensitiveEnum(SensitivityLevel), default=SensitivityLevel.INTERNAL
    )

    # Status & workflow
    status: Mapped[DocumentStatus] = mapped_column(
        CaseInsensitiveEnum(DocumentStatus), default=DocumentStatus.PENDING, index=True
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

    # Governance Library taxonomy (Wave W0) — sits alongside `reference_number`
    # (DOC-YYYY-####). `pel_doc_ref` is a separate, atomically-allocated
    # reference (PEL-<FUNCTION>-<SEQ> since WA-2 / ADR-0023); see
    # src.domain.services.document_category_service.allocate_pel_doc_ref.
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("document_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    pel_doc_ref: Mapped[Optional[str]] = mapped_column(String(30), unique=True, nullable=True, index=True)

    # Owning function (WA-2 / ADR-0023) — the axis the PEL reference is drawn
    # from, deliberately distinct from `category_id`. Fixed at filing: it is a
    # property of the document, not a live pointer to the current owner, so
    # RESTRICT rather than SET NULL — orphaning it would leave a reference
    # nothing accounts for. Nullable because a document may be filed before a
    # function is confirmed, in which case no PEL reference is allocated.
    function_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("document_functions.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    # Cascade level 1..5 (NS-1 / Northern Star v6). This is the *same* number as
    # the band digit of `pel_doc_ref` whenever one is allocated — the allocator
    # takes the level and returns the reference, so R02 ("the first digit of the
    # sequence equals the cascade level") holds by construction rather than by
    # a reconciliation job. Nullable because legacy rows predate the cascade and
    # a document may be filed before its level is confirmed; but a PEL reference
    # is never issued without one, because the band it would be drawn from is
    # exactly what the level names.
    cascade_level: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, index=True)

    # Site/workshop binding — reuses the existing Location model (no new Site table).
    site_location_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # WC-1 / L-40 — which legal matter this document is filed under. Hold state
    # is NOT stored here: `matter_legal_holds` remains the only hold register,
    # and a document is frozen while an ACTIVE hold exists for this matter in
    # the same tenant. NULL means "filed under no matter", not "unknown".
    legal_matter_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Northern Star R20 (Wave W6 / NS-WF) — a document states its review cycle and
    # the *basis* for it before it can be issued. Deliberately two columns and
    # deliberately nullable: the pack says there is no default cycle, so an
    # unstated cycle must read as unstated rather than as a house standard nobody
    # agreed to, and legacy rows predate the rule. `DocumentCategory.review_cycle`
    # is free text guidance for the whole category and is not the same fact.
    review_cycle_months: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    review_cycle_basis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Governance Library filing (Wave W1) — defaults from category on create.
    access_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # all_staff|managers|restricted
    is_statutory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retention_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # CUT-1 / ADR-0023 / F-7 §2 — machine-readable retention, copied onto the
    # document when it is filed. `retention_until` stays the single disposal
    # clock; these three record the policy that produced it, which is what makes
    # a disposal decision answerable (R19 "a number of years with a basis") and
    # what stops a later taxonomy edit silently re-dating documents already
    # filed under the old rule. Nullable: a category rule the CUT-1 grammar
    # refuses to read leaves them unset, and unset means "keep", never "dispose".
    retention_years: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    retention_anchor: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    retention_basis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    duplicate_warning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_warning_detail: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

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
# IMMUTABLE PEL REFERENCE (WA-2 / ADR-0023)
# =============================================================================

# A PEL reference is printed on the document face and cited in client audit
# packs, so it is allocated once and never rewritten: a mis-filed reference is
# corrected by re-filing (new reference, old one retired), never by editing in
# place. The same holds for the function it was drawn from — rewriting that
# would leave the reference describing a function the document no longer claims.
#
# NULL -> value is allowed (the reference may be allocated after the row is
# created, when the function is confirmed). value -> different value and
# value -> NULL are refused.
#
# This listener is the in-process guard and is what the unit tests exercise on
# SQLite. It cannot see a raw `UPDATE documents SET ...` that bypasses the ORM,
# and it deliberately does not force a load of the previous value (that would
# emit lazy IO outside the async greenlet), so an expired attribute is passed
# over here. The `trg_documents_pel_doc_ref_immutable` trigger installed by the
# WA-2 migration is the authoritative enforcement on PostgreSQL.
_IMMUTABLE_ONCE_SET = ("pel_doc_ref", "function_id")


def _refuse_rewrite(attribute: str, target: "Document", value: object, oldvalue: object, initiator: object) -> object:
    from sqlalchemy.orm.base import NO_VALUE

    from src.domain.exceptions import ConflictError

    if oldvalue is NO_VALUE or oldvalue is None or oldvalue == value:
        return value
    raise ConflictError(
        f"Document.{attribute} is immutable once allocated "
        f"({oldvalue!r} -> {value!r}). Re-file the document to issue a new "
        "PEL reference; never edit an issued one in place (ADR-0023).",
        code="PEL_REF_IMMUTABLE",
    )


for _attribute in _IMMUTABLE_ONCE_SET:
    event.listen(
        getattr(Document, _attribute),
        "set",
        functools.partial(_refuse_rewrite, _attribute),
        retval=True,
    )
del _attribute


def _refuse_level_change_after_issue(target: "Document", value: object, oldvalue: object, initiator: object) -> object:
    """Refuse a cascade-level edit once a PEL reference has been issued (R02/R05).

    The band digit of an issued reference *is* the cascade level, so moving the
    level on an issued document would leave `PEL-HSEQ-3001` claiming level 3
    while the record claims level 4 — and the reference cannot follow, because
    it is immutable. Northern Star R05 says a level change is a reissue:
    withdraw the old reference and issue a new one in the new band with a
    Supersedes link.

    Before issue the level is freely editable — a draft's level is exactly the
    thing a filer is still deciding. Unlike `_refuse_rewrite` this therefore
    keys off `pel_doc_ref`, not off the old level being set.

    `pel_doc_ref` is read out of the instance dict rather than by attribute, for
    the same reason the listener above does not force a load: touching an
    expired attribute here would emit lazy IO outside the async greenlet. An
    unloaded reference reads as "not issued" and the edit is allowed through —
    the `trg_documents_pel_doc_ref_immutable` trigger is the authoritative
    guard on PostgreSQL and catches exactly that case.
    """
    from sqlalchemy.orm.base import NO_VALUE

    from src.domain.exceptions import ConflictError

    if oldvalue is NO_VALUE or oldvalue is None or oldvalue == value:
        return value
    issued_ref = target.__dict__.get("pel_doc_ref")
    if issued_ref is None:
        return value
    raise ConflictError(
        f"Document.cascade_level is fixed once a PEL reference is issued "
        f"({oldvalue!r} -> {value!r}); {issued_ref} is banded to level "
        f"{oldvalue!r}. Re-file the document to issue a reference in the new "
        "band and supersede this one (Northern Star R02/R05).",
        code="PEL_REF_IMMUTABLE",
    )


event.listen(Document.cascade_level, "set", _refuse_level_change_after_issue, retval=True)


# =============================================================================
# DOCUMENT CHUNKS (for RAG)
# =============================================================================


class DocumentChunk(Base, TimestampMixin):
    """Document chunk for vector search and RAG."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_tenant_document", "tenant_id", "document_id"),
        Index(
            "ix_document_chunks_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
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

    # Postgres FTS (maintained by trigger); Text variant keeps SQLite create_all working in tests
    search_vector: Mapped[Optional[str]] = mapped_column(
        TSVECTOR().with_variant(Text(), "sqlite"),
        nullable=True,
        deferred=True,
    )

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

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
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
    """Document version history with publish immutability."""

    __tablename__ = "document_versions"

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)

    # Version info
    version_number: Mapped[str] = mapped_column(String(20), nullable=False)
    change_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_type: Mapped[str] = mapped_column(String(50), default="revision", nullable=False)

    # Lifecycle — published/superseded rows are immutable (read-only)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False, index=True)
    is_immutable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Northern Star W6 / NS-WF — who issued this version and when. Kept apart
    # from `published_at` / `published_by_id`, which the approve transition uses
    # to record the approval: issue must not overwrite the approval record.
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

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
# LIBRARY ACCESS LOG (Wave W1)
# =============================================================================


class LibraryDocumentAccessLog(Base):
    """Audit trail for library document view/download via signed URLs."""

    __tablename__ = "library_document_access_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    user_name: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # view, download
    action_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


# =============================================================================
# INDEX JOBS
# =============================================================================


class IndexJob(Base, TimestampMixin):
    """Background job for document indexing to vector DB."""

    __tablename__ = "index_jobs"

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Job info
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)  # single, bulk, reindex
    status: Mapped[IndexJobStatus] = mapped_column(CaseInsensitiveEnum(IndexJobStatus), default=IndexJobStatus.PENDING)

    # Scope
    document_ids: Mapped[list] = mapped_column(JSON, nullable=False)  # [1, 2, 3]
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)

    # Progress
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    documents_processed: Mapped[int] = mapped_column(Integer, default=0)
    documents_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    documents_failed: Mapped[int] = mapped_column(Integer, default=0)
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

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
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
