"""Assessment execution models for on-the-job competency assessment."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from src.domain.models.engineer import Engineer
    from src.domain.models.user import User

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, CaseInsensitiveEnum, TimestampMixin
from src.domain.models.base import Base


class AssessmentStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    PENDING_DEBRIEF = "pending_debrief"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CompetencyVerdict(str, enum.Enum):
    COMPETENT = "competent"
    NOT_COMPETENT = "not_competent"
    NA = "na"


class AssessmentOutcome(str, enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    CONDITIONAL = "conditional"
    INCOMPLETE = "incomplete"


class AssessmentRun(Base, TimestampMixin, AuditTrailMixin):
    """A competency assessment of an engineer by a supervisor."""

    __tablename__ = "assessment_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reference_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # Links to unified template library (integer FK)
    template_id: Mapped[int] = mapped_column(ForeignKey("audit_templates.id"), nullable=False, index=True)
    template_version: Mapped[int] = mapped_column(Integer, default=1)

    # People — engineer_id references engineers.id; supervisor_id references users.id
    engineer_id: Mapped[int] = mapped_column(ForeignKey("engineers.id"), nullable=False, index=True)
    supervisor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Asset context
    asset_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("asset_types.id"), nullable=True, index=True)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("assets.id"), nullable=True)

    # Details
    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # GPS
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Status and dates
    status: Mapped[AssessmentStatus] = mapped_column(
        CaseInsensitiveEnum(AssessmentStatus),
        default=AssessmentStatus.DRAFT,
        index=True,
    )
    scheduled_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Outcome
    outcome: Mapped[Optional[AssessmentOutcome]] = mapped_column(CaseInsensitiveEnum(AssessmentOutcome), nullable=True)
    overall_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Debrief
    debrief_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    debrief_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # base64
    debrief_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Relationships
    engineer: Mapped["Engineer"] = relationship("Engineer", foreign_keys=[engineer_id])
    supervisor: Mapped["User"] = relationship("User", foreign_keys=[supervisor_id])
    responses: Mapped[List["AssessmentResponse"]] = relationship(
        "AssessmentResponse", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AssessmentRun(id={self.id}, ref='{self.reference_number}', status={self.status})>"


class AssessmentResponse(Base, TimestampMixin):
    """Response to a single question during a competency assessment."""

    __tablename__ = "assessment_responses"
    __table_args__ = (UniqueConstraint("run_id", "question_id", name="uq_assessment_responses_run_question"),)

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(ForeignKey("audit_questions.id"), nullable=False, index=True)

    # Verdict
    verdict: Mapped[Optional[CompetencyVerdict]] = mapped_column(CaseInsensitiveEnum(CompetencyVerdict), nullable=True)

    # Supervisor feedback
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supervisor_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Evidence
    photo_ids_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    voice_note_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Engineer sign-off on this specific feedback
    engineer_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # base64
    engineer_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    run: Mapped["AssessmentRun"] = relationship("AssessmentRun", back_populates="responses")

    def __repr__(self) -> str:
        return f"<AssessmentResponse(id={self.id}, verdict={self.verdict})>"
