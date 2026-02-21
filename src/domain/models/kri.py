"""Key Risk Indicator (KRI) Models.

Provides KRI tracking, thresholds, alerts, and trending for
enterprise risk management.
"""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, TimestampMixin
from src.infrastructure.database import Base


class KRICategory(str, enum.Enum):
    """Category of Key Risk Indicator."""

    SAFETY = "safety"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    REPUTATIONAL = "reputational"
    STRATEGIC = "strategic"
    ENVIRONMENTAL = "environmental"


class KRITrendDirection(str, enum.Enum):
    """Trend direction for KRI."""

    IMPROVING = "improving"
    STABLE = "stable"
    DETERIORATING = "deteriorating"


class ThresholdStatus(str, enum.Enum):
    """Status based on threshold comparison."""

    GREEN = "green"  # Within acceptable range
    AMBER = "amber"  # Warning level
    RED = "red"  # Breach level


class KeyRiskIndicator(Base, TimestampMixin, AuditTrailMixin):
    """Key Risk Indicator definition and tracking."""

    __tablename__ = "key_risk_indicators"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=False, index=True
    )

    # KRI identification
    code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[KRICategory] = mapped_column(
        SQLEnum(KRICategory, native_enum=False), nullable=False
    )

    # Measurement
    unit: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g., "count", "percentage", "days"
    measurement_frequency: Mapped[str] = mapped_column(
        String(50), default="monthly"
    )  # daily, weekly, monthly, quarterly

    # Data source
    data_source: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g., "incident_count", "audit_findings"
    calculation_method: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Description or formula
    auto_calculate: Mapped[bool] = mapped_column(Boolean, default=True)

    # Thresholds (lower_is_better = True means lower values are good)
    lower_is_better: Mapped[bool] = mapped_column(Boolean, default=True)
    green_threshold: Mapped[float] = mapped_column(
        Float, nullable=False
    )  # Acceptable limit
    amber_threshold: Mapped[float] = mapped_column(
        Float, nullable=False
    )  # Warning limit
    red_threshold: Mapped[float] = mapped_column(
        Float, nullable=False
    )  # Critical limit

    # Current state
    current_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_status: Mapped[Optional[ThresholdStatus]] = mapped_column(
        SQLEnum(ThresholdStatus, native_enum=False), nullable=True
    )
    last_updated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trend_direction: Mapped[Optional[KRITrendDirection]] = mapped_column(
        SQLEnum(KRITrendDirection, native_enum=False), nullable=True
    )

    # Linked risks
    linked_risk_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Ownership
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    measurements: Mapped[List["KRIMeasurement"]] = relationship(
        "KRIMeasurement",
        back_populates="kri",
        cascade="all, delete-orphan",
        order_by="desc(KRIMeasurement.measurement_date)",
    )
    alerts: Mapped[List["KRIAlert"]] = relationship(
        "KRIAlert", back_populates="kri", cascade="all, delete-orphan"
    )

    def calculate_status(self, value: float) -> ThresholdStatus:
        """Calculate status based on value and thresholds."""
        if self.lower_is_better:
            if value <= self.green_threshold:
                return ThresholdStatus.GREEN
            elif value <= self.amber_threshold:
                return ThresholdStatus.AMBER
            else:
                return ThresholdStatus.RED
        else:
            if value >= self.green_threshold:
                return ThresholdStatus.GREEN
            elif value >= self.amber_threshold:
                return ThresholdStatus.AMBER
            else:
                return ThresholdStatus.RED

    def __repr__(self) -> str:
        return f"<KeyRiskIndicator(id={self.id}, code='{self.code}', status={self.current_status})>"


class KRIMeasurement(Base, TimestampMixin):
    """Historical measurements for KRI trending."""

    __tablename__ = "kri_measurements"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kri_id: Mapped[int] = mapped_column(
        ForeignKey("key_risk_indicators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Measurement
    measurement_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[ThresholdStatus] = mapped_column(
        SQLEnum(ThresholdStatus, native_enum=False), nullable=False
    )

    # Period
    period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source reference
    source_data: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # Raw data used for calculation

    # Relationships
    kri: Mapped["KeyRiskIndicator"] = relationship(
        "KeyRiskIndicator", back_populates="measurements"
    )

    def __repr__(self) -> str:
        return (
            f"<KRIMeasurement(id={self.id}, kri_id={self.kri_id}, value={self.value})>"
        )


class KRIAlert(Base, TimestampMixin):
    """Alerts generated when KRI thresholds are breached."""

    __tablename__ = "kri_alerts"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=False, index=True
    )
    kri_id: Mapped[int] = mapped_column(
        ForeignKey("key_risk_indicators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Alert details
    alert_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # threshold_breach, trend_warning
    severity: Mapped[ThresholdStatus] = mapped_column(
        SQLEnum(ThresholdStatus, native_enum=False), nullable=False
    )

    # Trigger
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    trigger_value: Mapped[float] = mapped_column(Float, nullable=False)
    previous_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threshold_breached: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Message
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Status
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    acknowledgment_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Resolution
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    kri: Mapped["KeyRiskIndicator"] = relationship(
        "KeyRiskIndicator", back_populates="alerts"
    )

    def __repr__(self) -> str:
        return (
            f"<KRIAlert(id={self.id}, kri_id={self.kri_id}, severity={self.severity})>"
        )


class RiskScoreHistory(Base, TimestampMixin):
    """Track risk score changes over time for trending."""

    __tablename__ = "risk_score_history"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_id: Mapped[int] = mapped_column(
        ForeignKey("risks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Score at this point
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    likelihood: Mapped[int] = mapped_column(Integer, nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False)

    # What triggered this update
    trigger_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # manual, incident, near_miss, audit_finding
    trigger_entity_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    trigger_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Change details
    previous_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_change: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<RiskScoreHistory(id={self.id}, risk_id={self.risk_id}, score={self.risk_score})>"
