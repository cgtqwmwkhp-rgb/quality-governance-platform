"""Analytics API response schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, RootModel

# ============================================================================
# Dashboard Schemas
# ============================================================================


class DashboardSummaryItem(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    is_default: bool = False
    widget_count: int = 0
    updated_at: Optional[str] = None


class DashboardListResponse(BaseModel):
    dashboards: list[DashboardSummaryItem] = []


class DashboardCreatedResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    icon: str = "LayoutDashboard"
    color: str = "#10B981"
    created_at: str


class WidgetItem(BaseModel):
    id: int
    widget_type: str
    title: str
    data_source: str
    metric: str
    grid_x: int = 0
    grid_y: int = 0
    grid_w: int = 4
    grid_h: int = 3
    group_by: Optional[str] = None


class DashboardDetailResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    widgets: list[WidgetItem] = []


class DashboardUpdatedResponse(BaseModel):
    id: int
    name: Optional[str] = None
    updated_at: str


class DashboardDeletedResponse(BaseModel):
    success: bool
    id: int


# ============================================================================
# Widget Data Schemas
# ============================================================================


class ChartData(BaseModel):
    labels: list[str] = []
    values: list[float] = []


class WidgetDataPayload(BaseModel):
    value: Optional[float] = None
    previous_value: Optional[float] = None
    change: Optional[float] = None
    trend: Optional[str] = None
    chart_data: Optional[ChartData] = None


class WidgetDataResponse(BaseModel):
    widget_id: int
    data: WidgetDataPayload = WidgetDataPayload()
    updated_at: str


class WidgetPreviewResponse(BaseModel):
    widget_type: str
    title: str
    data: dict[str, Any] = {}


# ============================================================================
# Drill-Down Schemas
# ============================================================================


class DrillDownRecord(BaseModel):
    id: str
    title: str
    date: Optional[str] = None
    status: Optional[str] = None
    severity: Optional[str] = None


class DrillDownResponse(BaseModel):
    data_source: str
    dimension: str
    value: str
    records: list[DrillDownRecord] = []
    total: int = 0


# ============================================================================
# Forecast Schemas
# ============================================================================


class HistoricalData(BaseModel):
    labels: list[str] = []
    values: list[float] = []


class ForecastResponse(BaseModel):
    data_source: str
    metric: str
    historical: HistoricalData = HistoricalData()
    forecast: dict[str, Any] = {}


# ============================================================================
# Cost Schemas
# ============================================================================


class CostRecordResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: str
    amount: float
    created_at: str


# ============================================================================
# ROI Schemas
# ============================================================================


class InvestmentCreatedResponse(BaseModel):
    id: int
    name: str
    category: str
    investment_amount: float
    created_at: str


class InvestmentActualsResponse(BaseModel):
    id: int
    actual_savings: float
    incidents_prevented: int
    updated_at: str


# ============================================================================
# Report Schemas
# ============================================================================


class ReportGeneratedResponse(BaseModel):
    report_id: str
    report_type: str
    format: str
    status: str
    estimated_completion: str
    download_url: Optional[str] = None


class ReportStatusResponse(BaseModel):
    report_id: str
    status: str
    download_url: Optional[str] = None
    expires_at: Optional[str] = None


# ============================================================================
# Service-backed Response Schemas
# ============================================================================


class KpiSummaryResponse(RootModel[dict[str, Any]]):
    pass


class TrendDataResponse(RootModel[dict[str, Any]]):
    pass


class BenchmarkSummaryResponse(RootModel[dict[str, Any]]):
    pass


class BenchmarkComparisonResponse(RootModel[dict[str, Any]]):
    pass


class CostNonComplianceResponse(RootModel[dict[str, Any]]):
    pass


class CostBreakdownResponse(RootModel[dict[str, Any]]):
    pass


class RoiSummaryResponse(RootModel[dict[str, Any]]):
    pass


class InvestmentRoiResponse(RootModel[dict[str, Any]]):
    pass


class ExecutiveSummaryResponse(RootModel[dict[str, Any]]):
    pass
