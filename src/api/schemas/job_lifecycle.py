"""Pydantic schemas for Job Lifecycle axes (JL-1 / JL-3 / ADR-0022)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

JobCellLinkKind = Literal["app", "external", "audit_outcome", "job_cycle"]

#: Deming phase used to colour a step. Nullable everywhere — an unset phase is
#: a legitimate state, not a default of "plan".
JobStepPdcaPhase = Literal["plan", "do", "check", "act"]


class JobTypeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class JobTypeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class JobTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    code: str
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class JobTypeListResponse(BaseModel):
    items: List[JobTypeResponse]
    total: int


class JobLaneCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class JobLaneUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class JobLaneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    job_type_id: int
    code: str
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class JobLaneListResponse(BaseModel):
    items: List[JobLaneResponse]
    total: int


class JobStepCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    pdca_phase: Optional[JobStepPdcaPhase] = None


class JobStepUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    #: Send an explicit ``null`` to clear the phase. Omitting the key leaves it
    #: alone — the two are told apart via ``model_fields_set``, not a companion
    #: flag, so nothing write-only leaks into the wire contract.
    pdca_phase: Optional[JobStepPdcaPhase] = None


class JobStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    job_type_id: int
    code: str
    name: str
    description: Optional[str] = None
    sort_order: int
    is_active: bool
    pdca_phase: Optional[JobStepPdcaPhase] = None
    created_at: datetime
    updated_at: datetime


class JobStepListResponse(BaseModel):
    items: List[JobStepResponse]
    total: int


class JobCellDocumentsPut(BaseModel):
    """Replace the cell's ``library_document_id[]`` membership."""

    model_config = ConfigDict(extra="forbid")

    library_document_ids: List[int] = Field(default_factory=list)


class JobCellLinkCreate(BaseModel):
    """Create a cell hyperlink. App / audit hrefs resolved via href_registry."""

    model_config = ConfigDict(extra="forbid")

    kind: JobCellLinkKind
    label: str = Field(..., min_length=1, max_length=300)
    entity_type: Optional[str] = Field(None, min_length=1, max_length=64)
    entity_id: Optional[int] = Field(None, gt=0)
    external_url: Optional[str] = Field(None, min_length=1, max_length=2000)
    audit_run_id: Optional[int] = Field(None, gt=0)
    audit_finding_id: Optional[int] = Field(None, gt=0)
    target_job_type_id: Optional[int] = Field(None, gt=0)
    sort_order: int = 0

    @field_validator("external_url")
    @classmethod
    def _https_external(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        parsed = urlparse(cleaned)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("external_url must be an absolute http(s) URL")
        return cleaned

    @field_validator("entity_type")
    @classmethod
    def _normalise_entity_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("entity_type must be non-empty")
        return cleaned

    @model_validator(mode="after")
    def _kind_fields(self) -> "JobCellLinkCreate":
        if self.kind == "app":
            if not self.entity_type or self.entity_id is None:
                raise ValueError("app links require entity_type and entity_id")
            if self.external_url or self.audit_run_id or self.audit_finding_id:
                raise ValueError("app links must not set external_url or audit_*")
            if self.target_job_type_id is not None:
                raise ValueError("app links must not set target_job_type_id")
        elif self.kind == "external":
            if not self.external_url:
                raise ValueError("external links require external_url")
            if self.entity_type or self.entity_id is not None:
                raise ValueError("external links must not set entity_*")
            if self.audit_run_id or self.audit_finding_id:
                raise ValueError("external links must not set audit_*")
            if self.target_job_type_id is not None:
                raise ValueError("external links must not set target_job_type_id")
        elif self.kind == "audit_outcome":
            if self.audit_run_id is None or self.audit_finding_id is None:
                raise ValueError("audit_outcome links require audit_run_id and audit_finding_id")
            if self.entity_type or self.entity_id is not None or self.external_url:
                raise ValueError("audit_outcome links must not set entity_* or external_url")
            if self.target_job_type_id is not None:
                raise ValueError("audit_outcome links must not set target_job_type_id")
        elif self.kind == "job_cycle":
            if self.target_job_type_id is None:
                raise ValueError("job_cycle links require target_job_type_id")
            if self.entity_type or self.entity_id is not None or self.external_url:
                raise ValueError("job_cycle links must not set entity_* or external_url")
            if self.audit_run_id or self.audit_finding_id:
                raise ValueError("job_cycle links must not set audit_*")
        return self


class JobCellLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    cell_id: int
    kind: JobCellLinkKind
    label: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    external_url: Optional[str] = None
    audit_run_id: Optional[int] = None
    audit_finding_id: Optional[int] = None
    target_job_type_id: Optional[int] = None
    href: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


class JobCellLinkListResponse(BaseModel):
    items: List[JobCellLinkResponse]
    total: int


class JobLinkEntityTypesResponse(BaseModel):
    """Entity types the ``app`` link picker may offer.

    Sourced from ``href_registry`` so the composer dropdown cannot drift from
    the builders that actually resolve the hrefs.
    """

    items: List[str]
    total: int


class JobCellResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    job_type_id: int
    lane_id: int
    step_id: int
    library_document_ids: List[int] = Field(default_factory=list)
    links: List[JobCellLinkResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class JobCellListResponse(BaseModel):
    items: List[JobCellResponse]
    total: int


__all__ = [
    "JobCellDocumentsPut",
    "JobCellLinkCreate",
    "JobCellLinkKind",
    "JobCellLinkListResponse",
    "JobCellLinkResponse",
    "JobCellListResponse",
    "JobCellResponse",
    "JobLaneCreate",
    "JobLaneListResponse",
    "JobLaneResponse",
    "JobLaneUpdate",
    "JobLinkEntityTypesResponse",
    "JobStepCreate",
    "JobStepListResponse",
    "JobStepPdcaPhase",
    "JobStepResponse",
    "JobStepUpdate",
    "JobTypeCreate",
    "JobTypeListResponse",
    "JobTypeResponse",
    "JobTypeUpdate",
]
