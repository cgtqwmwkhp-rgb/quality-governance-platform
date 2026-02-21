"""Auditor Competence Management Models.

Provides tracking for:
- Auditor qualifications and certifications
- Competency assessments
- Training records
- Skill-based audit assignment
"""

import enum
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, TimestampMixin
from src.infrastructure.database import Base


class CompetenceLevel(str, enum.Enum):
    """Competence levels for auditors."""

    TRAINEE = "trainee"
    AUDITOR = "auditor"
    LEAD_AUDITOR = "lead_auditor"
    PRINCIPAL_AUDITOR = "principal_auditor"
    EXPERT = "expert"


class CertificationStatus(str, enum.Enum):
    """Status of a certification."""

    ACTIVE = "active"
    EXPIRED = "expired"
    PENDING_RENEWAL = "pending_renewal"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class AuditorProfile(Base, TimestampMixin, AuditTrailMixin):
    """Auditor profile with competence tracking."""

    __tablename__ = "auditor_profiles"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Professional details
    employee_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Overall competence level
    competence_level: Mapped[CompetenceLevel] = mapped_column(
        SQLEnum(CompetenceLevel, native_enum=False), default=CompetenceLevel.TRAINEE
    )

    # Experience
    years_audit_experience: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_audits_conducted: Mapped[int] = mapped_column(Integer, default=0)
    total_audits_as_lead: Mapped[int] = mapped_column(Integer, default=0)

    # Specializations (JSON array)
    specializations: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # ["ISO 9001", "ISO 14001", "Safety"]

    # Industries/sectors with experience
    industry_experience: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Languages
    languages: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True
    )  # [{"language": "English", "level": "native"}]

    # Availability
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    availability_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Last assessment
    last_competence_assessment: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_assessment_due: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Overall competence score (0-100)
    competence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Active status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    certifications: Mapped[List["AuditorCertification"]] = relationship(
        "AuditorCertification", back_populates="profile", cascade="all, delete-orphan"
    )
    training_records: Mapped[List["AuditorTraining"]] = relationship(
        "AuditorTraining", back_populates="profile", cascade="all, delete-orphan"
    )
    competencies: Mapped[List["AuditorCompetency"]] = relationship(
        "AuditorCompetency", back_populates="profile", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AuditorProfile(id={self.id}, user_id={self.user_id}, level={self.competence_level})>"


class AuditorCertification(Base, TimestampMixin):
    """Auditor certification/qualification record."""

    __tablename__ = "auditor_certifications"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("auditor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Certification details
    certification_name: Mapped[str] = mapped_column(String(200), nullable=False)
    certification_body: Mapped[str] = mapped_column(String(200), nullable=False)
    certification_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Standard/framework covered
    standard_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # ISO 9001, ISO 14001, etc.

    # Level
    certification_level: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # Internal Auditor, Lead Auditor

    # Dates
    issued_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Status
    status: Mapped[CertificationStatus] = mapped_column(
        SQLEnum(CertificationStatus, native_enum=False),
        default=CertificationStatus.ACTIVE,
    )

    # CPD/CPE requirements
    cpd_hours_required: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cpd_hours_completed: Mapped[int] = mapped_column(Integer, default=0)

    # Evidence
    certificate_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    verification_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    profile: Mapped["AuditorProfile"] = relationship("AuditorProfile", back_populates="certifications")

    def __repr__(self) -> str:
        return f"<AuditorCertification(id={self.id}, name={self.certification_name}, status={self.status})>"

    @property
    def is_valid(self) -> bool:
        """Check if certification is currently valid."""
        if self.status != CertificationStatus.ACTIVE:
            return False
        if self.expiry_date and self.expiry_date < datetime.now(timezone.utc):
            return False
        return True

    @property
    def days_until_expiry(self) -> Optional[int]:
        """Get days until expiry."""
        if not self.expiry_date:
            return None
        delta = self.expiry_date - datetime.now(timezone.utc)
        return delta.days


class AuditorTraining(Base, TimestampMixin):
    """Training record for an auditor."""

    __tablename__ = "auditor_training"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("auditor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Training details
    training_name: Mapped[str] = mapped_column(String(200), nullable=False)
    training_provider: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    training_type: Mapped[str] = mapped_column(String(50), default="course")  # course, workshop, webinar, on_the_job

    # Topic/area
    topic: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    standard_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Dates
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Duration
    duration_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpd_hours_earned: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Completion
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completion_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Assessment
    assessment_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    assessment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Certificate
    certificate_issued: Mapped[bool] = mapped_column(Boolean, default=False)
    certificate_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    profile: Mapped["AuditorProfile"] = relationship("AuditorProfile", back_populates="training_records")

    def __repr__(self) -> str:
        return f"<AuditorTraining(id={self.id}, name={self.training_name}, completed={self.completed})>"


class CompetencyArea(Base, TimestampMixin):
    """Definition of a competency area that can be assessed."""

    __tablename__ = "competency_areas"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Area identification
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Category
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # technical, behavioral, industry

    # Applicable standards
    applicable_standards: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # ["ISO 9001", "ISO 14001"]

    # Proficiency levels and descriptions
    # JSON: {"1": "Basic awareness", "2": "Can perform with supervision", ...}
    proficiency_scale: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Required level for different auditor levels
    # JSON: {"trainee": 1, "auditor": 2, "lead_auditor": 3, "principal": 4, "expert": 5}
    required_levels: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Weight in overall competence calculation
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    # Assessment criteria (JSON)
    assessment_criteria: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<CompetencyArea(id={self.id}, code={self.code}, category={self.category})>"


class AuditorCompetency(Base, TimestampMixin):
    """Individual auditor's competency in a specific area."""

    __tablename__ = "auditor_competencies"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("auditor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    competency_area_id: Mapped[int] = mapped_column(
        ForeignKey("competency_areas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Current proficiency level (typically 1-5)
    current_level: Mapped[int] = mapped_column(Integer, nullable=False)
    target_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Evidence of competency
    evidence_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_links: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Assessment history
    last_assessed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assessed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    assessment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # self, peer, supervisor, exam

    # Development plan
    development_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    development_actions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Gap analysis
    has_gap: Mapped[bool] = mapped_column(Boolean, default=False)
    gap_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    profile: Mapped["AuditorProfile"] = relationship("AuditorProfile", back_populates="competencies")

    def __repr__(self) -> str:
        return f"<AuditorCompetency(id={self.id}, profile={self.profile_id}, level={self.current_level})>"


class AuditAssignmentCriteria(Base, TimestampMixin):
    """Criteria for assigning auditors to specific audit types."""

    __tablename__ = "audit_assignment_criteria"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # What this criteria applies to
    audit_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # ISO 9001 audit, Safety audit, etc.

    # Required certifications (JSON array)
    required_certifications: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Required competency levels (JSON: {competency_area_code: min_level})
    required_competencies: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Minimum auditor level
    minimum_auditor_level: Mapped[CompetenceLevel] = mapped_column(
        SQLEnum(CompetenceLevel, native_enum=False), default=CompetenceLevel.AUDITOR
    )

    # Experience requirements
    minimum_audits_conducted: Mapped[int] = mapped_column(Integer, default=0)
    minimum_years_experience: Mapped[float] = mapped_column(Float, default=0)

    # Industry/sector requirements
    required_industry_experience: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Additional requirements
    additional_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<AuditAssignmentCriteria(id={self.id}, audit_type={self.audit_type})>"
