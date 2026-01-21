"""Pydantic schemas for Road Traffic Collisions (RTAs)."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.models.rta import RTASeverity, RTAStatus


class RTABase(BaseModel):
    """Base schema for RTA."""

    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1)
    severity: RTASeverity = RTASeverity.DAMAGE_ONLY
    status: RTAStatus = RTAStatus.REPORTED
    collision_date: datetime
    reported_date: datetime
    location: str = Field(..., min_length=1, max_length=500)
    road_name: Optional[str] = Field(None, max_length=200)
    postcode: Optional[str] = Field(None, max_length=20)

    # Optional fields
    collision_time: Optional[str] = Field(None, max_length=10)
    weather_conditions: Optional[str] = Field(None, max_length=100)
    road_conditions: Optional[str] = Field(None, max_length=100)
    lighting_conditions: Optional[str] = Field(None, max_length=100)
    company_vehicle_registration: Optional[str] = Field(None, max_length=20)
    company_vehicle_make_model: Optional[str] = Field(None, max_length=100)
    company_vehicle_damage: Optional[str] = None
    driver_name: Optional[str] = Field(None, max_length=200)
    driver_statement: Optional[str] = None
    driver_injured: bool = False
    driver_injury_details: Optional[str] = None
    third_parties: Optional[dict] = None
    witnesses: Optional[str] = None
    police_attended: bool = False
    police_reference: Optional[str] = Field(None, max_length=100)
    police_station: Optional[str] = Field(None, max_length=200)
    insurance_notified: bool = False
    insurance_reference: Optional[str] = Field(None, max_length=100)
    insurance_notes: Optional[str] = None
    estimated_cost: Optional[int] = None
    investigation_notes: Optional[str] = None
    root_cause: Optional[str] = None
    fault_determination: Optional[str] = Field(None, max_length=50)
    linked_risk_ids: Optional[str] = None
    closure_notes: Optional[str] = None

    @field_validator("title", "description", "location")
    @classmethod
    def must_not_be_whitespace(cls, v: str) -> str:
        """Validate field is not just whitespace."""
        if not v.strip():
            raise ValueError("Field must not be empty or whitespace")
        return v.strip()


class RTACreate(RTABase):
    """Schema for creating an RTA."""

    driver_id: Optional[int] = None
    driver_email: Optional[str] = Field(None, max_length=255, description="Driver's email for portal tracking")
    investigator_id: Optional[int] = None
    reporter_id: Optional[int] = None
    reporter_email: Optional[str] = Field(None, max_length=255, description="Reporter's email for portal tracking")
    reporter_name: Optional[str] = Field(None, max_length=255, description="Reporter's name")


class RTAUpdate(BaseModel):
    """Schema for updating an RTA."""

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    severity: Optional[RTASeverity] = None
    status: Optional[RTAStatus] = None
    collision_date: Optional[datetime] = None
    reported_date: Optional[datetime] = None
    location: Optional[str] = Field(None, min_length=1, max_length=500)
    road_name: Optional[str] = Field(None, max_length=200)
    postcode: Optional[str] = Field(None, max_length=20)
    collision_time: Optional[str] = Field(None, max_length=10)
    weather_conditions: Optional[str] = Field(None, max_length=100)
    road_conditions: Optional[str] = Field(None, max_length=100)
    lighting_conditions: Optional[str] = Field(None, max_length=100)
    company_vehicle_registration: Optional[str] = Field(None, max_length=20)
    company_vehicle_make_model: Optional[str] = Field(None, max_length=100)
    company_vehicle_damage: Optional[str] = None
    driver_id: Optional[int] = None
    driver_name: Optional[str] = Field(None, max_length=200)
    driver_statement: Optional[str] = None
    driver_injured: Optional[bool] = None
    driver_injury_details: Optional[str] = None
    third_parties: Optional[dict] = None
    witnesses: Optional[str] = None
    police_attended: Optional[bool] = None
    police_reference: Optional[str] = Field(None, max_length=100)
    police_station: Optional[str] = Field(None, max_length=200)
    insurance_notified: Optional[bool] = None
    insurance_reference: Optional[str] = Field(None, max_length=100)
    insurance_notes: Optional[str] = None
    estimated_cost: Optional[int] = None
    investigator_id: Optional[int] = None
    investigation_notes: Optional[str] = None
    root_cause: Optional[str] = None
    fault_determination: Optional[str] = Field(None, max_length=50)
    reporter_id: Optional[int] = None
    linked_risk_ids: Optional[str] = None
    closed_at: Optional[datetime] = None
    closed_by_id: Optional[int] = None
    closure_notes: Optional[str] = None

    @field_validator("title", "description", "location")
    @classmethod
    def must_not_be_whitespace(cls, v: Optional[str]) -> Optional[str]:
        """Validate field is not just whitespace."""
        if v is not None and not v.strip():
            raise ValueError("Field must not be empty or whitespace")
        return v.strip() if v is not None else None


class RTAResponse(RTABase):
    """Schema for RTA response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str
    driver_id: Optional[int] = None
    driver_email: Optional[str] = None
    investigator_id: Optional[int] = None
    reporter_id: Optional[int] = None
    reporter_email: Optional[str] = None
    reporter_name: Optional[str] = None
    closed_at: Optional[datetime] = None
    closed_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None
    updated_by_id: Optional[int] = None


class RTAListResponse(BaseModel):
    """Schema for paginated RTA list response."""

    items: List[RTAResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class RTAActionBase(BaseModel):
    """Base schema for RTA Action."""

    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1)
    action_type: str = Field(default="corrective", max_length=50)
    priority: str = Field(default="medium", max_length=20)
    owner_id: Optional[int] = None
    due_date: Optional[datetime] = None

    @field_validator("title", "description")
    @classmethod
    def must_not_be_whitespace(cls, v: str) -> str:
        """Validate field is not just whitespace."""
        if not v.strip():
            raise ValueError("Field must not be empty or whitespace")
        return v.strip()


class RTAActionCreate(RTAActionBase):
    """Schema for creating an RTA Action."""

    pass


class RTAActionUpdate(BaseModel):
    """Schema for updating an RTA Action."""

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    action_type: Optional[str] = Field(None, max_length=50)
    priority: Optional[str] = Field(None, max_length=20)
    owner_id: Optional[int] = None
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    verified_by_id: Optional[int] = None
    completion_notes: Optional[str] = None
    verification_notes: Optional[str] = None

    @field_validator("title", "description")
    @classmethod
    def must_not_be_whitespace(cls, v: Optional[str]) -> Optional[str]:
        """Validate field is not just whitespace."""
        if v is not None and not v.strip():
            raise ValueError("Field must not be empty or whitespace")
        return v.strip() if v is not None else None


class RTAActionResponse(RTAActionBase):
    """Schema for RTA Action response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rta_id: int
    reference_number: str
    status: str
    completed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    verified_by_id: Optional[int] = None
    completion_notes: Optional[str] = None
    verification_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None
    updated_by_id: Optional[int] = None


class RTAActionListResponse(BaseModel):
    """Schema for paginated RTA Action list response."""

    items: List[RTAActionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
