"""Engineer competency models for workforce development.

Separate from auditor_competence.py which tracks auditor qualifications.
This tracks field engineer skills, certifications, and competency lifecycle.
"""

import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, Base, CaseInsensitiveEnum, TimestampMixin


class OnboardingStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class CompetencyLifecycleState(str, enum.Enum):
    ACTIVE = "active"
    DUE = "due"
    EXPIRED = "expired"
    FAILED = "failed"
    NOT_ASSESSED = "not_assessed"


class TicketVerifyState(str, enum.Enum):
    """Verification lifecycle for statutory / scheme training tickets."""

    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Engineer(Base, TimestampMixin, AuditTrailMixin):
    """Field engineer profile with competency tracking."""

    __tablename__ = "engineers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        index=True,
    )

    display_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    pams_technician_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    employee_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    site: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Specialisations (JSON array of asset type IDs or names)
    specialisations_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Legacy certifications blob — prefer TrainingTicket rows (P0 spine).
    certifications_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # When True, PAMS sync must not overwrite QGP-edited identity fields (pseudo-DB).
    qgp_profile_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    competency_records: Mapped[List["CompetencyRecord"]] = relationship(
        "CompetencyRecord", back_populates="engineer", cascade="all, delete-orphan"
    )
    training_tickets: Mapped[List["TrainingTicket"]] = relationship(
        "TrainingTicket", back_populates="engineer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Engineer(id={self.id}, user_id={self.user_id})>"


class CompetencyRecord(Base, TimestampMixin):
    """Per assessment/induction outcome, tracking lifecycle states."""

    __tablename__ = "competency_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    engineer_id: Mapped[int] = mapped_column(ForeignKey("engineers.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type_id: Mapped[int] = mapped_column(ForeignKey("asset_types.id"), nullable=False, index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("audit_templates.id"), nullable=False)

    # Source run reference (UUID string pointing to assessment_runs.id or induction_runs.id)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "assessment" or "induction"
    source_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Outcome
    state: Mapped[CompetencyLifecycleState] = mapped_column(
        CaseInsensitiveEnum(CompetencyLifecycleState),
        default=CompetencyLifecycleState.NOT_ASSESSED,
        index=True,
    )
    outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # pass/fail/conditional

    assessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assessed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    engineer: Mapped["Engineer"] = relationship("Engineer", back_populates="competency_records")

    def __repr__(self) -> str:
        return f"<CompetencyRecord(id={self.id}, engineer={self.engineer_id}, state={self.state})>"


class CompetencyRequirement(Base, TimestampMixin):
    """Mandatory competencies per asset type with reassessment intervals."""

    __tablename__ = "competency_requirements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_type_id: Mapped[int] = mapped_column(
        ForeignKey("asset_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[int] = mapped_column(ForeignKey("audit_templates.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    reassessment_interval_days: Mapped[int] = mapped_column(Integer, default=365)
    # Optional allocation filters (role key / site) for bulk allocate
    role_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    site: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<CompetencyRequirement(id={self.id}, name='{self.name}')>"


class TrainingTicket(Base, TimestampMixin, AuditTrailMixin):
    """First-class statutory / scheme training ticket (Complo/ScopeKit/ONCREO spine).

    Replaces unqueryable certifications_json blobs for expiry, verify, and gate truth.
    """

    __tablename__ = "training_tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    engineer_id: Mapped[int] = mapped_column(ForeignKey("engineers.id", ondelete="CASCADE"), nullable=False, index=True)

    scheme: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    ticket_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    issuer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    verify_state: Mapped[TicketVerifyState] = mapped_column(
        CaseInsensitiveEnum(TicketVerifyState),
        default=TicketVerifyState.UNVERIFIED,
        nullable=False,
        index=True,
    )
    evidence_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("evidence_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    engineer: Mapped["Engineer"] = relationship("Engineer", back_populates="training_tickets")

    def __repr__(self) -> str:
        return f"<TrainingTicket(id={self.id}, scheme='{self.scheme}', number='{self.ticket_number}')>"


class OnboardingChecklist(Base, TimestampMixin):
    """Auto-generated checklist for new starters based on assigned asset types."""

    __tablename__ = "onboarding_checklists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    engineer_id: Mapped[int] = mapped_column(ForeignKey("engineers.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("competency_requirements.id"), nullable=False)

    status: Mapped[OnboardingStatus] = mapped_column(
        CaseInsensitiveEnum(OnboardingStatus),
        default=OnboardingStatus.PENDING,
        index=True,
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<OnboardingChecklist(id={self.id}, engineer={self.engineer_id}, status='{self.status}')>"
