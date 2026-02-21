"""Incident models for incident reporting and investigation."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, ReferenceNumberMixin, TimestampMixin
from src.infrastructure.database import Base

if TYPE_CHECKING:
    from src.domain.models.user import User


class IncidentType(str, enum.Enum):
    """Type of incident."""

    INJURY = "injury"
    NEAR_MISS = "near_miss"
    HAZARD = "hazard"
    PROPERTY_DAMAGE = "property_damage"
    ENVIRONMENTAL = "environmental"
    SECURITY = "security"
    QUALITY = "quality"
    OTHER = "other"


class IncidentSeverity(str, enum.Enum):
    """Severity of incident."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class IncidentStatus(str, enum.Enum):
    """Status of incident."""

    REPORTED = "reported"
    UNDER_INVESTIGATION = "under_investigation"
    PENDING_ACTIONS = "pending_actions"
    ACTIONS_IN_PROGRESS = "actions_in_progress"
    PENDING_REVIEW = "pending_review"
    CLOSED = "closed"


class ActionStatus(str, enum.Enum):
    """Status of an action."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class Incident(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Incident model for workplace incidents, near misses, and hazards."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Incident identification
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    incident_type: Mapped[IncidentType] = mapped_column(
        SQLEnum(IncidentType, native_enum=False), default=IncidentType.OTHER
    )
    severity: Mapped[IncidentSeverity] = mapped_column(
        SQLEnum(IncidentSeverity, native_enum=False), default=IncidentSeverity.MEDIUM
    )
    status: Mapped[IncidentStatus] = mapped_column(
        SQLEnum(IncidentStatus, native_enum=False), default=IncidentStatus.REPORTED
    )

    # When and where
    incident_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reported_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Tenant isolation
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)

    # Who was involved
    reporter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reporter_email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )  # Portal user email for tracking
    reporter_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Portal user name
    people_involved: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Names/details of people involved
    witnesses: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Immediate response
    immediate_actions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    first_aid_given: Mapped[bool] = mapped_column(Boolean, default=False)
    emergency_services_called: Mapped[bool] = mapped_column(Boolean, default=False)

    # Investigation
    investigator_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    investigation_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    investigation_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contributing_factors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # RIDDOR classification (UK specific)
    is_riddor_reportable: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    riddor_classification: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    riddor_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Standard mapping
    clause_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Risk linkage
    linked_risk_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Comma-separated risk IDs

    # Email ingestion source
    source_type: Mapped[str] = mapped_column(String(50), default="manual")  # manual, email, api
    source_email_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Portal form source tracking (for audit traceability)
    source_form_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., portal_incident_v1

    # Closure
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    closure_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # SIF (Serious Injury or Fatality) Classification
    is_sif: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    is_psif: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)  # Potential SIF
    sif_classification: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # SIF, pSIF, Non-SIF
    sif_assessment_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sif_assessed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    sif_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    life_altering_potential: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    precursor_events: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # List of precursor indicators
    control_failures: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # List of failed controls

    # Relationships
    reporter: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reporter_id],
        lazy="noload",
    )
    actions: Mapped[List["IncidentAction"]] = relationship(
        "IncidentAction",
        back_populates="incident",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Incident(id={self.id}, ref='{self.reference_number}', type='{self.incident_type}')>"


class IncidentAction(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Action model for corrective/preventive actions from incidents."""

    __tablename__ = "incident_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)

    # Action details
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), default="corrective")  # corrective, preventive, improvement
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # critical, high, medium, low

    # Assignment
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Status and dates
    status: Mapped[ActionStatus] = mapped_column(SQLEnum(ActionStatus, native_enum=False), default=ActionStatus.OPEN)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Evidence
    completion_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Effectiveness
    effectiveness_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    effectiveness_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_effective: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="actions")

    def __repr__(self) -> str:
        return f"<IncidentAction(id={self.id}, ref='{self.reference_number}', status='{self.status}')>"
