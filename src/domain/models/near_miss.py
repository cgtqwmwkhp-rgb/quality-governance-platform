"""Near Miss domain model - Separate from Incidents for proper workflow tracking."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TSVECTOR

from src.infrastructure.database import Base


class NearMiss(Base):
    """Near Miss report - events that could have resulted in injury or damage but didn't."""

    __tablename__ = "near_misses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    reference_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # Reporter information
    reporter_name: Mapped[str] = mapped_column(String(200), nullable=False)
    reporter_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reporter_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reporter_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    was_involved: Mapped[bool] = mapped_column(Boolean, default=True)

    # Contract/Location
    contract: Mapped[str] = mapped_column(String(100), nullable=False)
    contract_other: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    location_coordinates: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Event details
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Description
    description: Mapped[str] = mapped_column(Text, nullable=False)
    potential_consequences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preventive_action_suggested: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # People involved
    persons_involved: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array or comma-separated
    witnesses_present: Mapped[bool] = mapped_column(Boolean, default=False)
    witness_names: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Asset information
    asset_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    asset_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Risk assessment
    risk_category: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # environmental, safety, equipment, etc.
    potential_severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # low, medium, high, critical

    # Attachments (JSON array of file URLs)
    attachments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Portal form source tracking (for audit traceability)
    source_form_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., portal_near_miss_v1

    # Status workflow
    status: Mapped[str] = mapped_column(String(50), default="REPORTED", nullable=False)
    # REPORTED -> UNDER_REVIEW -> ACTION_REQUIRED -> IN_PROGRESS -> CLOSED

    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)

    # Assignment
    assigned_to_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Resolution
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corrective_actions_taken: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Full-text search (populated by DB trigger)
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)

    __table_args__ = (Index("ix_near_misses_search_vector", "search_vector", postgresql_using="gin"),)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    assigned_to = relationship("User", foreign_keys=[assigned_to_id], lazy="joined")
    created_by = relationship("User", foreign_keys=[created_by_id], lazy="joined")
    updated_by = relationship("User", foreign_keys=[updated_by_id], lazy="joined")
    closed_by = relationship("User", foreign_keys=[closed_by_id], lazy="joined")

    def __repr__(self) -> str:
        return f"<NearMiss(id={self.id}, ref={self.reference_number}, status={self.status})>"
