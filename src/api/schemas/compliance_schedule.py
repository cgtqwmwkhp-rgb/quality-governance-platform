"""Pydantic schemas for Compliance Schedule (Wave 1)."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.api.schemas.validators import sanitize_field
from src.domain.models.compliance_schedule import (
    ComplianceFilingStatus,
    ComplianceRecordOutcome,
    ComplianceScheduleAnchor,
)

ComplianceStatusLiteral = Literal["current", "due_soon", "overdue"]


class CatalogueTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    template_key: str
    title: str
    taxonomy_id: str
    description: Optional[str] = None
    regulatory_basis: Optional[str] = None
    frequency_months: Optional[int] = None
    frequency_days: Optional[int] = None
    anchor: ComplianceScheduleAnchor
    statutory: bool
    is_active: bool


class CatalogueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[CatalogueTemplateResponse]
    total: int


class CatalogueActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: Optional[int] = None
    next_due_date: Optional[date] = None
    last_completed_at: Optional[datetime] = None
    owner_id: Optional[int] = None


class RequirementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=255)
    taxonomy_id: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = None
    regulatory_basis: Optional[str] = Field(None, max_length=255)
    frequency_months: Optional[int] = Field(None, ge=1)
    frequency_days: Optional[int] = Field(None, ge=1)
    anchor: ComplianceScheduleAnchor = ComplianceScheduleAnchor.SCHEDULE
    statutory: bool = False
    next_due_date: date
    last_completed_at: Optional[datetime] = None
    location_id: Optional[int] = None
    owner_id: Optional[int] = None
    template_id: Optional[int] = None
    is_active: bool = True

    @field_validator("title", "taxonomy_id", "description", "regulatory_basis", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class RequirementUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    taxonomy_id: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = None
    regulatory_basis: Optional[str] = Field(None, max_length=255)
    frequency_months: Optional[int] = Field(None, ge=1)
    frequency_days: Optional[int] = Field(None, ge=1)
    anchor: Optional[ComplianceScheduleAnchor] = None
    statutory: Optional[bool] = None
    next_due_date: Optional[date] = None
    last_completed_at: Optional[datetime] = None
    location_id: Optional[int] = None
    owner_id: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("title", "taxonomy_id", "description", "regulatory_basis", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class RequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    external_id: str
    tenant_id: int
    reference_number: str
    template_id: Optional[int] = None
    location_id: Optional[int] = None
    title: str
    taxonomy_id: str
    description: Optional[str] = None
    regulatory_basis: Optional[str] = None
    frequency_months: Optional[int] = None
    frequency_days: Optional[int] = None
    anchor: ComplianceScheduleAnchor
    statutory: bool
    next_due_date: date
    last_completed_at: Optional[datetime] = None
    owner_id: Optional[int] = None
    is_active: bool
    status: Optional[ComplianceStatusLiteral] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class RequirementListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[RequirementResponse]
    total: int
    page: int
    page_size: int
    pages: int


class RecordCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_at: Optional[datetime] = None
    check_passed: Optional[bool] = None
    notes: Optional[str] = None
    evidence_asset_ids: Optional[List[int]] = None
    due_date: Optional[date] = None

    @field_validator("notes", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class RecordEvidenceAttachRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_asset_ids: List[int] = Field(..., min_length=1)


class RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    external_id: str
    tenant_id: int
    reference_number: str
    requirement_id: int
    due_date: date
    outcome: ComplianceRecordOutcome
    completed_at: Optional[datetime] = None
    check_passed: Optional[bool] = None
    notes: Optional[str] = None
    library_document_id: Optional[int] = None
    filing_status: ComplianceFilingStatus
    filing_error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class RecordListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[RecordResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ComplianceScheduleStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_active: int
    current: int
    due_soon: int
    overdue: int
