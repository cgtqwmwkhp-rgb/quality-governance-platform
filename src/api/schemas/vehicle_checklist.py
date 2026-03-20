"""Pydantic schemas for Vehicle Checklists (PAMS integration)."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ChecklistSchemaResponse(BaseModel):
    """Auto-discovered column metadata for a PAMS table."""

    table_name: str
    columns: list[dict[str, str]]


class ChecklistRecord(BaseModel):
    """A single checklist row — dynamic keys from PAMS columns."""

    data: dict[str, Any]


class ChecklistListResponse(BaseModel):
    """Paginated list of checklist records."""

    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    pages: int


class DefectCreate(BaseModel):
    """Flag a defect against a PAMS checklist item."""

    pams_table: str = Field(..., pattern="^(daily|monthly)$")
    pams_record_id: int
    check_field: str = Field(..., max_length=255)
    check_value: Optional[str] = Field(None, max_length=500)
    priority: str = Field(..., pattern="^(P1|P2|P3)$")
    notes: Optional[str] = None
    vehicle_reg: Optional[str] = Field(None, max_length=20)
    assigned_to_email: Optional[str] = Field(None, max_length=255)


class DefectResponse(BaseModel):
    """Response schema for a vehicle defect."""

    id: int
    pams_table: str
    pams_record_id: int
    check_field: str
    check_value: Optional[str] = None
    priority: str
    status: str
    notes: Optional[str] = None
    vehicle_reg: Optional[str] = None
    created_by_id: Optional[int] = None
    assigned_to_email: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class DefectListResponse(BaseModel):
    """Paginated list of defects."""

    items: list[DefectResponse]
    total: int
    page: int
    page_size: int
    pages: int


class DefectUpdate(BaseModel):
    """Update a vehicle defect."""

    priority: Optional[str] = Field(None, pattern="^(P1|P2|P3)$")
    status: Optional[str] = Field(
        None,
        pattern="^(open|auto_detected|acknowledged|action_assigned|resolved|dismissed)$",
    )
    notes: Optional[str] = None
    assigned_to_email: Optional[str] = Field(None, max_length=255)


class DefectActionCreate(BaseModel):
    """Create an action against a vehicle defect."""

    title: str = Field(..., max_length=300)
    description: str
    due_date: Optional[str] = Field(None, description="ISO format YYYY-MM-DD")
    assigned_to_email: Optional[str] = Field(None, max_length=255)
    action_type: str = Field(default="corrective")


class AnalyticsSummary(BaseModel):
    """Dashboard summary cards data."""

    total_daily_checks: int = 0
    total_monthly_checks: int = 0
    open_defects: int = 0
    p1_defects: int = 0
    p2_defects: int = 0
    p3_defects: int = 0
    overdue_actions: int = 0
    pass_rate_daily: Optional[float] = None
    pass_rate_monthly: Optional[float] = None
    last_sync: Optional[str] = None


class TrendDataPoint(BaseModel):
    """Single data point for trend charts."""

    date: str
    p1: int = 0
    p2: int = 0
    p3: int = 0
    total: int = 0


class HeatmapEntry(BaseModel):
    """Frequency of failures per check field."""

    check_field: str
    failure_count: int
    pams_table: str
