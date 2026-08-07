"""Doc Graph (ADR-0021): authored library Document ↔ Document edges.

Nodes are library ``Document`` rows only. Authored edge types are closed;
lifecycle-derived types (``supersedes``, ``derived_from``) are never stored here.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base, CaseInsensitiveEnum, DataClassification, TimestampMixin


class DocumentEdgeType(str, enum.Enum):
    """Authored Doc Graph edge types (closed set)."""

    IMPLEMENTS = "implements"
    REQUIRES_RECORD = "requires_record"
    REFERENCES = "references"
    RELATED_TO = "related_to"
    CONFLICTS_WITH = "conflicts_with"


class DocumentEdgeStatus(str, enum.Enum):
    """Propose → confirm posture (mirrors CEL; separate enum)."""

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class DocumentEdgeMethod(str, enum.Enum):
    """How the edge was created."""

    MANUAL = "manual"
    AI = "ai"
    EXTRACTED = "extracted"
    HEURISTIC = "heuristic"
    AUTO = "auto"


_EDGE_TYPE_VALUES = ", ".join(f"'{m.value}'" for m in DocumentEdgeType)
_STATUS_VALUES = ", ".join(f"'{m.value}'" for m in DocumentEdgeStatus)
_METHOD_VALUES = ", ".join(f"'{m.value}'" for m in DocumentEdgeMethod)

# Undirected peer types: service stores src_document_id < dst_document_id.
CANONICAL_UNDIRECTED_TYPES = frozenset(
    {
        DocumentEdgeType.RELATED_TO,
        DocumentEdgeType.CONFLICTS_WITH,
    }
)


class DocumentEdge(Base, TimestampMixin):
    """Typed relationship between two library documents within a tenant."""

    __tablename__ = "document_edges"
    __data_classification__ = DataClassification.C2_INTERNAL
    __table_args__ = (
        CheckConstraint(
            f"edge_type IN ({_EDGE_TYPE_VALUES})",
            name="ck_document_edges_edge_type",
        ),
        CheckConstraint(
            f"status IN ({_STATUS_VALUES})",
            name="ck_document_edges_status",
        ),
        CheckConstraint(
            f"created_method IN ({_METHOD_VALUES})",
            name="ck_document_edges_created_method",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_document_edges_confidence",
        ),
        CheckConstraint(
            "src_document_id <> dst_document_id",
            name="ck_document_edges_no_self_loop",
        ),
        CheckConstraint(
            "(edge_type = 'implements') OR (is_primary_parent = false)",
            name="ck_document_edges_primary_parent_implements_only",
        ),
        # Soft-delete aware uniqueness: one live edge per typed pair per tenant.
        Index(
            "ux_document_edges_tenant_src_dst_type_live",
            "tenant_id",
            "src_document_id",
            "dst_document_id",
            "edge_type",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_document_edges_tenant_src", "tenant_id", "src_document_id"),
        Index("ix_document_edges_tenant_dst", "tenant_id", "dst_document_id"),
        Index("ix_document_edges_tenant_type_status", "tenant_id", "edge_type", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    src_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    dst_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    src_pel_doc_ref: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    dst_pel_doc_ref: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    edge_type: Mapped[DocumentEdgeType] = mapped_column(
        CaseInsensitiveEnum(DocumentEdgeType, length=32),
        nullable=False,
    )
    is_primary_parent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    status: Mapped[DocumentEdgeStatus] = mapped_column(
        CaseInsensitiveEnum(DocumentEdgeStatus, length=20),
        nullable=False,
        default=DocumentEdgeStatus.PROPOSED,
        server_default=text("'proposed'"),
    )
    created_method: Mapped[DocumentEdgeMethod] = mapped_column(
        CaseInsensitiveEnum(DocumentEdgeMethod, length=20),
        nullable=False,
        default=DocumentEdgeMethod.MANUAL,
        server_default=text("'manual'"),
    )

    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    confirmed_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # references-only citation locator (nullable for other types)
    cited_document_version_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("document_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    chunk_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    char_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    char_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quote_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    citation_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cited_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return (
            f"<DocumentEdge(id={self.id}, type={self.edge_type!r}, "
            f"src={self.src_document_id}, dst={self.dst_document_id}, "
            f"status={self.status!r})>"
        )
