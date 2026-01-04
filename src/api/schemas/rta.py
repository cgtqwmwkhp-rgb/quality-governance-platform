"""Pydantic schemas for Root Cause Analysis (RTA)."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.models.rta_analysis import RCAStatus


class RTABase(BaseModel):
    """Base schema for RTA."""

    title: str = Field(..., min_length=1, max_length=300)
    problem_statement: str = Field(..., min_length=1)
    root_cause: Optional[str] = None
    corrective_actions: Optional[str] = None
    status: RCAStatus = RCAStatus.DRAFT

    @field_validator("title")
    @classmethod
    def title_must_not_be_whitespace(cls, v: str) -> str:
        """Validate title is not just whitespace."""
        if not v.strip():
            raise ValueError("Title must not be empty or whitespace")
        return v.strip()


class RTACreate(RTABase):
    """Schema for creating an RTA."""

    incident_id: int


class RTAUpdate(BaseModel):
    """Schema for updating an RTA."""

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    problem_statement: Optional[str] = None
    root_cause: Optional[str] = None
    corrective_actions: Optional[str] = None
    status: Optional[RCAStatus] = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_whitespace(cls, v: Optional[str]) -> Optional[str]:
        """Validate title is not just whitespace."""
        if v is not None and not v.strip():
            raise ValueError("Title must not be empty or whitespace")
        return v.strip() if v is not None else None


class RTAResponse(RTABase):
    """Schema for RTA response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    reference_number: str
    created_at: datetime
    updated_at: datetime


class RTAListResponse(BaseModel):
    """Schema for paginated RTA list response."""

    items: List[RTAResponse]
    total: int
    page: int
    page_size: int
