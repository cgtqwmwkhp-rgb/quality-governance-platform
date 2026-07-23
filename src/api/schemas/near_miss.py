"""Near Miss API schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.api.schemas.validators import reject_future_statutory_datetime, sanitize_field


class NearMissBase(BaseModel):
    """Base schema for Near Miss."""

    reporter_name: str = Field(..., min_length=1, max_length=200)
    reporter_email: Optional[str] = None
    reporter_phone: Optional[str] = None
    reporter_role: Optional[str] = None
    was_involved: bool = True

    contract: str = Field(..., min_length=1, max_length=100)
    contract_other: Optional[str] = None
    location: str = Field(..., min_length=1)
    location_coordinates: Optional[str] = None

    event_date: datetime
    event_time: Optional[str] = None

    description: str = Field(..., min_length=10)
    potential_consequences: Optional[str] = None
    preventive_action_suggested: Optional[str] = None

    persons_involved: Optional[str] = None
    witnesses_present: bool = False
    witness_names: Optional[str] = None

    asset_number: Optional[str] = None
    asset_type: Optional[str] = None
    asset_id: Optional[int] = Field(None, description="Linked Asset registry id (golden thread)")

    risk_category: Optional[str] = None
    potential_severity: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    is_hipo: bool = False


class NearMissCreate(NearMissBase):
    """Schema for creating a Near Miss."""

    attachments: Optional[str] = None  # JSON array of file URLs

    @field_validator("description", "location", "contract", "reporter_name", mode="before")
    @classmethod
    def _sanitize(cls, v: str) -> str:
        return sanitize_field(v)

    @field_validator("event_date")
    @classmethod
    def event_date_not_future(cls, v: datetime) -> datetime:
        return reject_future_statutory_datetime(v)


class NearMissUpdate(BaseModel):
    """Schema for updating a Near Miss."""

    description: Optional[str] = Field(None, min_length=10)
    potential_consequences: Optional[str] = None
    preventive_action_suggested: Optional[str] = None

    status: Optional[str] = Field(None, pattern="^(REPORTED|UNDER_REVIEW|ACTION_REQUIRED|IN_PROGRESS|CLOSED)$")
    priority: Optional[str] = Field(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")

    assigned_to_id: Optional[int] = None

    resolution_notes: Optional[str] = None
    lessons_learnt: Optional[str] = None
    corrective_actions_taken: Optional[str] = None

    risk_category: Optional[str] = None
    potential_severity: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    is_hipo: Optional[bool] = None
    asset_id: Optional[int] = Field(None, description="Linked Asset registry id (null clears link)")
    asset_number: Optional[str] = None
    asset_type: Optional[str] = None
    event_date: Optional[datetime] = None

    @field_validator("description", mode="before")
    @classmethod
    def _sanitize_description(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_field(v)

    @field_validator("event_date")
    @classmethod
    def event_date_not_future(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        return reject_future_statutory_datetime(v)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "NearMissUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for update")
        return self


class NearMissResponse(BaseModel):
    """Response schema for Near Miss.

    Does NOT inherit from NearMissBase to prevent Field constraints
    (min_length, max_length, pattern) from running on DB output
    and causing 500 errors.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    reference_number: str
    reporter_name: str
    reporter_email: Optional[str] = None
    reporter_phone: Optional[str] = None
    reporter_role: Optional[str] = None
    was_involved: bool
    contract: str
    contract_other: Optional[str] = None
    location: str
    location_coordinates: Optional[str] = None
    event_date: datetime
    event_time: Optional[str] = None
    description: str
    potential_consequences: Optional[str] = None
    preventive_action_suggested: Optional[str] = None
    persons_involved: Optional[str] = None
    witnesses_present: bool
    witness_names: Optional[str] = None
    asset_number: Optional[str] = None
    asset_type: Optional[str] = None
    asset_id: Optional[int] = None
    risk_category: Optional[str] = None
    potential_severity: Optional[str] = None
    is_hipo: bool = False
    linked_risk_ids: Optional[str] = None
    status: str
    priority: str
    assigned_to_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    lessons_learnt: Optional[str] = None
    corrective_actions_taken: Optional[str] = None
    closed_at: Optional[datetime] = None
    attachments: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None


class NearMissListResponse(BaseModel):
    """Schema for paginated Near Miss list."""

    items: List[NearMissResponse]
    total: int
    page: int
    page_size: int
    pages: int
