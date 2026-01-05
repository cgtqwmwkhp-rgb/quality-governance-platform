"""Incident API schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

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


class IncidentCreate(IncidentBase):
    """Schema for creating a new incident."""

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        """Validate title is not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Title cannot be empty or whitespace")
        return v.strip()


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

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Validate title is not empty or whitespace if provided."""
        if v is not None and (not v or not v.strip()):
            raise ValueError("Title cannot be empty or whitespace")
        return v.strip() if v else None


class IncidentResponse(IncidentBase):
    """Schema for incident responses."""

    id: int
    reference_number: str
    reported_date: datetime
    created_at: datetime
    updated_at: datetime
    reporter_id: Optional[int] = None
    investigator_id: Optional[int] = None
    closed_at: Optional[datetime] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class IncidentListResponse(BaseModel):
    """Schema for paginated incident list responses."""

    items: list[IncidentResponse]
    total: int
    page: int = 1
    page_size: int = 50
    pages: int = Field(..., description="Total number of pages")
