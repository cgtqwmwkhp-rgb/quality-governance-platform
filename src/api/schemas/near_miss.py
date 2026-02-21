"""Near Miss API schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


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

    risk_category: Optional[str] = None
    potential_severity: Optional[str] = Field(
        None, pattern="^(low|medium|high|critical)$"
    )


class NearMissCreate(NearMissBase):
    """Schema for creating a Near Miss."""

    attachments: Optional[str] = None  # JSON array of file URLs


class NearMissUpdate(BaseModel):
    """Schema for updating a Near Miss."""

    description: Optional[str] = None
    potential_consequences: Optional[str] = None
    preventive_action_suggested: Optional[str] = None

    status: Optional[str] = Field(
        None, pattern="^(REPORTED|UNDER_REVIEW|ACTION_REQUIRED|IN_PROGRESS|CLOSED)$"
    )
    priority: Optional[str] = Field(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")

    assigned_to_id: Optional[int] = None

    resolution_notes: Optional[str] = None
    corrective_actions_taken: Optional[str] = None

    risk_category: Optional[str] = None
    potential_severity: Optional[str] = None


class NearMissResponse(NearMissBase):
    """Schema for Near Miss response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str

    status: str
    priority: str

    assigned_to_id: Optional[int] = None
    assigned_at: Optional[datetime] = None

    resolution_notes: Optional[str] = None
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
