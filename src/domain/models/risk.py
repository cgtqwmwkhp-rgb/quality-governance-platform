"""Risk models for risk register and controls."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text, Integer, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from src.infrastructure.database import Base
from src.domain.models.base import TimestampMixin, ReferenceNumberMixin, AuditTrailMixin


class RiskStatus(str, enum.Enum):
    """Status of a risk."""
    IDENTIFIED = "identified"
    ASSESSING = "assessing"
    TREATING = "treating"
    MONITORING = "monitoring"
    CLOSED = "closed"


class RiskCategory(str, enum.Enum):
    """Category of risk."""
    STRATEGIC = "strategic"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    COMPLIANCE = "compliance"
    REPUTATIONAL = "reputational"
    SAFETY = "safety"
    ENVIRONMENTAL = "environmental"
    INFORMATION_SECURITY = "information_security"
    QUALITY = "quality"


class ControlStatus(str, enum.Enum):
    """Status of a risk control."""
    PLANNED = "planned"
    IMPLEMENTING = "implementing"
    IMPLEMENTED = "implemented"
    EFFECTIVE = "effective"
    INEFFECTIVE = "ineffective"


class Risk(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Risk model for the risk register."""

    __tablename__ = "risks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Risk identification
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[RiskCategory] = mapped_column(SQLEnum(RiskCategory), default=RiskCategory.OPERATIONAL)
    source: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Where was this risk identified
    
    # Risk ownership
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Inherent risk assessment (before controls)
    inherent_likelihood: Mapped[int] = mapped_column(Integer, default=3)  # 1-5 scale
    inherent_impact: Mapped[int] = mapped_column(Integer, default=3)  # 1-5 scale
    
    # Residual risk assessment (after controls)
    residual_likelihood: Mapped[int] = mapped_column(Integer, default=3)  # 1-5 scale
    residual_impact: Mapped[int] = mapped_column(Integer, default=3)  # 1-5 scale
    
    # Target risk (acceptable level)
    target_likelihood: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_impact: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Status and dates
    status: Mapped[RiskStatus] = mapped_column(SQLEnum(RiskStatus), default=RiskStatus.IDENTIFIED)
    identified_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    review_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Standard mapping
    clause_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Comma-separated clause IDs
    
    # Additional metadata
    risk_appetite: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # accept, mitigate, transfer, avoid
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    controls: Mapped[List["RiskControl"]] = relationship(
        "RiskControl",
        back_populates="risk",
        cascade="all, delete-orphan",
    )
    assessments: Mapped[List["RiskAssessment"]] = relationship(
        "RiskAssessment",
        back_populates="risk",
        cascade="all, delete-orphan",
        order_by="RiskAssessment.assessment_date.desc()",
    )

    @property
    def inherent_risk_score(self) -> int:
        """Calculate inherent risk score."""
        return self.inherent_likelihood * self.inherent_impact

    @property
    def residual_risk_score(self) -> int:
        """Calculate residual risk score."""
        return self.residual_likelihood * self.residual_impact

    @property
    def risk_level(self) -> str:
        """Determine risk level based on residual score."""
        score = self.residual_risk_score
        if score >= 20:
            return "critical"
        elif score >= 12:
            return "high"
        elif score >= 6:
            return "medium"
        else:
            return "low"

    def __repr__(self) -> str:
        return f"<Risk(id={self.id}, ref='{self.reference_number}', title='{self.title[:50]}')>"


class RiskControl(Base, TimestampMixin, AuditTrailMixin):
    """Risk control/mitigation model."""

    __tablename__ = "risk_controls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks.id", ondelete="CASCADE"), nullable=False)
    
    # Control details
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    control_type: Mapped[str] = mapped_column(String(50), default="preventive")  # preventive, detective, corrective
    
    # Status and effectiveness
    status: Mapped[ControlStatus] = mapped_column(SQLEnum(ControlStatus), default=ControlStatus.PLANNED)
    effectiveness: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5 scale
    
    # Ownership
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Dates
    implementation_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Standard mapping
    clause_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Evidence
    evidence_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    risk: Mapped["Risk"] = relationship("Risk", back_populates="controls")

    def __repr__(self) -> str:
        return f"<RiskControl(id={self.id}, title='{self.title[:50]}')>"


class RiskAssessment(Base, TimestampMixin, AuditTrailMixin):
    """Risk assessment history model for tracking changes over time."""

    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks.id", ondelete="CASCADE"), nullable=False)
    
    # Assessment details
    assessment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assessor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Scores at time of assessment
    likelihood: Mapped[int] = mapped_column(Integer, nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Notes
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    risk: Mapped["Risk"] = relationship("Risk", back_populates="assessments")

    @property
    def risk_score(self) -> int:
        """Calculate risk score at time of assessment."""
        return self.likelihood * self.impact

    def __repr__(self) -> str:
        return f"<RiskAssessment(id={self.id}, risk_id={self.risk_id}, date='{self.assessment_date}')>"
