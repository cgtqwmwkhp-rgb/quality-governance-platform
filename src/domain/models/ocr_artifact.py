"""OCR artifact persistence — page-level provider outputs and consensus tier."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base, CaseInsensitiveEnum, TimestampMixin


class OCRArtifactTier(str, enum.Enum):
    """Whether an artifact is canonical (selected) or advisory (alternate provider)."""

    CANONICAL = "canonical"
    ADVISORY = "advisory"


class OCRArtifactOverrideStatus(str, enum.Enum):
    """Human override state for dispute/ack stubs (no provider dial)."""

    NONE = "none"
    DISPUTED = "disputed"
    ACKNOWLEDGED = "acknowledged"


class OCRArtifact(Base, TimestampMixin):
    """Persisted OCR page output or consensus selection for external audit import."""

    __tablename__ = "ocr_artifacts"
    __table_args__ = (
        Index("ix_ocr_artifacts_job_page", "job_ref", "page_number"),
        Index("ix_ocr_artifacts_draft_page", "draft_ref", "page_number"),
        Index("ix_ocr_artifacts_tenant_job", "tenant_id", "job_ref"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pipeline_version: Mapped[str] = mapped_column(String(32), nullable=False)
    job_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    draft_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tier: Mapped[OCRArtifactTier] = mapped_column(
        CaseInsensitiveEnum(OCRArtifactTier),
        nullable=False,
        default=OCRArtifactTier.ADVISORY,
    )
    override_status: Mapped[OCRArtifactOverrideStatus] = mapped_column(
        CaseInsensitiveEnum(OCRArtifactOverrideStatus),
        nullable=False,
        default=OCRArtifactOverrideStatus.NONE,
    )
    override_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    overridden_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    overridden_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<OCRArtifact(id={self.id}, provider={self.provider!r}, "
            f"page={self.page_number}, tier={self.tier.value})>"
        )
