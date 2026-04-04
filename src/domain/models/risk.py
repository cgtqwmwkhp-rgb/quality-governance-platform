"""Risk models for risk register and controls."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import (
    AuditTrailMixin,
    CaseInsensitiveEnum,
    DataClassification,
    ReferenceNumberMixin,
    TimestampMixin,
)
from src.domain.models.enums import RiskStatus
from src.infrastructure.database import Base


class Risk(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Risk model for the risk register."""

    __tablename__ = "risks"
    __data_classification__ = DataClassification.C3_CONFIDENTIAL
    __table_args__ = (
        CheckConstraint("likelihood BETWEEN 1 AND 5", name="ck_risks_likelihood_range"),
        CheckConstraint("impact BETWEEN 1 AND 5", name="ck_risks_impact_range"),
        CheckConstraint("risk_score BETWEEN 1 AND 25", name="ck_risks_risk_score_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Risk identification
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="operational")
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Risk details
    risk_source: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    risk_event: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    risk_consequence: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Current risk assessment
    likelihood: Mapped[int] = mapped_column(Integer, default=3)  # 1-5 scale
    impact: Mapped[int] = mapped_column(Integer, default=3)  # 1-5 scale
    risk_score: Mapped[int] = mapped_column(Integer, default=9)  # likelihood * impact
    risk_level: Mapped[str] = mapped_column(String(50), default="medium")

    # Risk ownership
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Review cycle
    review_frequency_months: Mapped[int] = mapped_column(Integer, default=12)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Standard mapping (JSON arrays) — renamed to _legacy by
    # 20260220_normalize_json_to_junction_tables migration.
    clause_ids_json_legacy: Mapped[Optional[list]] = mapped_column("clause_ids_json_legacy", JSON, nullable=True)
    control_ids_json_legacy: Mapped[Optional[list]] = mapped_column("control_ids_json_legacy", JSON, nullable=True)

    # Linkages (JSON arrays) — renamed to _legacy by same migration.
    linked_audit_ids_json_legacy: Mapped[Optional[list]] = mapped_column(
        "linked_audit_ids_json_legacy", JSON, nullable=True
    )
    linked_incident_ids_json_legacy: Mapped[Optional[list]] = mapped_column(
        "linked_incident_ids_json_legacy", JSON, nullable=True
    )
    linked_policy_ids_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Treatment
    treatment_strategy: Mapped[str] = mapped_column(String(50), default="mitigate")
    treatment_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treatment_due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Status
    status: Mapped[RiskStatus] = mapped_column(CaseInsensitiveEnum(RiskStatus), default=RiskStatus.OPEN, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Ownership
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    controls: Mapped[List["OperationalRiskControl"]] = relationship(
        "OperationalRiskControl",
        back_populates="risk",
        cascade="all, delete-orphan",
    )
    assessments: Mapped[List["RiskAssessment"]] = relationship(
        "RiskAssessment",
        back_populates="risk",
        cascade="all, delete-orphan",
        order_by="RiskAssessment.assessment_date.desc()",
    )

    def __repr__(self) -> str:
        return f"<Risk(id={self.id}, ref='{self.reference_number}', level='{self.risk_level}')>"


class OperationalRiskControl(Base, TimestampMixin, AuditTrailMixin):
    """Risk control/mitigation model for operational risks."""

    __tablename__ = "risk_controls"

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks.id", ondelete="CASCADE"), nullable=False, index=True)

    # Control details
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    control_type: Mapped[str] = mapped_column(String(50), default="preventive")

    # Status
    implementation_status: Mapped[str] = mapped_column(String(50), default="planned")
    effectiveness: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Ownership
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Standard mapping (JSON arrays)
    clause_ids_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    control_ids_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Testing
    last_tested_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_test_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    test_frequency_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    risk: Mapped["Risk"] = relationship("Risk", back_populates="controls")

    def __repr__(self) -> str:
        return f"<OperationalRiskControl(id={self.id}, title='{self.title[:50]}')>"


class RiskAssessment(Base, TimestampMixin):
    """Risk assessment history model for tracking changes over time."""

    __tablename__ = "risk_assessments"
    __table_args__ = (
        CheckConstraint("inherent_likelihood BETWEEN 1 AND 5", name="ck_risk_assessments_inherent_likelihood_range"),
        CheckConstraint("inherent_impact BETWEEN 1 AND 5", name="ck_risk_assessments_inherent_impact_range"),
    )

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks.id", ondelete="CASCADE"), nullable=False, index=True)

    # Assessment details
    assessment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(50), default="periodic")

    # Inherent risk (before controls)
    inherent_likelihood: Mapped[int] = mapped_column(Integer, nullable=False)
    inherent_impact: Mapped[int] = mapped_column(Integer, nullable=False)
    inherent_score: Mapped[int] = mapped_column(Integer, nullable=False)
    inherent_level: Mapped[str] = mapped_column(String(50), nullable=False)

    # Residual risk (after controls)
    residual_likelihood: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_impact: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_score: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_level: Mapped[str] = mapped_column(String(50), nullable=False)

    # Target risk (desired state)
    target_likelihood: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_impact: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Notes
    assessment_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    control_effectiveness_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Assessor
    assessed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationships
    risk: Mapped["Risk"] = relationship("Risk", back_populates="assessments")

    def __repr__(self) -> str:
        return f"<RiskAssessment(id={self.id}, risk_id={self.risk_id}, date='{self.assessment_date}')>"
