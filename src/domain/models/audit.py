"""Audit models for templates, runs, and findings."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text, Integer, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from src.infrastructure.database import Base
from src.domain.models.base import TimestampMixin, ReferenceNumberMixin, AuditTrailMixin


class AuditStatus(str, enum.Enum):
    """Status of an audit run."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FindingSeverity(str, enum.Enum):
    """Severity level of an audit finding."""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    OBSERVATION = "observation"
    OPPORTUNITY = "opportunity"


class QuestionType(str, enum.Enum):
    """Type of audit question."""
    CHECKBOX = "checkbox"
    TEXT = "text"
    NUMBER = "number"
    SCORE = "score"
    YES_NO = "yes_no"
    YES_NO_NA = "yes_no_na"
    MULTIPLE_CHOICE = "multiple_choice"
    DATE = "date"
    PHOTO = "photo"
    SIGNATURE = "signature"


class AuditTemplate(Base, TimestampMixin, AuditTrailMixin):
    """Audit template model for defining audit structures."""

    __tablename__ = "audit_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Template settings
    scoring_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    max_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pass_threshold: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    evidence_required: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
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

    def __repr__(self) -> str:
        return f"<AuditTemplate(id={self.id}, name='{self.name}')>"


class AuditQuestion(Base, TimestampMixin):
    """Audit question model for individual questions within a template."""

    __tablename__ = "audit_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("audit_templates.id", ondelete="CASCADE"), nullable=False)
    
    # Question content
    section: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(SQLEnum(QuestionType), default=QuestionType.YES_NO_NA)
    help_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Question settings
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    allows_na: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_evidence: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_comment: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Scoring
    weight: Mapped[int] = mapped_column(Integer, default=1)
    max_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Conditional logic (JSON)
    conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Options for multiple choice (JSON array)
    options: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Ordering
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    
    # Standard mapping
    clause_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Comma-separated clause IDs
    
    # Relationships
    template: Mapped["AuditTemplate"] = relationship("AuditTemplate", back_populates="questions")

    def __repr__(self) -> str:
        return f"<AuditQuestion(id={self.id}, text='{self.question_text[:50]}...')>"


class AuditRun(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Audit run model for actual audit executions."""

    __tablename__ = "audit_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("audit_templates.id"), nullable=False)
    
    # Audit details
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Status and dates
    status: Mapped[AuditStatus] = mapped_column(SQLEnum(AuditStatus), default=AuditStatus.DRAFT)
    scheduled_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Assignment
    auditor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Scoring
    total_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_possible_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pass_status: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    
    # Responses stored as JSON
    responses: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    template: Mapped["AuditTemplate"] = relationship("AuditTemplate", back_populates="runs")
    findings: Mapped[List["AuditFinding"]] = relationship(
        "AuditFinding",
        back_populates="audit_run",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AuditRun(id={self.id}, ref='{self.reference_number}', status='{self.status}')>"


class AuditFinding(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Audit finding model for issues identified during audits."""

    __tablename__ = "audit_findings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    audit_run_id: Mapped[int] = mapped_column(ForeignKey("audit_runs.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[Optional[int]] = mapped_column(ForeignKey("audit_questions.id"), nullable=True)
    
    # Finding details
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(SQLEnum(FindingSeverity), default=FindingSeverity.MINOR)
    
    # Standard mapping
    clause_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Comma-separated clause IDs
    
    # Evidence
    evidence_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Action tracking
    action_required: Mapped[bool] = mapped_column(Boolean, default=True)
    action_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action_due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    action_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    action_status: Mapped[str] = mapped_column(String(50), default="open")  # open, in_progress, completed, verified
    
    # Relationships
    audit_run: Mapped["AuditRun"] = relationship("AuditRun", back_populates="findings")

    def __repr__(self) -> str:
        return f"<AuditFinding(id={self.id}, ref='{self.reference_number}', severity='{self.severity}')>"
