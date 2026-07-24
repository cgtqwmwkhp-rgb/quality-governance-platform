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


class AuditSummary(BaseModel):
    """Audit reporting-pack summary (Branching Assessments + World-Class Reporting)."""

    totals: int = 0
    completed: int = 0
    in_progress: int = 0
    avg_score: Optional[float] = None
    pass_rate: Optional[float] = None
    essential_compliance_pct: Optional[float] = None
    incomplete_critical_count: int = 0


class TrendDataPoint(BaseModel):
    """Single trend data point.

    Count-series tiles use ``count``. Percentage / score tiles also set ``value``
    (prefer ``value`` when present for sparklines).
    """

    week_start: str
    count: int = 0
    value: Optional[float] = None


class TrendData(BaseModel):
    """Trend data for charts — weekly buckets for pulse sparklines."""

    incidents_weekly: List[TrendDataPoint] = Field(default_factory=list)
    complaints_weekly: List[TrendDataPoint] = Field(default_factory=list)
    near_misses_weekly: List[TrendDataPoint] = Field(default_factory=list)
    audits_weekly: List[TrendDataPoint] = Field(default_factory=list)
    training_compliance_weekly: List[TrendDataPoint] = Field(default_factory=list)
    tool_compliance_weekly: List[TrendDataPoint] = Field(default_factory=list)


class ActiveAlert(BaseModel):
    """Active alert requiring attention."""

    type: str
    severity: str
    title: str
    triggered_at: str


class SafetyInsightsSummary(BaseModel):
    """Latest Safety Insights Analyst snapshot for the executive surface."""

    available: bool = False
    run_id: Optional[int] = None
    completed_at: Optional[str] = None
    top_themes: List[dict] = Field(default_factory=list)
    ratios: Optional[dict] = None
    href: str = "/analytics/safety-insights"


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
    audits: AuditSummary = Field(default_factory=AuditSummary)
    trends: TrendData
    alerts: List[ActiveAlert]
    safety_insights: SafetyInsightsSummary = Field(default_factory=SafetyInsightsSummary)


class VehicleGovernanceSummary(BaseModel):
    """Vehicle governance KPIs for the executive dashboard."""

    total_vehicles: int = 0
    active_vehicles: int = 0
    compliant_vehicles: int = 0
    non_compliant_vehicles: int = 0
    compliance_rate: float = 100.0
    open_defects: int = 0
    open_p1_defects: int = 0
    open_p2_defects: int = 0
    overdue_checks: int = 0
    active_drivers: int = 0
    pending_acknowledgements: int = 0
    open_vehicle_capas: int = 0


class DashboardSummaryResponse(BaseModel):
    """Simplified dashboard summary for quick overview."""

    health_score: float
    health_status: str
    open_incidents: int
    pending_actions: int
    overdue_items: int
    kri_alerts: int
