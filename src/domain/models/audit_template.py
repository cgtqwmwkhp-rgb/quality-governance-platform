"""
Audit Template Models - Enterprise-grade audit tool builder
Supports templates, sections, questions, conditional logic, and scoring
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import JSON, Boolean, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.infrastructure.database import Base

# ============================================================================
# ENUMS
# ============================================================================


class QuestionType(str, Enum):
    """Supported question types for audit templates"""

    YES_NO = "yes_no"
    YES_NO_NA = "yes_no_na"
    PASS_FAIL = "pass_fail"
    SCALE_1_5 = "scale_1_5"
    SCALE_1_10 = "scale_1_10"
    MULTI_CHOICE = "multi_choice"
    CHECKLIST = "checklist"
    TEXT_SHORT = "text_short"
    TEXT_LONG = "text_long"
    NUMERIC = "numeric"
    DATE = "date"
    PHOTO = "photo"
    SIGNATURE = "signature"


class TemplateStatus(str, Enum):
    """Template lifecycle status"""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class TemplateCategory(str, Enum):
    """Categories for organizing templates"""

    QUALITY = "quality"
    SAFETY = "safety"
    ENVIRONMENT = "environment"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"
    CUSTOM = "custom"


class ScoringMethod(str, Enum):
    """Methods for calculating audit scores"""

    WEIGHTED = "weighted"
    EQUAL = "equal"
    PASS_FAIL = "pass_fail"
    POINTS = "points"


class RiskLevel(str, Enum):
    """Risk levels for questions"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConditionalOperator(str, Enum):
    """Operators for conditional logic"""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"


# ============================================================================
# MODELS
# ============================================================================


def generate_uuid():
    return str(uuid.uuid4())


class AuditTemplate(Base):
    """
    Master template for audits.
    Contains metadata, settings, and references to sections.
    """

    __tablename__ = "audit_templates"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    # Basic Info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(20), nullable=False, default="1.0.0")
    status: TemplateStatus = Column(SQLEnum(TemplateStatus), nullable=False, default=TemplateStatus.DRAFT)  # type: ignore[assignment]
    category: TemplateCategory = Column(SQLEnum(TemplateCategory), nullable=False, default=TemplateCategory.QUALITY)  # type: ignore[assignment]
    subcategory = Column(String(100), nullable=True)

    # ISO Standards (stored as JSON array)
    iso_standards = Column(JSON, nullable=True, default=list)

    # Scoring Configuration
    scoring_method: ScoringMethod = Column(SQLEnum(ScoringMethod), nullable=False, default=ScoringMethod.WEIGHTED)  # type: ignore[assignment]
    pass_threshold = Column(Float, nullable=False, default=80.0)

    # Metadata
    estimated_duration = Column(Integer, nullable=True, default=60)  # minutes
    tags = Column(JSON, nullable=True, default=list)
    is_locked = Column(Boolean, default=False)
    is_global = Column(Boolean, default=False)  # Available to all users

    # Ownership
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    organization_id = Column(String(36), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

    # Relationships
    sections = relationship(
        "AuditTemplateSection",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="AuditTemplateSection.order",
    )
    versions = relationship("AuditTemplateVersion", back_populates="template", cascade="all, delete-orphan")
    audit_runs = relationship("AuditRun", back_populates="template")

    @property
    def question_count(self) -> int:
        """Total number of questions across all sections"""
        return sum(len(section.questions) for section in self.sections)

    @property
    def section_count(self) -> int:
        """Number of sections in the template"""
        return len(self.sections)


class AuditTemplateSection(Base):
    """
    A section within an audit template.
    Groups related questions together.
    """

    __tablename__ = "audit_template_sections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    template_id = Column(String(36), ForeignKey("audit_templates.id"), nullable=False)

    # Section Info
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)
    color = Column(String(100), nullable=True)  # Gradient class or color code

    # Ordering & Weighting
    order = Column(Integer, nullable=False, default=0)
    weight = Column(Float, nullable=False, default=1.0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    template = relationship("AuditTemplate", back_populates="sections")
    questions = relationship(
        "AuditTemplateQuestion",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="AuditTemplateQuestion.order",
    )


class AuditTemplateQuestion(Base):
    """
    Individual question within a section.
    Supports various question types, scoring, and conditional logic.
    """

    __tablename__ = "audit_template_questions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    section_id = Column(String(36), ForeignKey("audit_template_sections.id"), nullable=False)

    # Question Content
    text = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    guidance = Column(Text, nullable=True)  # Auditor guidance

    # Question Type & Settings
    question_type: QuestionType = Column(SQLEnum(QuestionType), nullable=False, default=QuestionType.YES_NO)  # type: ignore[assignment]
    required = Column(Boolean, default=True)

    # Scoring
    weight = Column(Float, nullable=False, default=1.0)
    risk_level: Optional[RiskLevel] = Column(SQLEnum(RiskLevel), nullable=True)  # type: ignore[assignment]
    failure_triggers_action = Column(Boolean, default=False)

    # Evidence Requirements
    evidence_required = Column(Boolean, default=False)
    evidence_type = Column(String(50), nullable=True)  # photo, document, signature, any

    # ISO Mapping
    iso_clause = Column(String(50), nullable=True)

    # Options (for multi_choice/checklist)
    options = Column(JSON, nullable=True, default=list)  # [{id, label, value, score, isCorrect}]

    # Conditional Logic
    conditional_logic = Column(JSON, nullable=True)  # {enabled, showWhen, dependsOnQuestionId, value}

    # Tags
    tags = Column(JSON, nullable=True, default=list)

    # Ordering
    order = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    section = relationship("AuditTemplateSection", back_populates="questions")


class AuditTemplateVersion(Base):
    """
    Version history for templates.
    Stores snapshots of templates at specific versions.
    """

    __tablename__ = "audit_template_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    template_id = Column(String(36), ForeignKey("audit_templates.id"), nullable=False)

    # Version Info
    version = Column(String(20), nullable=False)
    change_summary = Column(Text, nullable=True)

    # Snapshot (JSON representation of entire template)
    snapshot = Column(JSON, nullable=False)

    # Metadata
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    template = relationship("AuditTemplate", back_populates="versions")


class AuditRun(Base):
    """
    An instance of an audit being executed.
    Links to a template and stores responses.
    """

    __tablename__ = "audit_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    template_id = Column(String(36), ForeignKey("audit_templates.id"), nullable=False)

    # Reference
    reference_number = Column(String(50), unique=True, nullable=False)
    title = Column(String(255), nullable=True)

    # Context
    location = Column(String(255), nullable=True)
    asset_id = Column(String(100), nullable=True)
    asset_name = Column(String(255), nullable=True)

    # Status
    status = Column(
        String(50), nullable=False, default="scheduled"
    )  # scheduled, in_progress, pending_review, completed

    # Scheduling
    scheduled_date = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Scoring
    score_percentage = Column(Float, nullable=True)
    total_questions = Column(Integer, nullable=True)
    answered_questions = Column(Integer, nullable=True)
    passed_questions = Column(Integer, nullable=True)
    failed_questions = Column(Integer, nullable=True)

    # Assignment
    auditor_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Metadata
    duration_seconds = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    template = relationship("AuditTemplate", back_populates="audit_runs")
    responses = relationship("AuditResponse", back_populates="audit_run", cascade="all, delete-orphan")
    findings = relationship("AuditFinding", back_populates="audit_run", cascade="all, delete-orphan")


class AuditResponse(Base):
    """
    Response to an individual question during an audit.
    """

    __tablename__ = "audit_responses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    audit_run_id = Column(String(36), ForeignKey("audit_runs.id"), nullable=False)
    question_id = Column(String(36), ForeignKey("audit_template_questions.id"), nullable=False)

    # Response
    response = Column(JSON, nullable=True)  # Flexible to store any response type
    notes = Column(Text, nullable=True)

    # Evidence
    photos = Column(JSON, nullable=True, default=list)  # Array of photo URLs
    signature = Column(Text, nullable=True)  # Base64 signature
    documents = Column(JSON, nullable=True, default=list)  # Array of document URLs

    # Scoring
    score = Column(Float, nullable=True)
    is_passed = Column(Boolean, nullable=True)

    # Flags
    flagged = Column(Boolean, default=False)
    flagged_reason = Column(Text, nullable=True)

    # Metadata
    duration_seconds = Column(Integer, nullable=True)  # Time spent on question

    # Timestamps
    answered_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    audit_run = relationship("AuditRun", back_populates="responses")


class AuditFinding(Base):
    """
    A finding (non-conformance, observation, etc.) from an audit.
    """

    __tablename__ = "audit_findings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    audit_run_id = Column(String(36), ForeignKey("audit_runs.id"), nullable=False)
    question_id = Column(String(36), ForeignKey("audit_template_questions.id"), nullable=True)

    # Reference
    reference_number = Column(String(50), unique=True, nullable=False)

    # Finding Details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(50), nullable=False)  # critical, high, medium, low, observation

    # Status
    status = Column(
        String(50), nullable=False, default="open"
    )  # open, in_progress, pending_verification, closed, deferred

    # Corrective Action
    corrective_action = Column(Text, nullable=True)
    corrective_action_due_date = Column(DateTime, nullable=True)
    corrective_action_completed_date = Column(DateTime, nullable=True)

    # Assignment
    assigned_to_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Evidence
    evidence = Column(JSON, nullable=True, default=list)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    audit_run = relationship("AuditRun", back_populates="findings")
