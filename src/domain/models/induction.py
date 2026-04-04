"""Induction/Training execution models for engineer training and development."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from src.domain.models.engineer import Engineer
    from src.domain.models.user import User

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, Base, CaseInsensitiveEnum, TimestampMixin


class InductionStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InductionStage(str, enum.Enum):
    STAGE_1_ONSITE = "stage_1_onsite"
    STAGE_2_FIELD = "stage_2_field"


class UnderstandingVerdict(str, enum.Enum):
    COMPETENT = "competent"
    NOT_YET_COMPETENT = "not_yet_competent"
    NA = "na"


class InductionRun(Base, TimestampMixin, AuditTrailMixin):
    """A training/induction session for an engineer."""

    __tablename__ = "induction_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reference_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    template_id: Mapped[int] = mapped_column(ForeignKey("audit_templates.id"), nullable=False, index=True)
    template_version: Mapped[int] = mapped_column(Integer, default=1)

    engineer_id: Mapped[int] = mapped_column(ForeignKey("engineers.id"), nullable=False, index=True)
    supervisor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    asset_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("asset_types.id"), nullable=True, index=True)

    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    stage: Mapped[InductionStage] = mapped_column(
        CaseInsensitiveEnum(InductionStage),
        default=InductionStage.STAGE_1_ONSITE,
    )
    status: Mapped[InductionStatus] = mapped_column(
        CaseInsensitiveEnum(InductionStatus),
        default=InductionStatus.DRAFT,
        index=True,
    )

    scheduled_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Counts
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    competent_count: Mapped[int] = mapped_column(Integer, default=0)
    not_yet_competent_count: Mapped[int] = mapped_column(Integer, default=0)

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Relationships
    engineer: Mapped["Engineer"] = relationship("Engineer", foreign_keys=[engineer_id])
    supervisor: Mapped["User"] = relationship("User", foreign_keys=[supervisor_id])
    responses: Mapped[List["InductionResponse"]] = relationship(
        "InductionResponse", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<InductionRun(id={self.id}, ref='{self.reference_number}', status={self.status})>"


class InductionResponse(Base, TimestampMixin):
    """Response to a single skill element during induction/training."""

    __tablename__ = "induction_responses"
    __table_args__ = (UniqueConstraint("run_id", "question_id", name="uq_induction_responses_run_question"),)

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("induction_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("audit_questions.id"), nullable=False, index=True)

    shown_explained: Mapped[bool] = mapped_column(Boolean, default=False)

    understanding: Mapped[Optional[UnderstandingVerdict]] = mapped_column(
        CaseInsensitiveEnum(UnderstandingVerdict), nullable=True
    )

    supervisor_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Per-item engineer sign-off
    engineer_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    engineer_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped["InductionRun"] = relationship("InductionRun", back_populates="responses")

    def __repr__(self) -> str:
        return f"<InductionResponse(id={self.id}, understanding={self.understanding})>"
