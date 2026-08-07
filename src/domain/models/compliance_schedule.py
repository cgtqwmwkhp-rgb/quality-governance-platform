"""Compliance Schedule models — organisation/location obligations (Wave 0).

Occurrence model (ADR-0020): requirements hold the schedule (`next_due_date`);
records are events for completed or missed occurrences. Global templates are
seeded from ``specs/compliance-schedule/catalogue.json``.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import (
    AuditTrailMixin,
    Base,
    CaseInsensitiveEnum,
    DataClassification,
    SoftDeleteMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from src.domain.models.document import Document
    from src.domain.models.location import Location

_JSON = _PG_JSONB().with_variant(JSON, "sqlite")


class ComplianceScheduleAnchor(str, enum.Enum):
    """How ``next_due_date`` advances after an occurrence closes."""

    COMPLETION = "completion"  # next = completed_at + interval
    SCHEDULE = "schedule"  # next = previous due_date + interval


class ComplianceFilingStatus(str, enum.Enum):
    """Library filing state for a completed record (separate from completion)."""

    NOT_FILED = "not_filed"
    FILED = "filed"
    FILING_FAILED = "filing_failed"


class ComplianceRecordOutcome(str, enum.Enum):
    """Whether the occurrence was completed or marked missed by the sweep."""

    COMPLETED = "completed"
    MISSED = "missed"


class ComplianceRequirementTemplate(Base, TimestampMixin):
    """Global catalogue row (tenant_id always NULL). Seeded from the spec file."""

    __tablename__ = "compliance_requirement_templates"
    __table_args__ = (
        UniqueConstraint("template_key", name="uq_compliance_requirement_templates_key"),
        CheckConstraint(
            "anchor IN ('completion', 'schedule')",
            name="ck_compliance_requirement_templates_anchor",
        ),
        CheckConstraint(
            "frequency_months IS NOT NULL OR frequency_days IS NOT NULL",
            name="ck_compliance_requirement_templates_frequency",
        ),
    )
    __data_classification__ = DataClassification.C2_INTERNAL

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    template_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    taxonomy_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    regulatory_basis: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    frequency_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    frequency_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    anchor: Mapped[ComplianceScheduleAnchor] = mapped_column(
        CaseInsensitiveEnum(ComplianceScheduleAnchor),
        nullable=False,
        default=ComplianceScheduleAnchor.SCHEDULE,
    )
    statutory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    requirements: Mapped[List["ComplianceRequirement"]] = relationship(
        "ComplianceRequirement", back_populates="template"
    )

    def __repr__(self) -> str:
        return f"<ComplianceRequirementTemplate(key='{self.template_key}')>"


class ComplianceRequirement(Base, TimestampMixin, SoftDeleteMixin, AuditTrailMixin):
    """Tenant obligation schedule — one row per (obligation × location|org-wide)."""

    __tablename__ = "compliance_requirements"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "reference_number",
            name="uq_compliance_requirements_tenant_reference",
        ),
        CheckConstraint(
            "anchor IN ('completion', 'schedule')",
            name="ck_compliance_requirements_anchor",
        ),
        CheckConstraint(
            "frequency_months IS NOT NULL OR frequency_days IS NOT NULL",
            name="ck_compliance_requirements_frequency",
        ),
    )
    __data_classification__ = DataClassification.C3_CONFIDENTIAL

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Tenant-scoped reference (CSR-YYYY-####); not globally unique.
    reference_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("compliance_requirement_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    location_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    taxonomy_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    regulatory_basis: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Structured Standards link (AI assist Accept). Free-text basis remains the citation.
    # No ORM relationships: `_requirement_response` is sync and must not lazy-load under asyncio.
    regulatory_standard_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("standards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    regulatory_clause_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clauses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    frequency_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    frequency_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    anchor: Mapped[ComplianceScheduleAnchor] = mapped_column(
        CaseInsensitiveEnum(ComplianceScheduleAnchor),
        nullable=False,
        default=ComplianceScheduleAnchor.SCHEDULE,
    )
    statutory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    next_due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    last_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    template: Mapped[Optional["ComplianceRequirementTemplate"]] = relationship(
        "ComplianceRequirementTemplate", back_populates="requirements"
    )
    location: Mapped[Optional["Location"]] = relationship("Location")
    records: Mapped[List["ComplianceRecord"]] = relationship(
        "ComplianceRecord", back_populates="requirement", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ComplianceRequirement(id={self.id}, ref='{self.reference_number}')>"


class ComplianceRecord(Base, TimestampMixin, AuditTrailMixin):
    """One completed or missed occurrence of a requirement."""

    __tablename__ = "compliance_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "reference_number",
            name="uq_compliance_records_tenant_reference",
        ),
        UniqueConstraint(
            "tenant_id",
            "requirement_id",
            "due_date",
            name="uq_compliance_records_tenant_requirement_due",
        ),
        CheckConstraint(
            "outcome IN ('completed', 'missed')",
            name="ck_compliance_records_outcome",
        ),
        CheckConstraint(
            "filing_status IN ('not_filed', 'filed', 'filing_failed')",
            name="ck_compliance_records_filing_status",
        ),
    )
    __data_classification__ = DataClassification.C3_CONFIDENTIAL

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    reference_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("compliance_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    outcome: Mapped[ComplianceRecordOutcome] = mapped_column(
        CaseInsensitiveEnum(ComplianceRecordOutcome), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    check_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    library_document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filing_status: Mapped[ComplianceFilingStatus] = mapped_column(
        CaseInsensitiveEnum(ComplianceFilingStatus),
        nullable=False,
        default=ComplianceFilingStatus.NOT_FILED,
    )
    filing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    requirement: Mapped["ComplianceRequirement"] = relationship("ComplianceRequirement", back_populates="records")
    library_document: Mapped[Optional["Document"]] = relationship("Document")

    def __repr__(self) -> str:
        return f"<ComplianceRecord(id={self.id}, ref='{self.reference_number}', outcome={self.outcome})>"


class ComplianceOcrDraftStatus(str, enum.Enum):
    """Lifecycle of an FRA / PAS 79 OCR propose→confirm draft."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISCARDED = "discarded"


class ComplianceOcrFilingStatus(str, enum.Enum):
    """Library filing state for a confirmed FRA OCR draft (separate from confirm)."""

    NOT_FILED = "not_filed"
    FILED = "filed"
    FILING_FAILED = "filing_failed"


class ComplianceScheduleOcrDraft(Base, TimestampMixin, AuditTrailMixin):
    """Propose→confirm draft for FRA / PAS 79 OCR ingest (Wave 3).

    Stores field proposals and Priority Action Plan rows. Confirmed actions are
    recorded on the draft only in PR 1 — no CAPA rows are created. Full OCR text
    is deliberately not persisted; per-field evidence snippets live in
    ``proposed_json`` (capped at 200 characters each).
    """

    __tablename__ = "compliance_schedule_ocr_drafts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'discarded')",
            name="ck_cs_ocr_drafts_status",
        ),
        CheckConstraint(
            "filing_status IN ('not_filed', 'filed', 'filing_failed')",
            name="ck_cs_ocr_drafts_filing_status",
        ),
        CheckConstraint("purpose IN ('fra_pas79')", name="ck_cs_ocr_drafts_purpose"),
        Index(
            "uq_cs_ocr_drafts_pending_source",
            "tenant_id",
            "requirement_id",
            "source_checksum_sha256",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
        Index("ix_cs_ocr_drafts_tenant_status", "tenant_id", "status"),
    )
    __data_classification__ = DataClassification.C3_CONFIDENTIAL

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("compliance_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    purpose: Mapped[str] = mapped_column(String(32), nullable=False, default="fra_pas79")
    status: Mapped[ComplianceOcrDraftStatus] = mapped_column(
        CaseInsensitiveEnum(ComplianceOcrDraftStatus),
        nullable=False,
        default=ComplianceOcrDraftStatus.PENDING,
        index=True,
    )

    source_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_storage_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # When set, the draft reuses an occurrence EvidenceAsset blob and must not
    # delete that blob on discard (or IntegrityError cleanup).
    evidence_asset_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("evidence_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    extraction_method: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ocr_provider_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    proposed_json: Mapped[dict] = mapped_column(_JSON, nullable=False)
    warnings_json: Mapped[Optional[list]] = mapped_column(_JSON, nullable=True)
    confirmed_json: Mapped[Optional[dict]] = mapped_column(_JSON, nullable=True)
    applied_json: Mapped[Optional[dict]] = mapped_column(_JSON, nullable=True)

    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    discarded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    library_document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filing_status: Mapped[ComplianceOcrFilingStatus] = mapped_column(
        CaseInsensitiveEnum(ComplianceOcrFilingStatus),
        nullable=False,
        default=ComplianceOcrFilingStatus.NOT_FILED,
    )
    filing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    requirement: Mapped["ComplianceRequirement"] = relationship("ComplianceRequirement")
    library_document: Mapped[Optional["Document"]] = relationship("Document")

    def __repr__(self) -> str:
        return f"<ComplianceScheduleOcrDraft(id={self.id}, status={self.status})>"
