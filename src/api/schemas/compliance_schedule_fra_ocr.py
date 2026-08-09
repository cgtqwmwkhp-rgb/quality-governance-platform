"""Pydantic schemas for Compliance Schedule FRA / PAS 79 OCR ingest."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.api.schemas.compliance_schedule import RequirementResponse
from src.api.schemas.validators import sanitize_field

FraFieldConfidence = Literal["high", "medium", "none"]
FraRiskVocabulary = Literal["pas79", "lmh"]
FraActionPriority = Literal["high", "medium", "low"]


class FraExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Optional[str] = None
    confidence: FraFieldConfidence = "none"
    evidence_snippet: Optional[str] = Field(default=None, max_length=200)


class FraProposedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=0)
    source_ref: Optional[str] = Field(default=None, max_length=20)
    text: str = Field(..., min_length=1, max_length=2000)
    priority_raw: Optional[str] = Field(default=None, max_length=40)
    priority_normalised: Optional[FraActionPriority] = None
    target_date: Optional[date] = None
    target_date_raw: Optional[str] = Field(default=None, max_length=60)
    confidence: FraFieldConfidence = "none"
    needs_review: bool = False


class FraProposedFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_date: FraExtractedField = Field(default_factory=lambda: FraExtractedField())
    next_review_date: FraExtractedField = Field(default_factory=lambda: FraExtractedField())
    review_interval_months: FraExtractedField = Field(default_factory=lambda: FraExtractedField())
    assessor_name: FraExtractedField = Field(default_factory=lambda: FraExtractedField())
    assessor_organisation: FraExtractedField = Field(default_factory=lambda: FraExtractedField())
    premises_name: FraExtractedField = Field(default_factory=lambda: FraExtractedField())
    pas79_reference: FraExtractedField = Field(default_factory=lambda: FraExtractedField())
    overall_risk_rating: FraExtractedField = Field(default_factory=lambda: FraExtractedField())
    risk_vocabulary: Optional[FraRiskVocabulary] = None


class FraOcrAppliedSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: int
    next_due_date_before: date
    next_due_date_after: date
    actions_recorded: int
    actions_created: int = 0  # >0 only when COMPLIANCE_SCHEDULE_FRA_OCR_ACTIONS_ENABLED
    risks_created: int = 0  # >0 only when COMPLIANCE_SCHEDULE_FRA_OCR_RISK_ENABLED + operator scores
    changed_fields: List[str]
    warnings: List[str] = Field(default_factory=list)


class FraOcrDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    external_id: str
    tenant_id: int
    requirement_id: int
    purpose: Literal["fra_pas79"]
    status: Literal["pending", "confirmed", "discarded"]
    source_filename: Optional[str] = None
    source_size_bytes: Optional[int] = None
    source_checksum_sha256: str
    evidence_asset_id: Optional[int] = None
    extraction_method: Optional[str] = None
    ocr_provider_status: Optional[str] = None
    page_count: Optional[int] = None
    proposed: FraProposedFields
    proposed_actions: List[FraProposedAction] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    confirmed_at: Optional[datetime] = None
    confirmed_by_id: Optional[int] = None
    applied: Optional[FraOcrAppliedSummary] = None
    library_document_id: Optional[int] = None
    filing_status: Literal["not_filed", "filed", "filing_failed"]
    filing_error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class FraOcrFromEvidenceRequest(BaseModel):
    """Create a pending FRA OCR draft from an occurrence evidence PDF already stored."""

    model_config = ConfigDict(extra="forbid")

    evidence_asset_id: int = Field(..., ge=1)


class FraOcrDraftListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[FraOcrDraftResponse]
    total: int
    page: int
    page_size: int
    pages: int


class FraOcrConfirmedAction(BaseModel):
    """One action the human chose to keep, as they left it."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=0)
    text: str = Field(..., min_length=1, max_length=2000)
    priority_normalised: Optional[FraActionPriority] = None
    target_date: Optional[date] = None

    @field_validator("text", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class FraOcrRiskProposal(BaseModel):
    """Operator-entered risk proposal at confirm time.

    Likelihood and impact are required when this object is present — OCR never
    invents scores. Absent ``risk`` on the confirm body means no risk row.
    """

    model_config = ConfigDict(extra="forbid")

    inherent_likelihood: int = Field(..., ge=1, le=5)
    inherent_impact: int = Field(..., ge=1, le=5)
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=4000)

    @field_validator("title", "description", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class FraOcrDraftConfirmRequest(BaseModel):
    """The human gate. Nothing on the requirement moves without this body.

    ``next_due_date`` is required and is *not* defaulted from the parse: a
    field the operator did not have to look at is not a gate. The proposal is
    shown to them; what they send back is what is written.
    """

    model_config = ConfigDict(extra="forbid")

    next_due_date: date
    acknowledged_warnings: bool = False
    actions: List[FraOcrConfirmedAction] = Field(default_factory=list, max_length=200)
    note: Optional[str] = Field(default=None, max_length=1000)
    risk: Optional[FraOcrRiskProposal] = None

    @field_validator("note", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class FraOcrConfirmResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: FraOcrDraftResponse
    requirement: RequirementResponse
    applied: FraOcrAppliedSummary


class FraOcrFileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: int = Field(..., ge=1)
    # Owning function for the PEL reference (ADR-0023) — a different axis from
    # category_id. Omitted means "not yet confirmed": the document is filed
    # with no PEL reference rather than one derived from the category. An FRA
    # sits on the HSEQ/FAC boundary, so it is not safe to infer.
    function_code: Optional[str] = Field(default=None, min_length=1, max_length=20)
    # Cascade level 1-5 (NS-1) — the band the PEL reference is drawn from.
    # Required alongside function_code: an FRA is a level-4 assessment, but the
    # band is baked into an immutable reference, so it is confirmed by the
    # filer rather than assumed here.
    cascade_level: Optional[int] = Field(default=None, ge=1, le=5)
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)

    @field_validator("title", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)

    @model_validator(mode="after")
    def _level_required_with_function(self) -> "FraOcrFileRequest":
        if self.function_code is not None and self.cascade_level is None:
            raise ValueError("cascade_level is required when function_code is supplied (NS-1 banded PEL reference)")
        return self


class FraOcrFilingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: FraOcrDraftResponse
    library_document_id: int
    pel_doc_ref: Optional[str] = None
    duplicate_warning: bool = False
    duplicate_warning_detail: Optional[List[dict]] = None
    index_job_id: Optional[int] = None


class FraOcrDiscardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Optional[str] = Field(default=None, max_length=500)
