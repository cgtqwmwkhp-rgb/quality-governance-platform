"""Schemas for portal fire-drill capture (Wave 3)."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.api.schemas.validators import sanitize_field

ComplianceStatusLiteral = Literal["current", "due_soon", "overdue"]


class PortalFireDrillItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    reference_number: str
    next_due_date: date
    status: Optional[ComplianceStatusLiteral] = None
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    owner_id: Optional[int] = None
    last_completed_at: Optional[datetime] = None


class PortalFireDrillListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[PortalFireDrillItem]
    total: int
    evidence_capture_supported: bool = False


class PortalFireDrillCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_at: Optional[datetime] = None
    check_passed: Optional[bool] = None
    notes: Optional[str] = None
    evidence_asset_ids: Optional[List[int]] = Field(default=None)
    due_date: Optional[date] = None

    @field_validator("notes", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class PortalFireDrillCompleteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    reference_number: str
    requirement_id: int
    due_date: date
    completed_at: Optional[datetime] = None
    check_passed: Optional[bool] = None
    notes: Optional[str] = None
