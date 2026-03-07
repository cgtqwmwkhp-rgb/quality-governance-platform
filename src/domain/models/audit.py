"""Audit models for templates, runs, and findings."""

import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, CaseInsensitiveEnum, ReferenceNumberMixin, TimestampMixin
from src.infrastructure.database import Base


class AuditStatus(str, enum.Enum):
    """Status of an audit run."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FindingStatus(str, enum.Enum):
    """Status of an audit finding."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_VERIFICATION = "pending_verification"
    CLOSED = "closed"
    DEFERRED = "deferred"


class FindingSeverity(str, enum.Enum):
    """Severity level of an audit finding."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OBSERVATION = "observation"


class TemplateLifecycleStatus(str, enum.Enum):
    """Lifecycle status for template approval workflow."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class QuestionCriticality(str, enum.Enum):
    """Criticality level distinguishing mandatory-pass from scored items."""

    ESSENTIAL = "essential"
    GOOD_TO_HAVE = "good_to_have"


class AuditTemplate(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Audit template model for defining audit structures."""

    __tablename__ = "audit_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # UUID for offline sync and cross-model references
    external_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
    )

    # Template type and configuration
    audit_type: Mapped[str] = mapped_column(String(50), default="inspection")
    frequency: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    estimated_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Version control
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)

    # Template approval workflow lifecycle
    template_status: Mapped[TemplateLifecycleStatus] = mapped_column(
        CaseInsensitiveEnum(TemplateLifecycleStatus),
        default=TemplateLifecycleStatus.PUBLISHED,
    )

    # Scoring configuration
    scoring_method: Mapped[str] = mapped_column(String(50), default="percentage")
    passing_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pass_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Mobile configuration
    allow_offline: Mapped[bool] = mapped_column(Boolean, default=False)
    require_gps: Mapped[bool] = mapped_column(Boolean, default=False)
    require_signature: Mapped[bool] = mapped_column(Boolean, default=False)

    # Workflow configuration
    require_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_create_findings: Mapped[bool] = mapped_column(Boolean, default=True)

    # Standard mapping (JSON array of standard IDs)
    standard_ids_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Ownership
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Archive support
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    sections: Mapped[List["AuditSection"]] = relationship(
        "AuditSection",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="AuditSection.sort_order",
    )
    questions: Mapped[List["AuditQuestion"]] = relationship(
        "AuditQuestion",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="AuditQuestion.sort_order",
    )
    runs: Mapped[List["AuditRun"]] = relationship(
        "AuditRun",
        back_populates="template",
    )
    versions: Mapped[List["TemplateVersion"]] = relationship(
        "TemplateVersion",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateVersion.version_number.desc()",
    )

    def __repr__(self) -> str:
        return f"<AuditTemplate(id={self.id}, name='{self.name}', v{self.version})>"


class AuditSection(Base, TimestampMixin):
    """Audit section model for grouping questions within a template."""

    __tablename__ = "audit_sections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("audit_templates.id", ondelete="CASCADE"), nullable=False)

    # Section details
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Configuration
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    is_repeatable: Mapped[bool] = mapped_column(Boolean, default=False)
    max_repeats: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    template: Mapped["AuditTemplate"] = relationship("AuditTemplate", back_populates="sections")
    questions: Mapped[List["AuditQuestion"]] = relationship(
        "AuditQuestion",
        back_populates="section",
        order_by="AuditQuestion.sort_order",
    )

    def __repr__(self) -> str:
        return f"<AuditSection(id={self.id}, title='{self.title}')>"


class AuditQuestion(Base, TimestampMixin):
    """Audit question model with feature-rich configuration."""

    __tablename__ = "audit_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("audit_templates.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("audit_sections.id", ondelete="SET NULL"), nullable=True
    )

    # Question content
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(50), default="yes_no")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    help_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Question configuration
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_na: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Scoring
    max_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    # Options for MCQ/dropdown/radio (JSON array)
    options_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Numeric constraints
    min_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    decimal_places: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Text constraints
    min_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Evidence requirements (JSON object)
    evidence_requirements_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Conditional logic (JSON array of rules)
    conditional_logic_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Standard mapping (JSON arrays)
    clause_ids_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    control_ids_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Risk scoring
    risk_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    risk_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Workforce Development fields
    guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    criticality: Mapped[Optional[QuestionCriticality]] = mapped_column(
        CaseInsensitiveEnum(QuestionCriticality), nullable=True
    )
    regulatory_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    guidance_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sign_off_required: Mapped[bool] = mapped_column(Boolean, default=False)
    assessor_guidance_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    training_materials_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    failure_triggers_action: Mapped[bool] = mapped_column(Boolean, default=False)

    # Yes/No polarity: which answer is positive (green)? Default "yes".
    positive_answer: Mapped[str] = mapped_column(
        String(10), nullable=False, default="yes", server_default=text("'yes'")
    )

    # Ordering
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    template: Mapped["AuditTemplate"] = relationship("AuditTemplate", back_populates="questions")
    section: Mapped[Optional["AuditSection"]] = relationship("AuditSection", back_populates="questions")

    def __repr__(self) -> str:
        return f"<AuditQuestion(id={self.id}, type='{self.question_type}')>"


class AuditRun(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Audit run model for actual audit executions."""

    __tablename__ = "audit_runs"
    __table_args__ = (
        Index("ix_audit_runs_tenant_status", "tenant_id", "status"),
        Index("ix_audit_runs_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("audit_templates.id"), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, default=1)

    # Audit details
    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    location_details: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # GPS coordinates
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Status and dates
    status: Mapped[AuditStatus] = mapped_column(CaseInsensitiveEnum(AuditStatus), default=AuditStatus.SCHEDULED)
    scheduled_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Assignment
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Scoring
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Relationships
    template: Mapped["AuditTemplate"] = relationship("AuditTemplate", back_populates="runs")
    responses: Mapped[List["AuditResponse"]] = relationship(
        "AuditResponse",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    findings: Mapped[List["AuditFinding"]] = relationship(
        "AuditFinding",
        back_populates="run",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AuditRun(id={self.id}, ref='{self.reference_number}', status='{self.status}')>"


class AuditResponse(Base, TimestampMixin):
    """Audit response model for individual question answers."""

    __tablename__ = "audit_responses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("audit_runs.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("audit_questions.id"), nullable=False)

    # Response values (use appropriate field based on question type)
    response_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_number: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    response_bool: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    response_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    response_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # N/A handling
    is_na: Mapped[bool] = mapped_column(Boolean, default=False)

    # Scoring
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    run: Mapped["AuditRun"] = relationship("AuditRun", back_populates="responses")

    def __repr__(self) -> str:
        return f"<AuditResponse(id={self.id}, run_id={self.run_id}, question_id={self.question_id})>"


class AuditFinding(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Audit finding model for issues identified during audits."""

    __tablename__ = "audit_findings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("audit_runs.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[Optional[int]] = mapped_column(ForeignKey("audit_questions.id"), nullable=True)

    # Finding details
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="medium")
    finding_type: Mapped[str] = mapped_column(String(50), default="nonconformity")
    status: Mapped[FindingStatus] = mapped_column(
        CaseInsensitiveEnum(FindingStatus), default=FindingStatus.OPEN, index=True
    )

    # Standard mapping (JSON arrays)
    # clause_ids_json was renamed to clause_ids_json_legacy by the
    # 20260220_normalize_json_to_junction_tables migration; control_ids_json
    # and risk_ids_json were NOT renamed.
    clause_ids_json_legacy: Mapped[Optional[list]] = mapped_column("clause_ids_json_legacy", JSON, nullable=True)
    control_ids_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Risk linkage (JSON array)
    risk_ids_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Corrective action
    corrective_action_required: Mapped[bool] = mapped_column(Boolean, default=True)
    corrective_action_due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Ownership
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Relationships
    run: Mapped["AuditRun"] = relationship("AuditRun", back_populates="findings")

    def __repr__(self) -> str:
        return f"<AuditFinding(id={self.id}, ref='{self.reference_number}', severity='{self.severity}')>"


class TemplateVersion(Base, TimestampMixin):
    """Snapshot of a template at a specific version for audit trail and rollback."""

    __tablename__ = "template_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("audit_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Relationships
    template: Mapped["AuditTemplate"] = relationship("AuditTemplate", back_populates="versions")

    def __repr__(self) -> str:
        return f"<TemplateVersion(id={self.id}, template_id={self.template_id}, v{self.version_number})>"
