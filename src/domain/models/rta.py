"""Road Traffic Collision (RTA) models."""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, ReferenceNumberMixin, TimestampMixin
from src.domain.models.incident import ActionStatus
from src.infrastructure.database import Base


class RTASeverity(str, enum.Enum):
    """Severity of RTA."""

    FATAL = "fatal"
    SERIOUS_INJURY = "serious_injury"
    MINOR_INJURY = "minor_injury"
    DAMAGE_ONLY = "damage_only"
    NEAR_MISS = "near_miss"


class RTAStatus(str, enum.Enum):
    """Status of RTA."""

    REPORTED = "reported"
    UNDER_INVESTIGATION = "under_investigation"
    PENDING_INSURANCE = "pending_insurance"
    PENDING_ACTIONS = "pending_actions"
    CLOSED = "closed"


class RoadTrafficCollision(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Road Traffic Collision model for vehicle accident management."""

    __tablename__ = "road_traffic_collisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Collision identification
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[RTASeverity] = mapped_column(
        SQLEnum(RTASeverity, native_enum=False), default=RTASeverity.DAMAGE_ONLY
    )
    status: Mapped[RTAStatus] = mapped_column(SQLEnum(RTAStatus, native_enum=False), default=RTAStatus.REPORTED)

    # When and where
    collision_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collision_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # HH:MM format
    reported_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[str] = mapped_column(String(500), nullable=False)
    road_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    postcode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Weather and road conditions
    weather_conditions: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    road_conditions: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lighting_conditions: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Company vehicle details
    company_vehicle_registration: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    company_vehicle_make_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_vehicle_damage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Driver details
    driver_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    driver_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    driver_email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )  # Portal user email for tracking
    driver_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    driver_injured: Mapped[bool] = mapped_column(Boolean, default=False)
    driver_injury_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Reporter details (if different from driver)
    reporter_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    reporter_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Third party details (JSON for multiple parties)
    third_parties: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Structure: [{ name, contact, phone, email, vehicle_reg, vehicle_make_model, damage,
    #               injured, injury_details, insurer, insurer_policy_number, is_at_fault }]

    # Multiple vehicles involved count
    vehicles_involved_count: Mapped[int] = mapped_column(Integer, default=2, nullable=False)

    # CCTV / Dashcam footage
    cctv_available: Mapped[bool] = mapped_column(Boolean, default=False)
    cctv_location: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    dashcam_footage_available: Mapped[bool] = mapped_column(Boolean, default=False)
    footage_secured: Mapped[bool] = mapped_column(Boolean, default=False)
    footage_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Witnesses (structured JSON for multiple witnesses)
    witnesses: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    witnesses_structured: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Structure: [{ name, phone, email, statement, willing_to_provide_statement }]

    # Police involvement
    police_attended: Mapped[bool] = mapped_column(Boolean, default=False)
    police_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    police_station: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Insurance
    insurance_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    insurance_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    insurance_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_cost: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # In pence/cents

    # Investigation
    investigator_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    investigation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fault_determination: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # company_fault, third_party_fault, shared, undetermined

    # Reporter
    reporter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Risk linkage
    linked_risk_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Portal form source tracking (for audit traceability)
    source_form_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., portal_rta_v1

    # Closure
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    closure_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    actions: Mapped[List["RTAAction"]] = relationship(
        "RTAAction",
        back_populates="rta",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<RoadTrafficCollision(id={self.id}, ref='{self.reference_number}', severity='{self.severity}')>"


# Alias for convenience
RTA = RoadTrafficCollision


class RTAAction(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Action model for RTA follow-up actions."""

    __tablename__ = "rta_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    rta_id: Mapped[int] = mapped_column(ForeignKey("road_traffic_collisions.id", ondelete="CASCADE"), nullable=False)

    # Action details
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), default="corrective")
    priority: Mapped[str] = mapped_column(String(20), default="medium")

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

    # Relationships
    rta: Mapped["RoadTrafficCollision"] = relationship("RoadTrafficCollision", back_populates="actions")

    def __repr__(self) -> str:
        return f"<RTAAction(id={self.id}, ref='{self.reference_number}', status='{self.status}')>"
