"""Pydantic schemas for Assessment API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ============== Assessment Run Schemas ==============


class AssessmentPlantEvidence(BaseModel):
    """Which machine a demonstration happened on (CB-UI-3).

    Evidence only. Every field is optional and none of them is a competence
    claim: a serial number does not issue anything and an absent make does not
    invalidate the assessment. Make and model are recorded here as free text
    rather than looked up, because a validated OEM catalogue is CB-OEM's
    problem and inventing one would make this column pretend to be a registry.
    """

    model_config = ConfigDict(extra="forbid")

    # ``default=`` as a keyword, not a positional: PEP 681 only treats a field
    # specifier as defaulted when it is spelled this way, so ``Field(None, ...)``
    # leaves the field looking required to a type checker even though pydantic
    # defaults it at runtime.
    make: Optional[str] = Field(default=None, max_length=120)
    model: Optional[str] = Field(default=None, max_length=120)
    serial: Optional[str] = Field(default=None, max_length=120)
    pams_plant_id: Optional[str] = Field(default=None, max_length=120)


class AssessmentRunCreate(BaseModel):
    """Schema for creating an assessment run.

    ``extra="forbid"`` so a misspelled or unsupported field fails loudly instead
    of the run being created while the unknown key is silently dropped (B-10).
    """

    model_config = ConfigDict(extra="forbid")

    template_id: int
    engineer_id: int
    asset_type_id: Optional[int] = None
    asset_id: Optional[int] = None
    # ``default=`` spelled as a keyword — see AssessmentPlantEvidence above. This
    # is the first in-``src`` caller of this schema (CB-UI-3's start endpoint),
    # which is what surfaced it: omitting `location` was a mypy error.
    title: Optional[str] = Field(default=None, max_length=300)
    location: Optional[str] = Field(default=None, max_length=200)
    scheduled_date: Optional[datetime] = None
    notes: Optional[str] = None
    plant_evidence: Optional[AssessmentPlantEvidence] = None


class AssessmentRunUpdate(BaseModel):
    """Schema for updating an assessment run.

    ``extra="forbid"`` so a misspelled or unsupported field fails loudly instead
    of the run being updated while the unknown key is silently dropped (B-10).
    """

    model_config = ConfigDict(extra="forbid")

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
    # Deliberately a plain dict on the way out while the request side is the
    # strict ``AssessmentPlantEvidence``. Strict in, tolerant out: this reads a
    # JSON column, and a run whose stored evidence predates or outlives the
    # current field set must still be readable rather than 500 on serialisation.
    # Writes go through ``normalise_plant_evidence``, so nothing QGP stores can
    # hold a key the request model would have refused.
    plant_evidence: Optional[dict] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: str
    scheduled_date: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    outcome: Optional[str] = None
    overall_notes: Optional[str] = None
    debrief_notes: Optional[str] = None
    debrief_signature: Optional[str] = None
    debrief_signed_at: Optional[datetime] = None
    responses: List["AssessmentResponseResponse"] = []
    tenant_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    # Soft competency-gate warning fields (set on /start when mode=soft and not cleared)
    competency_gate_cleared: Optional[bool] = None
    competency_gate_reason: Optional[str] = None
    competency_gate_mode: Optional[str] = None


class AssessmentRunListResponse(BaseModel):
    """Schema for paginated assessment run list."""

    items: List[AssessmentRunResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ============== Assessment Response Schemas ==============


class AssessmentResponseCreate(BaseModel):
    """Schema for creating an assessment response.

    ``extra="forbid"`` so a misspelled or unsupported field fails loudly instead
    of the response being saved while the unknown key is silently dropped (B-10).
    """

    model_config = ConfigDict(extra="forbid")

    question_id: int
    verdict: Optional[str] = Field(None, pattern="^(competent|not_competent|na)$")
    feedback: Optional[str] = None
    supervisor_notes: Optional[str] = None


class AssessmentResponseUpdate(BaseModel):
    """Schema for updating an assessment response.

    ``extra="forbid"`` so a misspelled or unsupported field fails loudly instead
    of the response being updated while the unknown key is silently dropped (B-10).
    """

    model_config = ConfigDict(extra="forbid")

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


AssessmentRunResponse.model_rebuild()
