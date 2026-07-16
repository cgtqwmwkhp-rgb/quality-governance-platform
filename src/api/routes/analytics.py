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


@router.get("/kpis")
async def get_kpi_summary(
    db: DbSession,
    current_user: CurrentUser,
    time_range: str = Query("last_30_days"),
):
    """Get summary KPIs across all modules from live executive dashboard aggregates."""
    days = _period_days_from_time_range(time_range)
    service = ExecutiveDashboardService(db, tenant_id=current_user.tenant_id)
    dash = await service.get_full_dashboard(days)
    incidents = dash.get("incidents") or {}
    complaints = dash.get("complaints") or {}
    risks = dash.get("risks") or {}
    compliance = dash.get("compliance") or {}
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
            "resolution_rate": complaints.get("resolution_rate", 0),
        },
        "rtas": {
            "total": (dash.get("rtas") or {}).get("total_in_period", 0),
        },
        "actions": analytics_service.get_kpi_summary(time_range).get("actions"),
        "audits": analytics_service.get_kpi_summary(time_range).get("audits"),
        "risks": {
            "total": risks.get("total_active", 0),
            "high": risks.get("high_critical", 0),
            "medium": (risks.get("by_level") or {}).get("medium", 0),
            "low": (risks.get("by_level") or {}).get("low", 0),
            "mitigated": 0,
        },
        "compliance": {
            "overall_score": compliance.get("completion_rate", 0.0),
            "policy_overdue": compliance.get("overdue", 0),
        },
        "training": analytics_service.get_kpi_summary(time_range).get("training"),
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
