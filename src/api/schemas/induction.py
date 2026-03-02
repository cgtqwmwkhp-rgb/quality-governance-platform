"""Pydantic schemas for Induction API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============== Induction Run Schemas ==============


class InductionRunCreate(BaseModel):
    """Schema for creating an induction run."""

    template_id: int
    engineer_id: int
    asset_type_id: Optional[int] = None
    title: Optional[str] = Field(None, max_length=300)
    location: Optional[str] = Field(None, max_length=200)
    stage: str = Field(default="stage_1_onsite", pattern="^(stage_1_onsite|stage_2_field)$")
    scheduled_date: Optional[datetime] = None
    notes: Optional[str] = None


class InductionRunUpdate(BaseModel):
    """Schema for updating an induction run."""

    title: Optional[str] = Field(None, max_length=300)
    location: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None
    stage: Optional[str] = Field(None, pattern="^(stage_1_onsite|stage_2_field)$")
    status: Optional[str] = Field(None, pattern="^(draft|in_progress|completed|cancelled)$")


class InductionRunResponse(BaseModel):
    """Schema for induction run response - all fields from model."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    reference_number: str
    template_id: int
    template_version: int
    engineer_id: int
    supervisor_id: int
    asset_type_id: Optional[int] = None
    title: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    stage: str
    status: str
    scheduled_date: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_items: int
    competent_count: int
    not_yet_competent_count: int
    tenant_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class InductionRunListResponse(BaseModel):
    """Schema for paginated induction run list."""

    items: List[InductionRunResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ============== Induction Response Schemas ==============


class InductionResponseCreate(BaseModel):
    """Schema for creating an induction response."""

    question_id: int
    shown_explained: bool = False
    understanding: Optional[str] = Field(None, pattern="^(competent|not_yet_competent|na)$")
    supervisor_notes: Optional[str] = None


class InductionResponseUpdate(BaseModel):
    """Schema for updating an induction response."""

    shown_explained: Optional[bool] = None
    understanding: Optional[str] = Field(None, pattern="^(competent|not_yet_competent|na)$")
    supervisor_notes: Optional[str] = None
    engineer_signature: Optional[str] = None
    engineer_signed_at: Optional[datetime] = None


class InductionResponseResponse(BaseModel):
    """Schema for induction response - all fields from model."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    question_id: int
    shown_explained: bool
    understanding: Optional[str] = None
    supervisor_notes: Optional[str] = None
    engineer_signature: Optional[str] = None
    engineer_signed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
