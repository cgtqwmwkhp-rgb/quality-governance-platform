"""Executive Dashboard API Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthScoreComponent(BaseModel):
    """Individual health score component."""

    incidents: float
    near_miss_culture: float
    risk_management: float
    kri_performance: float
    compliance: float
    sla_performance: float


class HealthScore(BaseModel):
    """Overall health score."""

    score: float = Field(..., ge=0, le=100)
    status: str  # healthy, attention_needed, at_risk
    color: str  # green, amber, red
    components: HealthScoreComponent


class IncidentSummary(BaseModel):
    """Incident module summary."""

    total_in_period: int
    open: int
    by_severity: Dict[str, int]
    sif_count: int
    psif_count: int
    critical_high: int


class NearMissSummary(BaseModel):
    """Near-miss module summary."""

    total_in_period: int
    previous_period: int
    trend_percent: float
    reporting_rate: str


class ComplaintSummary(BaseModel):
    """Complaint module summary."""

    total_in_period: int
    open: int
    closed_in_period: int
    resolution_rate: float


class RTASummary(BaseModel):
    """RTA module summary."""

    total_in_period: int


class RiskSummary(BaseModel):
    """Risk module summary."""

    total_active: int
    by_level: Dict[str, int]
    high_critical: int
    average_score: float


class KRISummary(BaseModel):
    """KRI module summary."""

    total_active: int
    by_status: Dict[str, int]
    at_risk: int
    pending_alerts: int


class ComplianceSummary(BaseModel):
    """Compliance/policy acknowledgment summary."""

    total_assigned: int
    completed: int
    overdue: int
    completion_rate: float


class SLASummary(BaseModel):
    """SLA performance summary."""

    total_tracked: int
    met: int
    breached: int
    compliance_rate: float


class TrendDataPoint(BaseModel):
    """Single trend data point."""

    week_start: str
    count: int


class TrendData(BaseModel):
    """Trend data for charts."""

    incidents_weekly: List[TrendDataPoint]


class ActiveAlert(BaseModel):
    """Active alert requiring attention."""

    type: str
    severity: str
    title: str
    triggered_at: str


class ExecutiveDashboardResponse(BaseModel):
    """Complete executive dashboard response."""

    generated_at: str
    period_days: int
    health_score: HealthScore
    incidents: IncidentSummary
    near_misses: NearMissSummary
    complaints: ComplaintSummary
    rtas: RTASummary
    risks: RiskSummary
    kris: KRISummary
    compliance: ComplianceSummary
    sla_performance: SLASummary
    trends: TrendData
    alerts: List[ActiveAlert]


class DashboardSummaryResponse(BaseModel):
    """Simplified dashboard summary for quick overview."""

    health_score: float
    health_status: str
    open_incidents: int
    pending_actions: int
    overdue_items: int
    kri_alerts: int


class IncidentDashboardResponse(BaseModel):
    """Incident-specific dashboard data."""

    period_days: int
    summary: Dict[str, Any]
    trends: List[Any]


class RiskDashboardResponse(BaseModel):
    """Risk-specific dashboard data."""

    risks: Dict[str, Any]
    kris: Dict[str, Any]


class ComplianceDashboardResponse(BaseModel):
    """Compliance-specific dashboard data."""

    policy_acknowledgments: Dict[str, Any]
    sla_performance: Dict[str, Any]


class AlertsResponse(BaseModel):
    """Active alerts response."""

    total: int
    alerts: List[Any]
