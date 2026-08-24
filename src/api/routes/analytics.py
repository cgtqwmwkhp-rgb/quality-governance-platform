"""
Analytics API Routes

Features:
- Dashboard CRUD
- Widget data endpoints
- Trend analysis
- Forecasting
- Benchmarks
- Cost calculations
- ROI tracking
"""

from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.routes.actions import _compute_actions_summary
from src.domain.models.user import User
from src.domain.services.analytics_service import analytics_service
from src.domain.services.executive_dashboard import ExecutiveDashboardService

router = APIRouter()


def _period_days_from_time_range(time_range: str) -> int:
    normalized = (time_range or "").strip().lower().replace("-", "_")
    mapping = {
        "7d": 7,
        "last_7_days": 7,
        "30d": 30,
        "last_30_days": 30,
        "90d": 90,
        "last_90_days": 90,
        "1y": 365,
        "last_365_days": 365,
        "last_year": 365,
    }
    return mapping.get(normalized, 30)


# ============================================================================
# SCHEMAS
# ============================================================================


class WidgetConfig(BaseModel):
    """Widget configuration"""

    widget_type: str
    title: str
    data_source: str
    metric: str
    aggregation: str = "count"
    group_by: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    chart_options: Optional[Dict[str, Any]] = None
    grid_x: int = 0
    grid_y: int = 0
    grid_w: int = 4
    grid_h: int = 3


class DashboardCreate(BaseModel):
    """Create dashboard request"""

    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    widgets: Optional[List[WidgetConfig]] = None
    default_time_range: str = "last_30_days"


class DashboardUpdate(BaseModel):
    """Update dashboard request"""

    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    layout: Optional[Dict[str, Any]] = None
    default_time_range: Optional[str] = None


class ForecastRequest(BaseModel):
    """Forecast request"""

    data_source: str
    metric: str
    periods_ahead: int = 12
    confidence_level: float = 0.95


class CostRecord(BaseModel):
    """Cost record input"""

    entity_type: str
    entity_id: str
    cost_category: str
    cost_type: str
    amount: float
    currency: str = "GBP"
    description: Optional[str] = None
    cost_date: datetime


class ROIInvestmentCreate(BaseModel):
    """ROI investment input"""

    name: str
    description: Optional[str] = None
    category: str
    investment_amount: float
    currency: str = "GBP"
    investment_date: datetime
    expected_annual_savings: Optional[float] = None
    expected_incident_reduction: Optional[float] = None


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================


@router.get("/dashboards")
async def list_dashboards(current_user: CurrentUser):
    """List all dashboards for the current user."""
    return {"dashboards": []}


@router.post("/dashboards")
async def create_dashboard(
    dashboard: DashboardCreate,
    current_user: Annotated[User, Depends(require_permission("analytics:create"))],
):
    """Create a new custom dashboard."""
    return {
        "id": 4,
        "name": dashboard.name,
        "description": dashboard.description,
        "icon": dashboard.icon or "LayoutDashboard",
        "color": dashboard.color or "#10B981",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/dashboards/{dashboard_id}")
async def get_dashboard(dashboard_id: int, current_user: CurrentUser):
    """Get dashboard with widgets."""
    return {
        "id": dashboard_id,
        "name": "",
        "description": "",
        "widgets": [],
    }


@router.put("/dashboards/{dashboard_id}")
async def update_dashboard(
    dashboard_id: int,
    dashboard: DashboardUpdate,
    current_user: Annotated[User, Depends(require_permission("analytics:update"))],
):
    """Update dashboard configuration."""
    return {
        "id": dashboard_id,
        "name": dashboard.name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/dashboards/{dashboard_id}")
async def delete_dashboard(
    dashboard_id: int,
    current_user: Annotated[User, Depends(require_permission("analytics:delete"))],
):
    """Delete a dashboard."""
    return {"success": True, "id": dashboard_id}


# ============================================================================
# WIDGET DATA ENDPOINTS
# ============================================================================


@router.get("/widgets/{widget_id}/data")
async def get_widget_data(
    widget_id: int,
    current_user: CurrentUser,
    time_range: str = Query("last_30_days"),
):
    """Get data for a specific widget."""
    return {
        "widget_id": widget_id,
        "data": {
            "value": 0,
            "previous_value": 0,
            "change": 0.0,
            "trend": "stable",
            "chart_data": {
                "labels": [],
                "values": [],
            },
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/widgets/preview")
async def preview_widget(
    widget: WidgetConfig,
    current_user: Annotated[User, Depends(require_permission("analytics:create"))],
):
    """Preview widget data without saving."""
    trend_data = analytics_service.get_trend_data(
        data_source=widget.data_source,
        metric=widget.metric,
        time_range="last_30_days",
        group_by=widget.group_by,
    )
    return {
        "widget_type": widget.widget_type,
        "title": widget.title,
        "data": trend_data,
    }


# ============================================================================
# KPI & TRENDS ENDPOINTS
# ============================================================================

MEASURED = "measured"
UNAVAILABLE = "unavailable"


def _training_kpi_block(training: Dict[str, Any]) -> Dict[str, Any]:
    """Shape the training aggregate so a stub zero is not expressible.

    A discriminated union rather than nullable fields, following #1402. The
    ``unavailable`` branch carries **no numeric field at all**: the whole defect
    (C-7) was that a consumer could not tell a measured 0% from a never-measured
    one, and a branch that still offered ``completion_rate: null`` would leave
    that distinction resting on the client remembering to check for null.

    ``status`` is what makes this safe against the trap #1404 documented. Merely
    omitting fields is not enough on its own, because a client reading
    ``training.completion_rate ?? 0`` puts the fabricated zero straight back; the
    web client is updated in the same change to branch on ``status`` instead.
    """
    measured_cells = training.get("measured_cells")
    if not isinstance(measured_cells, int) or measured_cells <= 0:
        return {
            "status": UNAVAILABLE,
            "reason": "no_scored_training_matrix_cells",
            "detail": (
                "Training compliance needs a training matrix import with at least one "
                "scored cell for this tenant. None was readable, so no rate is reported."
            ),
        }
    return {
        "status": MEASURED,
        "completion_rate": training.get("completion_rate"),
        "expiring_soon": training.get("expiring_soon"),
        "overdue": training.get("overdue"),
        # The denominator travels with the rate so a consumer can see what the
        # percentage was taken over rather than trusting it blind.
        "measured_cells": measured_cells,
        "compliant_cells": training.get("compliant_cells"),
    }


def _audits_kpi_block(audits: Dict[str, Any], *, measured: bool) -> Dict[str, Any]:
    """Project the dashboard audit aggregate onto the KPI tile's field names.

    ``totals`` is renamed to ``total`` because that is the name this endpoint has
    always published. ``trend`` is None rather than 0.0: no period-over-period
    audit comparison is computed anywhere, so the 0.0 the old stub supplied was a
    fabricated "no change" that rendered as a real trend indicator.

    ``measured=False`` means the audit aggregate's query failed, and the counts in
    ``audits`` are its empty default rather than anything read from the database.
    #1420 made the *rates* honest for that case (``avg_score`` and friends were
    already None), but left ``total``/``completed``/``in_progress`` reading 0 —
    which is byte-identical to a tenant that genuinely ran no audits. Measured on
    PostgreSQL with ``audit_runs.status`` dropped, the tile published
    ``total: 0, completed: 0`` while three runs sat in the table and the
    unfiltered ``count(*)`` that produces ``total`` had *succeeded*. The zero was
    not an approximation of the truth, it was unrelated to it.

    So the unavailable branch carries no count key at all, following the
    discriminated union ``_training_kpi_block`` uses. Omission rather than null
    because the web client reads ``Number(payload?.audits?.total ?? 0)``, and
    ``null ?? 0`` is 0 — a nullable field would leave the fabrication one
    defensive idiom away from returning. The rate keys stay present-and-None:
    they were already honest, the client already reads them with
    ``numberOrNull``, and removing them would break consumers for no gain.
    """
    if not measured:
        return {
            "status": UNAVAILABLE,
            "reason": "audit_aggregate_query_failed",
            "detail": (
                "The audit aggregate could not be read for this tenant, so no audit "
                "count is reported. This is not a report that there are no audits."
            ),
            "avg_score": None,
            "pass_rate": None,
            "essential_compliance_pct": None,
            "trend": None,
        }
    return {
        "status": MEASURED,
        "total": audits.get("totals", 0),
        "completed": audits.get("completed", 0),
        "in_progress": audits.get("in_progress", 0),
        "avg_score": audits.get("avg_score"),
        "pass_rate": audits.get("pass_rate"),
        "essential_compliance_pct": audits.get("essential_compliance_pct"),
        "incomplete_critical_count": audits.get("incomplete_critical_count", 0),
        "trend": None,
    }


@router.get("/kpis")
async def get_kpi_summary(
    db: DbSession,
    current_user: CurrentUser,
    time_range: str = Query("last_30_days"),
):
    """Get summary KPIs across all modules from live executive dashboard aggregates."""
    days = _period_days_from_time_range(time_range)

    # Read every attribute we need off `current_user` before delegating the session.
    # `get_current_user` loads the User on *this* request's session, and the services
    # below recover that session when a sub-query fails, so that one failed
    # statement cannot poison the rest of the request (#1388). A full rollback expires
    # every instance in the session, so reading `current_user.tenant_id` afterwards
    # makes SQLAlchemy issue a lazy refresh — synchronous IO on an async session,
    # which raises MissingGreenlet and 500s the endpoint. A plain int cannot expire.
    #
    # Since C-8 that recovery unwinds to a SAVEPOINT and leaves the identity map
    # alone, so this read is no longer the only thing standing between a drifted
    # column and a 500. It stays because the full rollback survives as the fallback
    # for a session that cannot open a savepoint, and because a local int is free.
    tenant_id = current_user.tenant_id

    service = ExecutiveDashboardService(db, tenant_id=tenant_id)
    dash = await service.get_full_dashboard(days)
    incidents = dash.get("incidents") or {}
    complaints = dash.get("complaints") or {}
    rtas = dash.get("rtas") or {}
    risks = dash.get("risks") or {}
    compliance = dash.get("compliance") or {}

    # Actions come from the unified actions aggregate, not a static stub. `overdue`
    # here is the same value /actions/summary and /actions/view-counts return, so the
    # analytics tile cannot contradict the Actions page filter chip (PX-149/PX-178).
    actions_summary = await _compute_actions_summary(db, tenant_id)
    by_display = actions_summary.by_display_status

    # Audits come from the same dashboard aggregate as every other tile, not from a
    # second query seeded with stub zeros (C-7). The previous shape started from
    # `analytics_service.get_kpi_summary`, an in-memory dict of hardcoded zeros, and
    # overwrote it inside a `try/except: pass`, so a failed audit query silently
    # published those zeros — including `avg_score: 0.0` — as though they had been
    # measured. That `except` also did not roll back; on PostgreSQL the aborted
    # transaction would refuse every later statement, which was harmless only
    # because it happened to be the last query in the handler. Reading the aggregate
    # `get_full_dashboard` already produced removes both the stub and the bare
    # except (`_safe_call` recovers the session), drops a duplicate audit query, and makes this
    # tile agree with /executive-dashboard by construction rather than by coincidence.
    #
    # `unavailable` names the aggregates whose queries failed. Asking the service
    # which tiles are real, rather than inspecting their values for a zero, is what
    # separates "no audits ran" from "the audit query could not run": those two
    # produce the same numbers and only the service knows which happened.
    unmeasurable = set(dash.get("unavailable") or ())
    audits_summary = _audits_kpi_block(dash.get("audits") or {}, measured="audits" not in unmeasurable)

    return {
        "period_days": days,
        "generated_at": dash.get("generated_at"),
        "health_score": dash.get("health_score"),
        "incidents": {
            "total": incidents.get("total_in_period", 0),
            "open": incidents.get("open", 0),
            "closed": max(
                0,
                int(incidents.get("total_in_period", 0)) - int(incidents.get("open", 0)),
            ),
            "trend": 0.0,
            "avg_resolution_days": 0.0,
            "critical_high": incidents.get("critical_high", 0),
        },
        "complaints": {
            "total": complaints.get("total_in_period", 0),
            "open": complaints.get("open", 0),
            "closed": complaints.get("closed_in_period", 0),
            "resolution_rate": complaints.get("resolution_rate"),
        },
        # total/open/closed all describe the register, so open can never exceed total.
        # total_in_period stays available separately for period-scoped reporting.
        "rtas": {
            "total": rtas.get("total", 0),
            "total_in_period": rtas.get("total_in_period", 0),
            "open": rtas.get("open", 0),
            "closed": rtas.get("closed", 0),
        },
        "actions": {
            "total": actions_summary.total,
            "open": int(by_display.get("open", 0)) + int(by_display.get("in_progress", 0)),
            "overdue": actions_summary.overdue,
            # Not derivable from the unified aggregate; None means "not measured"
            # rather than a fabricated 0.
            "completed_on_time_rate": None,
            "trend": None,
        },
        "audits": audits_summary,
        # `total` is the whole visible register so it reconciles with
        # /risk-register/; `high`/`medium`/`low` describe the not-closed subset.
        "risks": {
            "total": risks.get("register_total"),
            "total_active": risks.get("total_active", 0),
            "high": risks.get("high_critical", 0),
            "medium": (risks.get("by_level") or {}).get("medium", 0),
            "low": (risks.get("by_level") or {}).get("low", 0),
            "mitigated": 0,
        },
        "compliance": {
            "policy_acknowledgment_rate": compliance.get("completion_rate"),
            "overall_score": compliance.get("completion_rate"),
            "policy_overdue": compliance.get("overdue", 0),
        },
        "score_definitions": {
            "health_score": (
                "Weighted composite of incidents, near misses, risks, KRIs, "
                "policy acknowledgments, and SLA performance for the selected period."
            ),
            "policy_acknowledgment_rate": (
                "Share of assigned policy-reading campaigns completed — not ISO evidence coverage."
            ),
            "audit_avg_score": ("Mean score_percentage of completed audit runs created in the selected period."),
        },
        "training": _training_kpi_block(dash.get("training") or {}),
        "source": "executive_dashboard",
    }


@router.get("/trends/{data_source}")
async def get_trend_data(
    data_source: str,
    current_user: CurrentUser,
    metric: str = Query("count"),
    granularity: str = Query("daily"),
    time_range: str = Query("last_30_days"),
    group_by: Optional[str] = None,
):
    """Get trend data for charting."""
    return analytics_service.get_trend_data(
        data_source=data_source,
        metric=metric,
        granularity=granularity,
        time_range=time_range,
        group_by=group_by,
    )


@router.get("/drill-down/{data_source}")
async def get_drill_down_data(
    data_source: str,
    current_user: CurrentUser,
    dimension: str = Query(...),
    value: str = Query(...),
    time_range: str = Query("last_30_days"),
):
    """Get drill-down data for a specific dimension value."""
    return {
        "data_source": data_source,
        "dimension": dimension,
        "value": value,
        "records": [],
        "total": 0,
    }


# ============================================================================
# FORECASTING ENDPOINTS
# ============================================================================


@router.post("/forecast")
async def generate_forecast(
    request: ForecastRequest,
    current_user: Annotated[User, Depends(require_permission("analytics:create"))],
):
    """Generate trend forecast with confidence intervals."""
    # Get historical data
    trend_data = analytics_service.get_trend_data(
        data_source=request.data_source,
        metric=request.metric,
        time_range="last_90_days",
    )

    historical = trend_data["datasets"][0]["data"] if trend_data["datasets"] else []

    # Generate forecast
    forecast = analytics_service.forecast_trend(
        historical_data=historical,
        periods_ahead=request.periods_ahead,
        confidence_level=request.confidence_level,
    )

    return {
        "data_source": request.data_source,
        "metric": request.metric,
        "historical": {
            "labels": trend_data["labels"],
            "values": historical,
        },
        "forecast": forecast,
    }


# ============================================================================
# BENCHMARK ENDPOINTS
# ============================================================================


@router.get("/benchmarks")
async def get_benchmark_summary(
    current_user: CurrentUser,
    industry: str = Query("utilities"),
):
    """Get benchmark comparison summary."""
    return analytics_service.get_benchmark_summary(industry)


@router.get("/benchmarks/{metric}")
async def get_benchmark_comparison(
    metric: str,
    current_user: CurrentUser,
    industry: str = Query("utilities"),
    region: str = Query("uk"),
):
    """Get benchmark comparison for a specific metric."""
    return analytics_service.get_benchmark_comparison(metric, industry, region)


# ============================================================================
# COST ANALYSIS ENDPOINTS
# ============================================================================


@router.get("/costs/non-compliance")
async def get_cost_of_non_compliance(
    current_user: CurrentUser,
    time_range: str = Query("last_12_months"),
):
    """Calculate cost of non-compliance."""
    return analytics_service.calculate_cost_of_non_compliance(time_range)


@router.post("/costs/record")
async def record_cost(
    cost: CostRecord,
    current_user: Annotated[User, Depends(require_permission("analytics:create"))],
):
    """Record a cost entry."""
    return {
        "id": 1,
        "entity_type": cost.entity_type,
        "entity_id": cost.entity_id,
        "amount": cost.amount,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/costs/breakdown")
async def get_cost_breakdown(
    current_user: CurrentUser,
    time_range: str = Query("last_12_months"),
    group_by: str = Query("category"),
):
    """Get cost breakdown by category."""
    costs = analytics_service.calculate_cost_of_non_compliance(time_range)
    return costs.get("breakdown", {})


# ============================================================================
# ROI TRACKING ENDPOINTS
# ============================================================================


@router.get("/roi")
async def get_roi_summary(current_user: CurrentUser):
    """Get ROI summary for all investments."""
    return analytics_service.calculate_roi()


@router.get("/roi/{investment_id}")
async def get_investment_roi(investment_id: int, current_user: CurrentUser):
    """Get ROI for a specific investment."""
    return analytics_service.calculate_roi(investment_id)


@router.post("/roi/investment")
async def create_investment(
    investment: ROIInvestmentCreate,
    current_user: Annotated[User, Depends(require_permission("analytics:create"))],
):
    """Create a new investment record."""
    return {
        "id": 4,
        "name": investment.name,
        "category": investment.category,
        "investment_amount": investment.investment_amount,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.put("/roi/{investment_id}/actual")
async def update_investment_actuals(
    investment_id: int,
    actual_savings: float,
    incidents_prevented: int,
    current_user: Annotated[User, Depends(require_permission("analytics:update"))],
):
    """Update actual savings and incidents prevented."""
    return {
        "id": investment_id,
        "actual_savings": actual_savings,
        "incidents_prevented": incidents_prevented,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# REPORT GENERATION ENDPOINTS
# ============================================================================


@router.get("/reports/executive-summary")
async def get_executive_summary(
    current_user: CurrentUser,
    time_range: str = Query("last_month"),
):
    """Generate executive summary data."""
    return analytics_service.generate_executive_summary(time_range)


class ReportRequest(BaseModel):
    report_type: str
    output_format: str = "pdf"
    time_range: str = "last_month"


@router.post("/reports/generate")
async def generate_report(
    body: ReportRequest,
    current_user: Annotated[User, Depends(require_permission("analytics:create"))],
):
    """Generate and queue a report for download."""
    return {
        "report_id": "RPT-001",
        "report_type": body.report_type,
        "format": body.output_format,
        "status": "generating",
        "estimated_completion": datetime.now(timezone.utc).isoformat(),
        "download_url": None,
    }


@router.get("/reports/{report_id}/status")
async def get_report_status(report_id: str, current_user: CurrentUser):
    """Check report generation status."""
    return {
        "report_id": report_id,
        "status": "complete",
        "download_url": f"/api/v1/analytics/reports/{report_id}/download",
        "expires_at": datetime.now(timezone.utc).isoformat(),
    }
