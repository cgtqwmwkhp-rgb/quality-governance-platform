"""Pydantic schemas for Complaint API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.domain.models.complaint import ComplaintPriority, ComplaintStatus, ComplaintType


class ComplaintBase(BaseModel):
    """Base schema for complaints."""

    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1)
    complaint_type: ComplaintType = ComplaintType.OTHER
    priority: ComplaintPriority = ComplaintPriority.MEDIUM
    received_date: datetime
    complainant_name: str = Field(..., min_length=1, max_length=200)
    complainant_email: Optional[EmailStr] = None
    complainant_phone: Optional[str] = Field(None, max_length=30)
    complainant_company: Optional[str] = Field(None, max_length=200)
    related_reference: Optional[str] = Field(None, max_length=100)

    @field_validator("title", "complainant_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip whitespace from string fields."""
        return v.strip()

    @field_validator("title", "complainant_name")
    @classmethod
    def non_empty(cls, v: str) -> str:
        """Ensure string fields are not empty after stripping."""
        if not v:
            raise ValueError("Field cannot be empty or whitespace only")
        return v


class ComplaintCreate(ComplaintBase):
    """Schema for creating a complaint."""

    pass


class ComplaintUpdate(BaseModel):
    """Schema for updating a complaint."""

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = Field(None, min_length=1)
    complaint_type: Optional[ComplaintType] = None
    priority: Optional[ComplaintPriority] = None
    status: Optional[ComplaintStatus] = None
    investigation_notes: Optional[str] = None
    root_cause: Optional[str] = None
    resolution_summary: Optional[str] = None
    customer_satisfied: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from title."""
        if v is not None:
            return v.strip()
        return v


class ComplaintResponse(ComplaintBase):
    """Schema for complaint response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str
    status: ComplaintStatus
    created_at: datetime
    updated_at: datetime


class ComplaintListResponse(BaseModel):
    """Schema for paginated complaint list response."""

    items: List[ComplaintResponse]
    total: int
    page: int
    page_size: int
