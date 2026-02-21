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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.api.dependencies import CurrentSuperuser, CurrentUser
from src.api.schemas.analytics import (
    BenchmarkComparisonResponse,
    BenchmarkSummaryResponse,
    CostBreakdownResponse,
    CostNonComplianceResponse,
    CostRecordResponse,
    DashboardCreatedResponse,
    DashboardDeletedResponse,
    DashboardDetailResponse,
    DashboardListResponse,
    DashboardUpdatedResponse,
    DrillDownResponse,
    ExecutiveSummaryResponse,
    ForecastResponse,
    InvestmentActualsResponse,
    InvestmentCreatedResponse,
    InvestmentRoiResponse,
    KpiSummaryResponse,
    ReportGeneratedResponse,
    ReportStatusResponse,
    RoiSummaryResponse,
    TrendDataResponse,
    WidgetDataResponse,
    WidgetPreviewResponse,
)
from src.domain.services.analytics_service import analytics_service
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter()


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


@router.get("/dashboards", response_model=DashboardListResponse)
async def list_dashboards(current_user: CurrentUser):
    """List all dashboards for the current user."""
    # Mock dashboards
    return {
        "dashboards": [
            {
                "id": 1,
                "name": "Executive Overview",
                "description": "High-level KPIs and trends",
                "icon": "LayoutDashboard",
                "color": "#10B981",
                "is_default": True,
                "widget_count": 8,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "id": 2,
                "name": "Safety Performance",
                "description": "Incident and action tracking",
                "icon": "Shield",
                "color": "#3B82F6",
                "is_default": False,
                "widget_count": 6,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "id": 3,
                "name": "Compliance Monitor",
                "description": "ISO compliance tracking",
                "icon": "CheckCircle",
                "color": "#8B5CF6",
                "is_default": False,
                "widget_count": 5,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
    }


@router.post("/dashboards", response_model=DashboardCreatedResponse)
async def create_dashboard(dashboard: DashboardCreate, current_user: CurrentUser):
    """Create a new custom dashboard."""
    _span = tracer.start_span("create_dashboard") if tracer else None
    result = {
        "id": 4,
        "name": dashboard.name,
        "description": dashboard.description,
        "icon": dashboard.icon or "LayoutDashboard",
        "color": dashboard.color or "#10B981",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    track_metric("analytics.dashboards_created", 1)
    if _span:
        _span.end()
    return result


@router.get("/dashboards/{dashboard_id}", response_model=DashboardDetailResponse)
async def get_dashboard(dashboard_id: int, current_user: CurrentUser):
    """Get dashboard with widgets."""
    return {
        "id": dashboard_id,
        "name": "Executive Overview",
        "description": "High-level KPIs and trends",
        "widgets": [
            {
                "id": 1,
                "widget_type": "kpi_card",
                "title": "Total Incidents",
                "data_source": "incidents",
                "metric": "count",
                "grid_x": 0,
                "grid_y": 0,
                "grid_w": 3,
                "grid_h": 2,
            },
            {
                "id": 2,
                "widget_type": "line_chart",
                "title": "Incident Trend",
                "data_source": "incidents",
                "metric": "count",
                "grid_x": 3,
                "grid_y": 0,
                "grid_w": 6,
                "grid_h": 4,
            },
            {
                "id": 3,
                "widget_type": "pie_chart",
                "title": "Incidents by Type",
                "data_source": "incidents",
                "metric": "count",
                "group_by": "type",
                "grid_x": 9,
                "grid_y": 0,
                "grid_w": 3,
                "grid_h": 4,
            },
        ],
    }


@router.put("/dashboards/{dashboard_id}", response_model=DashboardUpdatedResponse)
async def update_dashboard(dashboard_id: int, dashboard: DashboardUpdate, current_user: CurrentUser):
    """Update dashboard configuration."""
    return {
        "id": dashboard_id,
        "name": dashboard.name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/dashboards/{dashboard_id}", response_model=DashboardDeletedResponse)
async def delete_dashboard(dashboard_id: int, current_user: CurrentSuperuser):
    """Delete a dashboard."""
    return {"success": True, "id": dashboard_id}


# ============================================================================
# WIDGET DATA ENDPOINTS
# ============================================================================


@router.get("/widgets/{widget_id}/data", response_model=WidgetDataResponse)
async def get_widget_data(
    widget_id: int,
    current_user: CurrentUser,
    time_range: str = Query("last_30_days"),
):
    """Get data for a specific widget."""
    # Mock widget data based on ID
    return {
        "widget_id": widget_id,
        "data": {
            "value": 47,
            "previous_value": 52,
            "change": -9.6,
            "trend": "down",
            "chart_data": {
                "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
                "values": [15, 12, 10, 10],
            },
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/widgets/preview", response_model=WidgetPreviewResponse)
async def preview_widget(widget: WidgetConfig, current_user: CurrentUser):
    """Preview widget data without saving."""
    trend_data = analytics_service.get_trend_data(
        data_source=widget.data_source,
        metric=widget.metric,
        time_range="last_30_days",
        group_by=widget.group_by,
        tenant_id=current_user.tenant_id,
    )
    return {
        "widget_type": widget.widget_type,
        "title": widget.title,
        "data": trend_data,
    }


# ============================================================================
# KPI & TRENDS ENDPOINTS
# ============================================================================


@router.get("/kpis", response_model=KpiSummaryResponse)
async def get_kpi_summary(
    current_user: CurrentUser,
    time_range: str = Query("last_30_days"),
):
    """Get summary KPIs across all modules."""
    track_metric("analytics.query", 1, {"time_range": time_range})
    return analytics_service.get_kpi_summary(time_range, tenant_id=current_user.tenant_id)


@router.get("/trends/{data_source}", response_model=TrendDataResponse)
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
        tenant_id=current_user.tenant_id,
    )


@router.get("/drill-down/{data_source}", response_model=DrillDownResponse)
async def get_drill_down_data(
    data_source: str,
    current_user: CurrentUser,
    dimension: str = Query(...),
    value: str = Query(...),
    time_range: str = Query("last_30_days"),
):
    """Get drill-down data for a specific dimension value."""
    # Mock drill-down data
    return {
        "data_source": data_source,
        "dimension": dimension,
        "value": value,
        "records": [
            {
                "id": "INC-001",
                "title": "Slip and fall incident",
                "date": "2026-01-15",
                "status": "closed",
                "severity": "medium",
            },
            {
                "id": "INC-002",
                "title": "Near miss - falling object",
                "date": "2026-01-12",
                "status": "closed",
                "severity": "low",
            },
            {
                "id": "INC-003",
                "title": "Equipment malfunction",
                "date": "2026-01-10",
                "status": "open",
                "severity": "high",
            },
        ],
        "total": 3,
    }


# ============================================================================
# FORECASTING ENDPOINTS
# ============================================================================


@router.post("/forecast", response_model=ForecastResponse)
async def generate_forecast(request: ForecastRequest, current_user: CurrentUser):
    """Generate trend forecast with confidence intervals."""
    # Get historical data
    trend_data = analytics_service.get_trend_data(
        data_source=request.data_source,
        metric=request.metric,
        time_range="last_90_days",
        tenant_id=current_user.tenant_id,
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


@router.get("/benchmarks", response_model=BenchmarkSummaryResponse)
async def get_benchmark_summary(
    current_user: CurrentUser,
    industry: str = Query("utilities"),
):
    """Get benchmark comparison summary."""
    return analytics_service.get_benchmark_summary(industry, tenant_id=current_user.tenant_id)


@router.get("/benchmarks/{metric}", response_model=BenchmarkComparisonResponse)
async def get_benchmark_comparison(
    metric: str,
    current_user: CurrentUser,
    industry: str = Query("utilities"),
    region: str = Query("uk"),
):
    """Get benchmark comparison for a specific metric."""
    return analytics_service.get_benchmark_comparison(metric, industry, region, tenant_id=current_user.tenant_id)


# ============================================================================
# COST ANALYSIS ENDPOINTS
# ============================================================================


@router.get("/costs/non-compliance", response_model=CostNonComplianceResponse)
async def get_cost_of_non_compliance(
    current_user: CurrentUser,
    time_range: str = Query("last_12_months"),
):
    """Calculate cost of non-compliance."""
    return analytics_service.calculate_cost_of_non_compliance(time_range, tenant_id=current_user.tenant_id)


@router.post("/costs/record", response_model=CostRecordResponse)
async def record_cost(cost: CostRecord, current_user: CurrentUser):
    """Record a cost entry."""
    return {
        "id": 1,
        "entity_type": cost.entity_type,
        "entity_id": cost.entity_id,
        "amount": cost.amount,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/costs/breakdown", response_model=CostBreakdownResponse)
async def get_cost_breakdown(
    current_user: CurrentUser,
    time_range: str = Query("last_12_months"),
    group_by: str = Query("category"),
):
    """Get cost breakdown by category."""
    costs = analytics_service.calculate_cost_of_non_compliance(time_range, tenant_id=current_user.tenant_id)
    return costs.get("breakdown", {})


# ============================================================================
# ROI TRACKING ENDPOINTS
# ============================================================================


@router.get("/roi", response_model=RoiSummaryResponse)
async def get_roi_summary(current_user: CurrentUser):
    """Get ROI summary for all investments."""
    return analytics_service.calculate_roi(tenant_id=current_user.tenant_id)


@router.get("/roi/{investment_id}", response_model=InvestmentRoiResponse)
async def get_investment_roi(investment_id: int, current_user: CurrentUser):
    """Get ROI for a specific investment."""
    return analytics_service.calculate_roi(investment_id, tenant_id=current_user.tenant_id)


@router.post("/roi/investment", response_model=InvestmentCreatedResponse)
async def create_investment(investment: ROIInvestmentCreate, current_user: CurrentUser):
    """Create a new investment record."""
    return {
        "id": 4,
        "name": investment.name,
        "category": investment.category,
        "investment_amount": investment.investment_amount,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.put("/roi/{investment_id}/actual", response_model=InvestmentActualsResponse)
async def update_investment_actuals(
    investment_id: int,
    actual_savings: float,
    incidents_prevented: int,
    current_user: CurrentUser,
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


@router.get("/reports/executive-summary", response_model=ExecutiveSummaryResponse)
async def get_executive_summary(
    current_user: CurrentUser,
    time_range: str = Query("last_month"),
):
    """Generate executive summary data."""
    return analytics_service.generate_executive_summary(time_range, tenant_id=current_user.tenant_id)


@router.post("/reports/generate", response_model=ReportGeneratedResponse)
async def generate_report(
    report_type: str,
    current_user: CurrentUser,
    format: str = Query("pdf"),
    time_range: str = Query("last_month"),
):
    """Generate and queue a report for download."""
    return {
        "report_id": "RPT-001",
        "report_type": report_type,
        "format": format,
        "status": "generating",
        "estimated_completion": datetime.now(timezone.utc).isoformat(),
        "download_url": None,  # Will be available when complete
    }


@router.get("/reports/{report_id}/status", response_model=ReportStatusResponse)
async def get_report_status(report_id: str, current_user: CurrentUser):
    """Check report generation status."""
    return {
        "report_id": report_id,
        "status": "complete",
        "download_url": f"/api/v1/analytics/reports/{report_id}/download",
        "expires_at": datetime.now(timezone.utc).isoformat(),
    }
