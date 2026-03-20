"""Pydantic schemas for Driver Profile API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DriverProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    user_id: int
    pams_driver_name: Optional[str] = None
    licence_number: Optional[str] = None
    licence_expiry: Optional[datetime] = None
    allocated_vehicle_reg: Optional[str] = None
    compliance_score: float
    last_check_completed_at: Optional[datetime] = None
    is_active_driver: bool
    tenant_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class DriverProfileCreate(BaseModel):
    user_id: int
    pams_driver_name: Optional[str] = Field(None, max_length=255)
    licence_number: Optional[str] = Field(None, max_length=50)
    licence_expiry: Optional[datetime] = None
    allocated_vehicle_reg: Optional[str] = Field(None, max_length=20)
    is_active_driver: bool = True


class DriverProfileUpdate(BaseModel):
    pams_driver_name: Optional[str] = Field(None, max_length=255)
    licence_number: Optional[str] = Field(None, max_length=50)
    licence_expiry: Optional[datetime] = None
    allocated_vehicle_reg: Optional[str] = None
    is_active_driver: Optional[bool] = None


class DriverListResponse(BaseModel):
    items: List[DriverProfileResponse]
    total: int
    page: int
    page_size: int
    pages: int


class DriverAcknowledgementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    driver_profile_id: int
    entity_type: str
    entity_id: int
    status: str
    acknowledged_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime


class AcknowledgementCreate(BaseModel):
    entity_type: str = Field(..., description="vehicle_defect | vehicle_assignment")
    entity_id: int
    notes: Optional[str] = None


class AcknowledgementAction(BaseModel):
    action: str = Field(..., description="acknowledge | refuse")
    notes: Optional[str] = None
