"""Pydantic schemas for Assessment API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ============== Assessment Run Schemas ==============


class AssessmentRunCreate(BaseModel):
    """Schema for creating an assessment run."""

    template_id: int
    engineer_id: int
    asset_type_id: Optional[int] = None
    asset_id: Optional[int] = None
    title: Optional[str] = Field(None, max_length=300)
    location: Optional[str] = Field(None, max_length=200)
    scheduled_date: Optional[datetime] = None
    notes: Optional[str] = None


class AssessmentRunUpdate(BaseModel):
    """Schema for updating an assessment run."""

    title: Optional[str] = Field(None, max_length=300)
    location: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(draft|in_progress|pending_debrief|completed|cancelled)$")


class AssessmentRunResponse(BaseModel):
    """Schema for assessment run response - all fields from model."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    reference_number: str
    template_id: int
    template_version: int
    engineer_id: int
    supervisor_id: int
    asset_type_id: Optional[int] = None
    asset_id: Optional[int] = None
    title: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: str
    scheduled_date: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    outcome: Optional[str] = None
    overall_notes: Optional[str] = None
    debrief_notes: Optional[str] = None
    tenant_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class AssessmentRunListResponse(BaseModel):
    """Schema for paginated assessment run list."""

    items: List[AssessmentRunResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ============== Assessment Response Schemas ==============


class AssessmentResponseCreate(BaseModel):
    """Schema for creating an assessment response."""

    question_id: int
    verdict: Optional[str] = Field(None, pattern="^(competent|not_competent|na)$")
    feedback: Optional[str] = None
    supervisor_notes: Optional[str] = None


class AssessmentResponseUpdate(BaseModel):
    """Schema for updating an assessment response."""

    verdict: Optional[str] = Field(None, pattern="^(competent|not_competent|na)$")
    feedback: Optional[str] = None
    supervisor_notes: Optional[str] = None
    engineer_signature: Optional[str] = None
    engineer_signed_at: Optional[datetime] = None


class AssessmentResponseResponse(BaseModel):
    """Schema for assessment response - all fields from model."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    question_id: int
    verdict: Optional[str] = None
    feedback: Optional[str] = None
    supervisor_notes: Optional[str] = None
    engineer_signature: Optional[str] = None
    engineer_signed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
