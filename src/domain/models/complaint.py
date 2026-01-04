"""Complaint models for complaint management."""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, ReferenceNumberMixin, TimestampMixin
from src.domain.models.incident import ActionStatus
from src.infrastructure.database import Base


class ComplaintType(str, enum.Enum):
    """Type of complaint."""

    PRODUCT = "product"
    SERVICE = "service"
    DELIVERY = "delivery"
    COMMUNICATION = "communication"
    BILLING = "billing"
    STAFF = "staff"
    ENVIRONMENTAL = "environmental"
    SAFETY = "safety"
    OTHER = "other"


class ComplaintPriority(str, enum.Enum):
    """Priority of complaint."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ComplaintStatus(str, enum.Enum):
    """Status of complaint."""

    RECEIVED = "received"
    ACKNOWLEDGED = "acknowledged"
    UNDER_INVESTIGATION = "under_investigation"
    PENDING_RESPONSE = "pending_response"
    AWAITING_CUSTOMER = "awaiting_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


class Complaint(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Complaint model for external complaint management."""

    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Complaint identification
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    complaint_type: Mapped[ComplaintType] = mapped_column(SQLEnum(ComplaintType), default=ComplaintType.OTHER)
    priority: Mapped[ComplaintPriority] = mapped_column(SQLEnum(ComplaintPriority), default=ComplaintPriority.MEDIUM)
    status: Mapped[ComplaintStatus] = mapped_column(SQLEnum(ComplaintStatus), default=ComplaintStatus.RECEIVED)

    # Dates
    received_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    target_resolution_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Complainant details
    complainant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    complainant_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    complainant_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    complainant_company: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    complainant_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Related reference (e.g., order number, invoice number)
    related_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    related_product_service: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Assignment
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Investigation
    investigation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Resolution
    resolution_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    customer_satisfied: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    compensation_offered: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Standard mapping
    clause_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Risk linkage
    linked_risk_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Email ingestion source
    source_type: Mapped[str] = mapped_column(String(50), default="manual")  # manual, email, api, phone
    source_email_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    original_email_subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    original_email_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Closure
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    closure_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    actions: Mapped[List["ComplaintAction"]] = relationship(
        "ComplaintAction",
        back_populates="complaint",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Complaint(id={self.id}, ref='{self.reference_number}', type='{self.complaint_type}')>"


class ComplaintAction(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Action model for complaint follow-up actions."""

    __tablename__ = "complaint_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False)

    # Action details
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), default="corrective")
    priority: Mapped[str] = mapped_column(String(20), default="medium")

    # Assignment
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Status and dates
    status: Mapped[ActionStatus] = mapped_column(SQLEnum(ActionStatus), default=ActionStatus.OPEN)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Evidence
    completion_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    complaint: Mapped["Complaint"] = relationship("Complaint", back_populates="actions")

    def __repr__(self) -> str:
        return f"<ComplaintAction(id={self.id}, ref='{self.reference_number}', status='{self.status}')>"
