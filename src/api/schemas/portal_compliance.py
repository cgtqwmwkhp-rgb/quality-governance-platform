"""Schemas for person-scoped portal tool + van compliance."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ClearState = Literal["clear", "attention", "blocked"]
ToolBand = Literal[
    "overdue",
    "due_30",
    "due_60",
    "due_90",
    "in_date",
    "none",
    "quarantined",
    "decommissioned",
]


class PortalToolItem(BaseModel):
    id: int
    name: str
    asset_number: str
    serial_number: Optional[str] = None
    status: str
    expiry_date: Optional[str] = None
    band: ToolBand
    vehicle_reg: Optional[str] = None
    owner_user_id: Optional[int] = None
    asset_type_name: Optional[str] = None
    type_pending: bool = False
    why_shown: str


class PortalToolSummary(BaseModel):
    total: int = 0
    overdue: int = 0
    due_30: int = 0
    due_60: int = 0
    due_90: int = 0
    in_date: int = 0
    quarantined: int = 0
    mine: int = 0
    on_van: int = 0


class PortalMyToolsResponse(BaseModel):
    items: list[PortalToolItem] = Field(default_factory=list)
    summary: PortalToolSummary
    empty_reason: Optional[str] = None


class PortalOpenDefect(BaseModel):
    id: int
    priority: str
    status: str
    check_field: str
    check_value: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


class PortalDefectCounts(BaseModel):
    p1: int = 0
    p2: int = 0
    p3: int = 0
    total: int = 0


class PortalMyVanResponse(BaseModel):
    linked_driver: bool = False
    vehicle_reg: Optional[str] = None
    assignment_conflict: bool = False
    conflicting_regs: list[str] = Field(default_factory=list)
    empty_reason: Optional[str] = None
    daily_last_at: Optional[str] = None
    daily_pass: Optional[bool] = None
    monthly_last_at: Optional[str] = None
    open_defects: list[PortalOpenDefect] = Field(default_factory=list)
    defect_counts: PortalDefectCounts = Field(default_factory=PortalDefectCounts)
    fleet_status: Optional[str] = None
    compliance_status: Optional[str] = None


class PortalVanSummary(BaseModel):
    vehicle_reg: Optional[str] = None
    daily_last_at: Optional[str] = None
    daily_pass: Optional[bool] = None
    monthly_last_at: Optional[str] = None
    defect_counts: PortalDefectCounts = Field(default_factory=PortalDefectCounts)
    empty_reason: Optional[str] = None
    assignment_conflict: bool = False


class PortalMyComplianceResponse(BaseModel):
    clear_state: ClearState
    tool_summary: PortalToolSummary
    tool_badge: int = 0
    van_summary: PortalVanSummary
    van_badge: int = 0
    tools_empty_reason: Optional[str] = None


class PortalDriverMeResponse(BaseModel):
    linked: bool
    driver_profile_id: Optional[int] = None
    pams_driver_name: Optional[str] = None
    allocated_vehicle_reg: Optional[str] = None
    vehicle_reg: Optional[str] = None
    assignment_conflict: bool = False
    conflicting_regs: list[str] = Field(default_factory=list)
    empty_reason: Optional[str] = None
