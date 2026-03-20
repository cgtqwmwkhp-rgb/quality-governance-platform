"""Pydantic schemas for Vehicle Registry API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class VehicleRegistryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    vehicle_reg: str
    pams_van_id: Optional[str] = None
    asset_id: Optional[int] = None
    fleet_status: str
    compliance_status: str
    last_daily_check_at: Optional[datetime] = None
    last_monthly_check_at: Optional[datetime] = None
    last_daily_check_pass: Optional[bool] = None
    road_tax_expiry: Optional[datetime] = None
    fire_extinguisher_expiry: Optional[datetime] = None
    tooling_calibration_expiry: Optional[datetime] = None
    assigned_driver_id: Optional[int] = None
    tenant_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class VehicleRegistryUpdate(BaseModel):
    fleet_status: Optional[str] = Field(None, description="active | vor | maintenance | decommissioned")
    assigned_driver_id: Optional[int] = None
    asset_id: Optional[int] = None


class VehicleListResponse(BaseModel):
    items: List[VehicleRegistryResponse]
    total: int
    page: int
    page_size: int
    pages: int


class VehicleDefectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    check_field: str
    check_value: Optional[str] = None
    priority: str
    status: str
    vehicle_reg: Optional[str] = None
    created_at: datetime


class VehicleDetailResponse(BaseModel):
    vehicle: VehicleRegistryResponse
    open_defects: List[VehicleDefectSummary]
    total_defects: int


class ComplianceGateResponse(BaseModel):
    vehicle_reg: str
    compliant: bool
    compliance_status: str
    fleet_status: str
    open_p1_count: int
    open_p2_count: int
    checks_current: bool
    message: str


class FleetHealthResponse(BaseModel):
    total_vehicles: int
    active: int
    vor: int
    maintenance: int
    decommissioned: int
    compliant: int
    non_compliant: int
    overdue_check: int
    suspended: int
    compliance_rate: float
