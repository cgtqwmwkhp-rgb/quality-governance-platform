"""Pydantic schemas for Compliance Schedule (Wave 1)."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class RecordFileRequest(BaseModel):
    """Body for the explicit Library filing step (ADR-0020).

    Exactly one mode per request:

    * ``evidence_asset_id`` + ``category_id`` — copy an evidence asset already
      attached to this occurrence into the Governance Library as a new draft
      document under that taxonomy category.
    * ``library_document_id`` — point the occurrence at a document that is
      already in the Library.

    The two are mutually exclusive rather than merged into one optional-field
    soup because they authorise differently: one creates a document, the other
    exposes an existing one. A request that supplies both is a caller who has
    not decided which they meant, and guessing for them would file something.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_asset_id: Optional[int] = Field(None, ge=1)
    category_id: Optional[int] = Field(None, ge=1)
    library_document_id: Optional[int] = Field(None, ge=1)
    title: Optional[str] = Field(None, min_length=1, max_length=500)

    @field_validator("title", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)

    @model_validator(mode="after")
    def _exactly_one_mode(self) -> "RecordFileRequest":
        if (self.evidence_asset_id is None) == (self.library_document_id is None):
            raise ValueError("Provide exactly one of evidence_asset_id or library_document_id")
        if self.evidence_asset_id is not None and self.category_id is None:
            raise ValueError("category_id is required when filing an evidence asset")
        if self.library_document_id is not None and self.category_id is not None:
            raise ValueError("category_id does not apply when linking an existing library document")
        if self.library_document_id is not None and self.title is not None:
            raise ValueError("title does not apply when linking an existing library document")
        return self


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


class RecordFilingResponse(BaseModel):
    """Outcome of one filing attempt.

    Returns the updated occurrence so the caller needs no second read, plus the
    parts of the outcome the occurrence has nowhere to hold: the allocated PEL
    reference, and whether the Library already holds an approved document that
    looks like this one. A duplicate does not block the filing — the occurrence
    is still filed — so the warning has to travel back with the response or it
    is lost.
    """

    model_config = ConfigDict(extra="forbid")

    record: RecordResponse
    library_document_id: int
    pel_doc_ref: Optional[str] = None
    linked_existing: bool
    duplicate_warning: bool = False
    duplicate_warning_detail: Optional[List[dict]] = None


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
