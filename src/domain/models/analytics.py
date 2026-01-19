"""
Analytics Models - Advanced Analytics Dashboard

Supports:
- Custom dashboard configurations
- Widget definitions
- Saved reports
- Benchmark data
- Cost tracking
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database import Base


class WidgetType(str, Enum):
    """Types of dashboard widgets"""

    # Charts
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    AREA_CHART = "area_chart"
    SCATTER_CHART = "scatter_chart"
    HEATMAP = "heatmap"
    GAUGE = "gauge"
    FUNNEL = "funnel"

    # KPIs
    KPI_CARD = "kpi_card"
    TREND_CARD = "trend_card"
    COMPARISON_CARD = "comparison_card"

    # Tables
    DATA_TABLE = "data_table"
    LEADERBOARD = "leaderboard"

    # Other
    MAP = "map"
    TIMELINE = "timeline"
    CALENDAR = "calendar"


class DataSource(str, Enum):
    """Available data sources for widgets"""

    INCIDENTS = "incidents"
    ACTIONS = "actions"
    AUDITS = "audits"
    RISKS = "risks"
    COMPLAINTS = "complaints"
    TRAINING = "training"
    DOCUMENTS = "documents"
    COMPLIANCE = "compliance"
    COMBINED = "combined"


class AggregationType(str, Enum):
    """Aggregation types for metrics"""

    COUNT = "count"
    SUM = "sum"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    PERCENTAGE = "percentage"
    RATE = "rate"


class TimeGranularity(str, Enum):
    """Time granularity for trends"""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class Dashboard(Base):
    """Custom dashboard configuration"""

    __tablename__ = "dashboards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Ownership
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Dashboard info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Layout configuration (JSON)
    layout: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Filters (JSON)
    default_filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Time range
    default_time_range: Mapped[str] = mapped_column(String(50), default="last_30_days")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Dashboard(id={self.id}, name={self.name})>"


class DashboardWidget(Base):
    """Individual widget on a dashboard"""

    __tablename__ = "dashboard_widgets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dashboard_id: Mapped[int] = mapped_column(
        ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Widget configuration
    widget_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Data configuration
    data_source: Mapped[str] = mapped_column(String(50), nullable=False)
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregation: Mapped[str] = mapped_column(String(50), default="count")

    # Dimensions and filters
    group_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Display options
    chart_options: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    colors: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Position in grid
    grid_x: Mapped[int] = mapped_column(Integer, default=0)
    grid_y: Mapped[int] = mapped_column(Integer, default=0)
    grid_w: Mapped[int] = mapped_column(Integer, default=4)
    grid_h: Mapped[int] = mapped_column(Integer, default=3)

    # Drill-down configuration
    drill_down_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    drill_down_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<DashboardWidget(id={self.id}, type={self.widget_type})>"


class SavedReport(Base):
    """Saved/scheduled report configuration"""

    __tablename__ = "saved_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Ownership
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Report info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Configuration
    dashboard_id: Mapped[Optional[int]] = mapped_column(ForeignKey("dashboards.id"), nullable=True)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Schedule
    is_scheduled: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    schedule_timezone: Mapped[str] = mapped_column(String(50), default="UTC")

    # Recipients
    recipients: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    send_email: Mapped[bool] = mapped_column(Boolean, default=True)

    # Output format
    output_format: Mapped[str] = mapped_column(String(20), default="pdf")

    # Last run info
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<SavedReport(id={self.id}, name={self.name})>"


class BenchmarkData(Base):
    """Industry/regional benchmark data"""

    __tablename__ = "benchmark_data"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Benchmark identification
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Values
    value: Mapped[float] = mapped_column(Float, nullable=False)
    percentile_25: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    percentile_50: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    percentile_75: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    percentile_90: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Context
    sample_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    data_year: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<BenchmarkData(category={self.category}, metric={self.metric})>"


class CostRecord(Base):
    """Cost tracking for incidents and non-compliance"""

    __tablename__ = "cost_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Entity reference
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Cost category
    cost_category: Mapped[str] = mapped_column(String(100), nullable=False)
    cost_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Amount
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="GBP")

    # Details
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    invoice_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Classification
    is_direct_cost: Mapped[bool] = mapped_column(Boolean, default=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)

    # Dates
    cost_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<CostRecord(entity={self.entity_type}/{self.entity_id}, amount={self.amount})>"


class ROIInvestment(Base):
    """ROI tracking for safety investments"""

    __tablename__ = "roi_investments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Investment info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    # Investment details
    investment_amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="GBP")
    investment_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Expected benefits
    expected_annual_savings: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_incident_reduction: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    payback_period_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Actual results
    actual_savings_to_date: Mapped[float] = mapped_column(Float, default=0)
    actual_incidents_prevented: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="active")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<ROIInvestment(id={self.id}, name={self.name})>"
