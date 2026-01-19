"""
Compliance Automation Models

Supports:
- Regulatory change monitoring
- Gap analysis
- Certificate expiry tracking
- Scheduled audits
- Compliance scoring
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


class RegulatorySource(str, Enum):
    """Source of regulatory updates"""

    HSE_UK = "hse_uk"
    ISO = "iso"
    EA_UK = "ea_uk"  # Environment Agency
    ICO = "ico"  # Information Commissioner
    CUSTOM = "custom"


class ChangeImpact(str, Enum):
    """Impact level of regulatory changes"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class CertificateType(str, Enum):
    """Types of certificates to track"""

    TRAINING = "training"
    EQUIPMENT = "equipment"
    COMPETENCY = "competency"
    LICENSE = "license"
    ACCREDITATION = "accreditation"
    CALIBRATION = "calibration"


class RegulatoryUpdate(Base):
    """Tracked regulatory/standard updates"""

    __tablename__ = "regulatory_updates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Source info
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Update details
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Impact assessment
    impact: Mapped[str] = mapped_column(String(20), default="medium")
    affected_standards: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    affected_clauses: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Dates
    published_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Status
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Actions
    requires_action: Mapped[bool] = mapped_column(Boolean, default=False)
    action_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<RegulatoryUpdate(source={self.source}, title={self.title[:50]})>"


class GapAnalysis(Base):
    """Gap analysis results from regulatory changes"""

    __tablename__ = "gap_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Reference
    regulatory_update_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("regulatory_updates.id"), nullable=True, index=True
    )
    standard_id: Mapped[Optional[int]] = mapped_column(ForeignKey("standards.id"), nullable=True, index=True)

    # Analysis info
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Gap details
    gaps: Mapped[dict] = mapped_column(JSON, nullable=False)
    total_gaps: Mapped[int] = mapped_column(Integer, default=0)
    critical_gaps: Mapped[int] = mapped_column(Integer, default=0)
    high_gaps: Mapped[int] = mapped_column(Integer, default=0)

    # Recommendations
    recommendations: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    estimated_effort_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="pending")
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<GapAnalysis(id={self.id}, title={self.title})>"


class Certificate(Base):
    """Certificate/expiry tracking"""

    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Certificate info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    certificate_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Associated entity
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # user, equipment, location
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Issuer
    issuing_body: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Dates
    issue_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expiry_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Reminders
    reminder_days: Mapped[int] = mapped_column(Integer, default=30)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="valid")
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)

    # Attachments
    document_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Certificate(name={self.name}, expiry={self.expiry_date})>"


class ScheduledAudit(Base):
    """Scheduled/recurring audits"""

    __tablename__ = "scheduled_audits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Audit info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audit_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Template reference
    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("audit_templates.id"), nullable=True)

    # Schedule
    frequency: Mapped[str] = mapped_column(String(50), nullable=False)  # weekly, monthly, quarterly, annual
    schedule_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    next_due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    last_completed_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Assignment
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Standard association
    standard_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Reminders
    reminder_days_before: Mapped[int] = mapped_column(Integer, default=7)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<ScheduledAudit(name={self.name}, next={self.next_due_date})>"


class ComplianceScore(Base):
    """Historical compliance score tracking"""

    __tablename__ = "compliance_scores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Scope
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)  # organization, department, standard
    scope_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    scope_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Score
    score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, default=100.0)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)

    # Breakdown
    breakdown: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Period
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Comparison
    previous_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Timestamp
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ComplianceScore(scope={self.scope_type}, score={self.percentage}%)>"


class RIDDORSubmission(Base):
    """RIDDOR submission tracking"""

    __tablename__ = "riddor_submissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Incident reference
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), nullable=False, index=True)

    # RIDDOR details
    riddor_type: Mapped[str] = mapped_column(String(100), nullable=False)
    hse_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Submission
    submission_status: Mapped[str] = mapped_column(String(50), default="pending")
    submission_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    submitted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Response
    hse_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    hse_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Deadline
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_overdue: Mapped[bool] = mapped_column(Boolean, default=False)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<RIDDORSubmission(incident={self.incident_id}, status={self.submission_status})>"
