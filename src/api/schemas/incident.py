"""Incident API schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.api.schemas.validators import reject_future_statutory_datetime, sanitize_field
from src.domain.models.incident import IncidentSeverity, IncidentStatus, IncidentType


class IncidentBase(BaseModel):
    """Base incident schema with common fields."""

    title: str = Field(..., min_length=1, max_length=300, description="Incident title")
    description: str = Field(..., description="Detailed description of the incident")
    incident_type: IncidentType = Field(default=IncidentType.OTHER, description="Type of incident")
    severity: IncidentSeverity = Field(default=IncidentSeverity.MEDIUM, description="Severity level")
    status: IncidentStatus = Field(default=IncidentStatus.REPORTED, description="Current status")
    incident_date: datetime = Field(..., description="When the incident occurred")
    location: Optional[str] = Field(None, max_length=300, description="Where the incident occurred")
    department: Optional[str] = Field(None, max_length=100, description="Department involved")
    asset_id: Optional[int] = Field(None, description="Linked Asset registry id (golden thread)")


class IncidentCreate(IncidentBase):
    """Schema for creating a new incident."""

    reference_number: Optional[str] = Field(
        None,
        max_length=50,
        description="Optional explicit reference number (requires permission)",
    )
    reporter_email: Optional[str] = Field(
        None,
        max_length=255,
        description="Email of the person reporting (for portal submissions)",
    )
    reporter_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Name of the person reporting (for portal submissions)",
    )

    @field_validator("title", "description", "location", "department", mode="before")
    @classmethod
    def _sanitize(cls, v: str) -> str:
        return sanitize_field(v)

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Title cannot be empty or whitespace")
        return v.strip()

    @field_validator("incident_date")
    @classmethod
    def incident_date_not_future(cls, v: datetime) -> datetime:
        return reject_future_statutory_datetime(v)


class IncidentUpdate(BaseModel):
    """Schema for updating an existing incident."""

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    incident_type: Optional[IncidentType] = None
    severity: Optional[IncidentSeverity] = None
    status: Optional[IncidentStatus] = None
    incident_date: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=300)
    department: Optional[str] = Field(None, max_length=100)
    owner_id: Optional[int] = Field(None, description="Case owner user id (null clears assignment)")
    asset_id: Optional[int] = Field(None, description="Linked Asset registry id (null clears link)")

    @field_validator("title", "description", "location", "department", mode="before")
    @classmethod
    def _sanitize(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_field(v)

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError("Title cannot be empty or whitespace")
        return v.strip() if v else None

    @field_validator("incident_date")
    @classmethod
    def incident_date_not_future(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        return reject_future_statutory_datetime(v)


class IncidentResponse(BaseModel):
    """Response schema for incidents.

    Does NOT inherit from IncidentBase to prevent Field constraints
    (min_length, max_length) from running on DB output and causing 500 errors.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    reference_number: str
    title: str
    description: str
    incident_type: IncidentType
    severity: IncidentSeverity
    status: IncidentStatus
    incident_date: datetime
    location: Optional[str] = None
    department: Optional[str] = None
    reported_date: datetime
    created_at: datetime
    updated_at: datetime
    reporter_id: Optional[int] = None
    reporter_email: Optional[str] = None
    reporter_name: Optional[str] = None
    people_involved: Optional[str] = None
    witnesses: Optional[str] = None
    immediate_actions: Optional[str] = None
    first_aid_given: bool = False
    emergency_services_called: bool = False
    investigator_id: Optional[int] = None
    is_riddor_reportable: Optional[bool] = None
    riddor_classification: Optional[str] = None
    is_sif: Optional[bool] = None
    life_altering_potential: Optional[bool] = None
    reporter_submission: Optional[dict[str, Any]] = None
    closed_at: Optional[datetime] = None
    owner_id: Optional[int] = None
    asset_id: Optional[int] = None
    linked_risk_ids: Optional[str] = Field(
        None,
        description="Comma-separated enterprise risk IDs linked to this incident",
    )

    @model_validator(mode="before")
    @classmethod
    def coerce_null_updated_at(cls, data: Any) -> Any:
        """Legacy/sample rows may lack updated_at — fall back to created_at (keep OpenAPI required)."""
        if data is None:
            return data
        if isinstance(data, dict):
            if data.get("updated_at") is None and data.get("created_at") is not None:
                return {**data, "updated_at": data["created_at"]}
            return data
        updated = getattr(data, "updated_at", None)
        created = getattr(data, "created_at", None)
        if updated is None and created is not None:
            try:
                data.updated_at = created
            except Exception:
                # Read-only / SimpleNamespace without setattr — rebuild as dict of known fields
                return {
                    key: getattr(data, key, None)
                    for key in cls.model_fields
                    if hasattr(data, key) or key == "updated_at"
                } | {"updated_at": created}
        return data


class IncidentListResponse(BaseModel):
    """Schema for paginated incident list responses."""

    items: list[IncidentResponse]
    total: int
    page: int = 1
    page_size: int = 50
    pages: int = Field(..., description="Total number of pages")
