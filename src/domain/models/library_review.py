"""Governance Library Wave W3 — review packs + regulatory findings."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.domain.models.base import Base, CaseInsensitiveEnum, TimestampMixin


class ReviewPackStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class FindingDisposition(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class HorizonProvider(str, enum.Enum):
    STUB = "stub"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    PERPLEXITY = "perplexity"


class LibraryReviewPack(Base, TimestampMixin):
    """A human review session opened when a document enters its 90-day window."""

    __tablename__ = "library_review_packs"
    __table_args__ = (
        Index("ix_library_review_packs_tenant_status", "tenant_id", "status"),
        Index(
            "uq_library_review_packs_one_open",
            "tenant_id",
            "document_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ReviewPackStatus] = mapped_column(
        CaseInsensitiveEnum(ReviewPackStatus),
        nullable=False,
        default=ReviewPackStatus.OPEN,
        index=True,
    )
    window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    window_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opened_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    internal_inputs: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    findings: Mapped[List["LibraryRegulatoryFinding"]] = relationship(
        "LibraryRegulatoryFinding",
        back_populates="pack",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<LibraryReviewPack(id={self.id}, document_id={self.document_id}, status={self.status})>"


class LibraryRegulatoryFinding(Base, TimestampMixin):
    """A horizon-scan finding attached to a review pack; requires human disposition."""

    __tablename__ = "regulatory_findings"
    __table_args__ = (Index("ix_regulatory_findings_pack_disposition", "pack_id", "disposition"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    pack_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("library_review_packs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    raw_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    disposition: Mapped[FindingDisposition] = mapped_column(
        CaseInsensitiveEnum(FindingDisposition),
        nullable=False,
        default=FindingDisposition.PENDING,
        index=True,
    )
    dispositioned_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    dispositioned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    disposition_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    pack: Mapped["LibraryReviewPack"] = relationship("LibraryReviewPack", back_populates="findings")

    def __repr__(self) -> str:
        return f"<LibraryRegulatoryFinding(id={self.id}, pack_id={self.pack_id}, disposition={self.disposition})>"
