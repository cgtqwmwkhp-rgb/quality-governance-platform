"""
Enterprise Risk Register Models - ISO 31000 Compliant

Features:
- Risk Taxonomy (Strategic, Operational, Financial, Compliance, Reputational)
- 5x5 Risk Matrix (Likelihood × Impact)
- Risk Appetite & Tolerance thresholds
- Control Mapping
- Bow-Tie Analysis
- Key Risk Indicators (KRIs)
- Risk Treatment Plans
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database import Base


class RiskCategory(str, Enum):
    """ISO 31000 compliant risk categories"""

    STRATEGIC = "strategic"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    COMPLIANCE = "compliance"
    REPUTATIONAL = "reputational"
    HEALTH_SAFETY = "health_safety"
    ENVIRONMENTAL = "environmental"
    TECHNOLOGICAL = "technological"
    LEGAL = "legal"
    PROJECT = "project"


class RiskStatus(str, Enum):
    """Risk lifecycle status"""

    IDENTIFIED = "identified"
    ASSESSING = "assessing"
    TREATING = "treating"
    MONITORING = "monitoring"
    CLOSED = "closed"
    ESCALATED = "escalated"


class LikelihoodLevel(str, Enum):
    """5-point likelihood scale"""

    RARE = "rare"  # 1
    UNLIKELY = "unlikely"  # 2
    POSSIBLE = "possible"  # 3
    LIKELY = "likely"  # 4
    ALMOST_CERTAIN = "almost_certain"  # 5


class ImpactLevel(str, Enum):
    """5-point impact scale"""

    INSIGNIFICANT = "insignificant"  # 1
    MINOR = "minor"  # 2
    MODERATE = "moderate"  # 3
    MAJOR = "major"  # 4
    CATASTROPHIC = "catastrophic"  # 5


class RiskAppetite(str, Enum):
    """Risk appetite levels"""

    AVERSE = "averse"  # Avoid risk
    MINIMAL = "minimal"  # Very low tolerance
    CAUTIOUS = "cautious"  # Prefer safe options
    OPEN = "open"  # Willing to consider risk
    HUNGRY = "hungry"  # Seek risk for reward


class TreatmentStrategy(str, Enum):
    """Risk treatment strategies (4T's)"""

    TREAT = "treat"  # Reduce likelihood/impact
    TOLERATE = "tolerate"  # Accept the risk
    TRANSFER = "transfer"  # Insurance, outsourcing
    TERMINATE = "terminate"  # Avoid the activity


class EnterpriseRisk(Base):
    """Main risk entity (Enterprise Risk Register)"""

    __tablename__ = "risks_v2"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Identification
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Taxonomy
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Source & Context
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    affected_objectives: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Organizational placement
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    process: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Inherent Risk (before controls)
    inherent_likelihood: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    inherent_impact: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    inherent_score: Mapped[int] = mapped_column(Integer, nullable=False)  # likelihood × impact

    # Residual Risk (after controls)
    residual_likelihood: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_impact: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_score: Mapped[int] = mapped_column(Integer, nullable=False)

    # Target Risk
    target_likelihood: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_impact: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Risk Appetite
    risk_appetite: Mapped[str] = mapped_column(String(50), default="cautious")
    appetite_threshold: Mapped[int] = mapped_column(Integer, default=12)  # Max acceptable score
    is_within_appetite: Mapped[bool] = mapped_column(Boolean, default=True)

    # Treatment
    treatment_strategy: Mapped[str] = mapped_column(String(50), default="treat")
    treatment_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treatment_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    treatment_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    treatment_benefit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ownership
    risk_owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    risk_owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    delegate_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Review
    status: Mapped[str] = mapped_column(String(50), default="identified", index=True)
    review_frequency_days: Mapped[int] = mapped_column(Integer, default=90)
    last_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Escalation
    is_escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    escalation_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Linked entities
    linked_incidents: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    linked_audits: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    linked_actions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Timestamps
    identified_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<Risk(ref={self.reference}, title={self.title[:30]})>"


class EnterpriseRiskControl(Base):
    """Controls linked to risks (Enterprise Risk Register)"""

    __tablename__ = "enterprise_risk_controls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Control identification
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Control type
    control_type: Mapped[str] = mapped_column(String(50), nullable=False)  # preventive, detective, corrective
    control_nature: Mapped[str] = mapped_column(String(50), nullable=False)  # manual, automated, hybrid

    # Effectiveness
    effectiveness: Mapped[str] = mapped_column(String(50), default="effective")  # effective, partially, ineffective
    effectiveness_score: Mapped[int] = mapped_column(Integer, default=3)  # 1-5

    # Ownership
    control_owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    control_owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Testing
    last_test_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    test_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    next_test_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Linked standards
    standard_clauses: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Evidence
    evidence_required: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    evidence_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    implementation_status: Mapped[str] = mapped_column(String(50), default="implemented")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<EnterpriseRiskControl(ref={self.reference}, name={self.name[:30]})>"


class RiskControlMapping(Base):
    """Many-to-many mapping between risks and controls"""

    __tablename__ = "risk_control_mappings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    control_id: Mapped[int] = mapped_column(
        ForeignKey("enterprise_risk_controls.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Mapping details
    contribution: Mapped[str] = mapped_column(String(50), default="partial")  # full, partial, minimal
    reduces_likelihood: Mapped[bool] = mapped_column(Boolean, default=True)
    reduces_impact: Mapped[bool] = mapped_column(Boolean, default=False)
    reduction_value: Mapped[int] = mapped_column(Integer, default=1)  # How much it reduces score

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BowTieElement(Base):
    """Bow-Tie Analysis elements (causes, consequences, barriers)"""

    __tablename__ = "bow_tie_elements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks_v2.id", ondelete="CASCADE"), nullable=False, index=True)

    # Element type
    element_type: Mapped[str] = mapped_column(String(50), nullable=False)  # cause, consequence, prevention, mitigation
    position: Mapped[str] = mapped_column(String(50), nullable=False)  # left (causes), right (consequences)

    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # For barriers
    barrier_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # hard, soft
    linked_control_id: Mapped[Optional[int]] = mapped_column(ForeignKey("enterprise_risk_controls.id"), nullable=True)
    effectiveness: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Ordering
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    # Escalation factors
    is_escalation_factor: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EnterpriseKeyRiskIndicator(Base):
    """Key Risk Indicators (KRIs) for monitoring (Enterprise)"""

    __tablename__ = "enterprise_key_risk_indicators"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks_v2.id", ondelete="CASCADE"), nullable=False, index=True)

    # KRI definition
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)  # count, percentage, ratio, value

    # Thresholds
    green_threshold: Mapped[float] = mapped_column(Float, nullable=False)  # Good
    amber_threshold: Mapped[float] = mapped_column(Float, nullable=False)  # Warning
    red_threshold: Mapped[float] = mapped_column(Float, nullable=False)  # Critical
    threshold_direction: Mapped[str] = mapped_column(String(20), default="above")  # above, below

    # Current value
    current_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # green, amber, red
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Data source
    data_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    calculation_method: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    update_frequency: Mapped[str] = mapped_column(String(50), default="monthly")

    # Historical values
    historical_values: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Alerting
    alert_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_recipients: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    last_alert_sent: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Ownership
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RiskAssessmentHistory(Base):
    """Historical risk assessment records"""

    __tablename__ = "risk_assessment_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks_v2.id", ondelete="CASCADE"), nullable=False, index=True)

    # Assessment snapshot
    assessment_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    assessed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Scores at time of assessment
    inherent_likelihood: Mapped[int] = mapped_column(Integer, nullable=False)
    inherent_impact: Mapped[int] = mapped_column(Integer, nullable=False)
    inherent_score: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_likelihood: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_impact: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_score: Mapped[int] = mapped_column(Integer, nullable=False)

    # Status at time
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    treatment_strategy: Mapped[str] = mapped_column(String(50), nullable=False)

    # Notes
    assessment_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changes_since_last: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Control effectiveness at time
    control_effectiveness: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class RiskAppetiteStatement(Base):
    """Organizational risk appetite statements by category"""

    __tablename__ = "risk_appetite_statements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Category
    category: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    # Appetite level
    appetite_level: Mapped[str] = mapped_column(String(50), nullable=False)  # averse, minimal, cautious, open, hungry

    # Thresholds
    max_inherent_score: Mapped[int] = mapped_column(Integer, default=25)
    max_residual_score: Mapped[int] = mapped_column(Integer, default=12)
    escalation_threshold: Mapped[int] = mapped_column(Integer, default=16)

    # Statement
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Approval
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
