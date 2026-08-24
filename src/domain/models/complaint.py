"""Complaint models for complaint management."""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import (
    AuditTrailMixin,
    Base,
    CaseInsensitiveEnum,
    DataClassification,
    ReferenceNumberMixin,
    TimestampMixin,
)
from src.domain.models.incident import ActionStatus


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


# One of the three fields the ``severity_levels`` lookup fills, so its members are
# the shared severity set defined by IncidentSeverity (B-9). ``negligible`` was the
# odd one out until then: the dropdown offered it, this enum did not have it, and
# picking it returned 422. The docstring stays one line because FastAPI publishes it
# as the OpenAPI description for the enum.
class ComplaintPriority(str, enum.Enum):
    """Priority of complaint."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


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


class FeedbackKind(str, enum.Enum):
    """What kind of customer feedback this register row is."""

    COMPLAINT = "complaint"
    COMPLIMENT = "compliment"
    SUGGESTION = "suggestion"
    GENERAL = "general"


class FeedbackPolarity(str, enum.Enum):
    """Whether a feedback kind counts for or against satisfaction."""

    NEGATIVE = "negative"
    POSITIVE = "positive"
    NEUTRAL = "neutral"


FEEDBACK_POLARITY: dict[FeedbackKind, FeedbackPolarity] = {
    FeedbackKind.COMPLAINT: FeedbackPolarity.NEGATIVE,
    FeedbackKind.COMPLIMENT: FeedbackPolarity.POSITIVE,
    FeedbackKind.SUGGESTION: FeedbackPolarity.NEUTRAL,
    FeedbackKind.GENERAL: FeedbackPolarity.NEUTRAL,
}


class Complaint(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Complaint model for external complaint management."""

    __tablename__ = "complaints"
    __data_classification__ = DataClassification.C4_RESTRICTED
    __table_args__ = (
        Index("ix_complaints_tenant_status", "tenant_id", "status"),
        Index("ix_complaints_tenant_created", "tenant_id", "created_at"),
        CheckConstraint(
            "source_type IN ('manual', 'email', 'api', 'phone', 'portal', 'in_person')",
            name="ck_complaint_source_type",
        ),
        CheckConstraint(
            "priority IN ('critical', 'high', 'medium', 'low', 'negligible')",
            name="ck_complaints_priority",
        ),
        CheckConstraint(
            "status IN ('received', 'acknowledged', 'under_investigation', "
            "'pending_response', 'awaiting_customer', 'resolved', 'closed', 'escalated')",
            name="ck_complaints_status",
        ),
        CheckConstraint(
            "feedback_kind IN ('complaint', 'compliment', 'suggestion', 'general')",
            name="ck_complaints_feedback_kind",
        ),
        Index("ix_complaints_tenant_kind_received", "tenant_id", "feedback_kind", "received_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Idempotency key for ETL/external systems
    # When provided, enforces uniqueness to prevent duplicate imports
    external_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True, index=True)

    # Complaint identification
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    complaint_type: Mapped[ComplaintType] = mapped_column(
        CaseInsensitiveEnum(ComplaintType), default=ComplaintType.OTHER
    )
    priority: Mapped[ComplaintPriority] = mapped_column(
        CaseInsensitiveEnum(ComplaintPriority), default=ComplaintPriority.MEDIUM
    )
    status: Mapped[ComplaintStatus] = mapped_column(
        CaseInsensitiveEnum(ComplaintStatus), default=ComplaintStatus.RECEIVED, index=True
    )
    # Discriminator for the Customer Feedback register. Existing rows and every
    # create path in PR-1 stay ``complaint``. Keep server_default so rolling
    # deploys and alembic check stay aligned.
    feedback_kind: Mapped[FeedbackKind] = mapped_column(
        CaseInsensitiveEnum(FeedbackKind, length=20),
        default=FeedbackKind.COMPLAINT,
        server_default="complaint",
        nullable=False,
    )

    # Dates
    received_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    target_resolution_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Response SLA (PX-210). All three are nullable: a complaint with no agreed
    # response SLA must read as "none stored" rather than as a met deadline.
    # response_due_at is derived from received_date + response_sla_hours unless a
    # caller supplies an explicit date; first_response_at records when the
    # complainant was actually responded to.
    response_sla_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Complainant details
    complainant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    complainant_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    complainant_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    complainant_company: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    complainant_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Related reference (e.g., order number, invoice number)
    related_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    related_product_service: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Customer / contract (portal + staff intake)
    contract_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Who the complaint is about (staff user and/or free-text name)
    subject_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    subject_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Alleged event datetime (distinct from when the complaint was received)
    alleged_event_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Structured witnesses (mirrors RTA/Incident.witnesses_structured):
    # [{ name, phone, email, statement, willing_to_provide_statement }]
    witnesses_structured: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

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
    source_type: Mapped[str] = mapped_column(String(50), default="manual")  # manual, email, api, phone, portal
    source_email_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    original_email_subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    original_email_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Portal form source tracking (for audit traceability)
    source_form_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., portal_complaint_v1
    reporter_submission: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # Immutable snapshot of reporter-entered intake data

    # GDPR Art. 18 — restriction of processing
    processing_restricted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    # Closure
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    closure_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lessons_learnt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Soft delete (PX-177) — EvidenceAsset-style; list/get exclude deleted rows.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    actions: Mapped[List["ComplaintAction"]] = relationship(
        "ComplaintAction",
        back_populates="complaint",
        cascade="all, delete-orphan",
    )

    @property
    def is_deleted(self) -> bool:
        """True when this complaint has been soft-deleted."""
        return self.deleted_at is not None

    @property
    def feedback_polarity(self) -> FeedbackPolarity:
        """Derived polarity. Never stored — kind is the single source of truth."""
        try:
            return FEEDBACK_POLARITY[self.feedback_kind]
        except KeyError as exc:
            raise ValueError(f"Unmapped feedback_kind {self.feedback_kind!r}") from exc

    def __repr__(self) -> str:
        return (
            f"<Complaint(id={self.id}, ref='{self.reference_number}', "
            f"kind='{self.feedback_kind}', type='{self.complaint_type}')>"
        )


def is_complaint_kind():
    """SQL filter: rows that count as ISO 10002 complaints, not compliments."""
    return Complaint.feedback_kind == FeedbackKind.COMPLAINT


class ComplaintAction(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Action model for complaint follow-up actions."""

    __tablename__ = "complaint_actions"

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    complaint_id: Mapped[int] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Action details
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), default="corrective")
    priority: Mapped[str] = mapped_column(String(20), default="medium")

    # Assignment
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Status and dates
    status: Mapped[ActionStatus] = mapped_column(CaseInsensitiveEnum(ActionStatus), default=ActionStatus.OPEN)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Evidence
    completion_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Soft delete (PX-177)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    complaint: Mapped["Complaint"] = relationship("Complaint", back_populates="actions")

    @property
    def is_deleted(self) -> bool:
        """True when this action has been soft-deleted."""
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return f"<ComplaintAction(id={self.id}, ref='{self.reference_number}', status='{self.status}')>"


class ComplaintRunningSheetEntry(Base, TimestampMixin):
    """Timestamped runner-sheet entry for a complaint."""

    __tablename__ = "complaint_running_sheet_entries"
    __data_classification__ = DataClassification.C4_RESTRICTED
    __table_args__ = (Index("ix_cmp_run_sheet_tenant_complaint", "tenant_id", "complaint_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    complaint_id: Mapped[int] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False, default="note")
    author_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    author_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
