"""External audit import job and draft models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import AuditTrailMixin, CaseInsensitiveEnum, ReferenceNumberMixin, TimestampMixin
from src.infrastructure.database import Base


class ExternalAuditImportStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    REVIEW_REQUIRED = "review_required"
    PROMOTING = "promoting"
    COMPLETED = "completed"
    FAILED = "failed"


class ExternalAuditDraftStatus(str, enum.Enum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PROMOTED = "promoted"


class ExternalAuditImportJob(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Tracks OCR/import processing for a source audit report."""

    __tablename__ = "external_audit_import_jobs"
    __table_args__ = (
        UniqueConstraint(
            "audit_run_id",
            "source_document_asset_id",
            "source_checksum_sha256",
            name="uq_external_audit_import_job_idempotency",
        ),
        Index("ix_external_audit_import_jobs_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_run_id: Mapped[int] = mapped_column(ForeignKey("audit_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_document_asset_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    status: Mapped[ExternalAuditImportStatus] = mapped_column(
        CaseInsensitiveEnum(ExternalAuditImportStatus),
        default=ExternalAuditImportStatus.PENDING,
        index=True,
    )
    provider_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provider_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    extraction_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    extraction_text_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_texts_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    provenance_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    analysis_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ExternalAuditDraft(Base, TimestampMixin, AuditTrailMixin):
    """Reviewable imported finding draft prior to live promotion."""

    __tablename__ = "external_audit_import_drafts"
    __table_args__ = (
        Index("ix_external_audit_import_drafts_job_status", "import_job_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    import_job_id: Mapped[int] = mapped_column(
        ForeignKey("external_audit_import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audit_run_id: Mapped[int] = mapped_column(ForeignKey("audit_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    status: Mapped[ExternalAuditDraftStatus] = mapped_column(
        CaseInsensitiveEnum(ExternalAuditDraftStatus),
        default=ExternalAuditDraftStatus.DRAFT,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    finding_type: Mapped[str] = mapped_column(String(50), nullable=False, default="nonconformity")
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    competence_verdict: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_pages_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    evidence_snippets_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    mapped_frameworks_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    mapped_standards_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    provenance_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    suggested_action_title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    suggested_action_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_risk_title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    promoted_finding_id: Mapped[Optional[int]] = mapped_column(ForeignKey("audit_findings.id"), nullable=True, index=True)
