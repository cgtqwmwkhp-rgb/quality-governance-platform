"""Pydantic schemas for Job Lifecycle axes (JL-1 / JL-3 / ADR-0022)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

JobCellLinkKind = Literal["app", "external", "audit_outcome", "job_cycle"]

#: Deming phase used to colour a step. Nullable everywhere — an unset phase is
#: a legitimate state, not a default of "plan".
JobStepPdcaPhase = Literal["plan", "do", "check", "act"]

#: Document freshness read from the Library / Document Control SSOT (JL-UX-W3).
#: ``unknown`` is a first-class answer — it means the SSOT holds no review date,
#: not that the document is fine.
JobDocumentFreshnessState = Literal["current", "due_soon", "overdue", "obsolete", "unknown"]

#: Audit-outcome cadence state. ``unknown`` covers ad-hoc audits and runs with
#: no cadence or due date.
JobAuditLapseState = Literal["current", "due_soon", "lapsed", "unknown"]

#: Mandatory-evidence cell readiness (JL-UX-W4). ``unknown`` means the evidence
#: exists but its standing could not be read — not that the cell is fine.
JobCellReadinessState = Literal[
    "not_required",
    "ready",
    "missing_evidence",
    "obsolete_evidence",
    "unknown",
]

#: Node / edge vocabulary shared by the process interaction map and the audit
#: trail (JL-UX-W4). One model, two views — never two edge shapes to keep in step.
JobGraphNodeKind = Literal["job_type", "cell", "document", "audit_finding", "app", "external"]
JobGraphEdgeKind = Literal["nests", "contains", "evidences", "audits", "references"]


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


class JobCellLinkAuditLapse(BaseModel):
    """Audit-lapse cue for an ``audit_outcome`` link (JL-UX-W3).

    Read-only and derived from the audit run plus its template cadence. When
    the run has neither a cadence nor a due date the state is ``unknown`` with
    a ``reason`` — the composer says so rather than implying good standing.
    """

    model_config = ConfigDict(from_attributes=True)

    state: JobAuditLapseState
    reason: str
    last_completed_at: Optional[datetime] = None
    next_due_at: Optional[datetime] = None
    frequency: Optional[str] = None
    frequency_days: Optional[int] = None


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
    #: Populated for ``audit_outcome`` links only; ``None`` everywhere else.
    audit_lapse: Optional[JobCellLinkAuditLapse] = None
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


class JobCellRequirementUpdate(BaseModel):
    """Mark a lane × step intersection as owing evidence (JL-UX-W4).

    The *requirement* is authored; the readiness verdict is not writable
    anywhere — it is derived from the cell's document refs on every read.
    """

    model_config = ConfigDict(extra="forbid")

    requires_evidence: bool


class JobCellResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    job_type_id: int
    lane_id: int
    step_id: int
    #: Default False so a payload built before W4 still validates.
    requires_evidence: bool = False
    library_document_ids: List[int] = Field(default_factory=list)
    links: List[JobCellLinkResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class JobCellListResponse(BaseModel):
    items: List[JobCellResponse]
    total: int


class JobDocumentFreshnessItem(BaseModel):
    """Freshness for one library document, projected from the document SSOT.

    Both raw statuses are echoed alongside the derived ``state`` so the UI can
    show what the SSOT actually said, rather than only this module's reading
    of it. ``found=False`` means the id is not visible to this tenant.
    """

    model_config = ConfigDict(from_attributes=True)

    library_document_id: int
    found: bool
    title: Optional[str] = None
    reference: Optional[str] = None
    library_status: Optional[str] = None
    controlled_status: Optional[str] = None
    state: JobDocumentFreshnessState
    reason: str
    review_date: Optional[datetime] = None
    is_obsolete: bool


class JobDocumentFreshnessResponse(BaseModel):
    items: List[JobDocumentFreshnessItem]
    total: int


# ---------------------------------------------------------------------------
# JL-UX-W4 — clone, readiness, and the shared map / trail graph
# ---------------------------------------------------------------------------


class JobTypeCloneRequest(BaseModel):
    """Clone a pack's axes into a new job cycle.

    Axes only. There is no ``include_cells`` or ``include_documents`` option
    because there is no honest version of one: a cell's document refs assert
    that *this* pack is evidenced by that document, and copying a template
    cannot make that claim for the new pack.
    """

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    #: Inactive axes are copied by default — a retired lane is still part of
    #: the template's shape, and dropping it silently would change the pack.
    include_inactive: bool = True


class JobTypeCloneResponse(BaseModel):
    """The new pack plus what was, and was not, copied into it."""

    job_type: JobTypeResponse
    source_job_type_id: int
    cloned_lane_count: int
    cloned_step_count: int
    #: Always zero. Returned rather than implied so the contract states it.
    cloned_cell_count: int = 0
    cloned_document_count: int = 0


class JobCellReadiness(BaseModel):
    """Whether a mandatory cell is actually satisfied. Derived on every read."""

    model_config = ConfigDict(from_attributes=True)

    state: JobCellReadinessState
    reason: str
    evidence_count: int
    obsolete_count: int
    unresolved_count: int
    is_ready: bool


class JobCellReadinessItem(BaseModel):
    """Readiness of one mandatory-evidence cell. Derived, never stored."""

    model_config = ConfigDict(from_attributes=True)

    cell_id: int
    lane_id: int
    lane_name: str
    step_id: int
    step_name: str
    requires_evidence: bool
    library_document_ids: List[int] = Field(default_factory=list)
    state: JobCellReadinessState
    reason: str
    evidence_count: int
    obsolete_count: int
    unresolved_count: int
    is_ready: bool


class JobEvidenceReadinessResponse(BaseModel):
    items: List[JobCellReadinessItem]
    total: int
    job_type_id: int
    #: Echoed back so a caller can tell a presence-only pass from an assured one.
    assure: bool
    summary: Dict[str, int] = Field(default_factory=dict)


class JobGraphNodeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    kind: JobGraphNodeKind
    ref_id: int
    label: str
    href: Optional[str] = None
    detail: Optional[str] = None


class JobGraphEdgeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    kind: JobGraphEdgeKind
    source: str
    target: str
    label: str
    href: Optional[str] = None
    cell_id: Optional[int] = None
    lane_id: Optional[int] = None
    step_id: Optional[int] = None


class JobCycleGraphResponse(BaseModel):
    """Process interaction map — a view over ``job_cycle`` cell links."""

    root_job_type_id: int
    depth: int
    #: True when nesting continues past the requested depth.
    truncated: bool
    nodes: List[JobGraphNodeModel] = Field(default_factory=list)
    edges: List[JobGraphEdgeModel] = Field(default_factory=list)


class JobAuditTrailPath(BaseModel):
    """One sampled walk: pack → cell → the evidence that cell points at."""

    cell_id: int
    lane_id: int
    lane_name: str
    step_id: int
    step_name: str
    requires_evidence: bool
    library_document_ids: List[int] = Field(default_factory=list)
    node_keys: List[str] = Field(default_factory=list)
    edge_keys: List[str] = Field(default_factory=list)
    readiness: JobCellReadiness


class JobAuditTrailResponse(BaseModel):
    root_job_type_id: int
    assure: bool
    limit: int
    #: How many cells *could* have been walked, so a sample never reads as a
    #: complete export.
    total_candidates: int
    truncated: bool
    paths: List[JobAuditTrailPath] = Field(default_factory=list)
    nodes: List[JobGraphNodeModel] = Field(default_factory=list)
    edges: List[JobGraphEdgeModel] = Field(default_factory=list)
    summary: Dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Baselines (JL-UX-W5) — snapshots, never forks
# ---------------------------------------------------------------------------


class JobTypeBaselineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Optional[str] = Field(None, max_length=200)
    note: Optional[str] = None


class JobTypeBaselineResponse(BaseModel):
    """One frozen snapshot. ``edit_targets_live`` is always true by design."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    job_type_id: int
    label: Optional[str] = None
    note: Optional[str] = None
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    snapshot: Optional[Dict[str, Any]] = None
    is_snapshot: bool = True
    edit_targets_live: bool = True
    viewing_baseline: bool = False
    banner: Optional[str] = None


class JobTypeBaselineListResponse(BaseModel):
    items: List[JobTypeBaselineResponse]
    total: int
    job_type_id: int
    edit_targets_live: bool = True


class JobTypeBaselineDiffResponse(BaseModel):
    baseline_id: int
    job_type_id: int
    viewing_baseline: bool = True
    edit_targets_live: bool = True
    banner: str
    baseline_created_at: datetime
    baseline_label: Optional[str] = None
    has_changes: bool
    summary: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    sections: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Portal nested-cycle read (JL-UX-W5)
# ---------------------------------------------------------------------------


class PortalJobNestLink(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: Literal["job_cycle"] = "job_cycle"
    label: str
    target_job_type_id: Optional[int] = None
    href: str
    sort_order: int = 0


class PortalJobCell(BaseModel):
    id: int
    lane_id: int
    step_id: int
    requires_evidence: bool = False
    library_document_ids: List[int] = Field(default_factory=list)
    nest_links: List[PortalJobNestLink] = Field(default_factory=list)


class PortalNestedCycleResponse(BaseModel):
    """Field/portal nest-aware cycle DTO. Read-only by contract."""

    job_type: JobTypeResponse
    lanes: List[JobLaneResponse] = Field(default_factory=list)
    steps: List[JobStepResponse] = Field(default_factory=list)
    cells: List[PortalJobCell] = Field(default_factory=list)
    cycle_graph: Optional[JobCycleGraphResponse] = None
    read_only: bool = True
    can_author: bool = False


__all__ = [
    "JobAuditLapseState",
    "JobAuditTrailPath",
    "JobAuditTrailResponse",
    "JobCellDocumentsPut",
    "JobCellLinkAuditLapse",
    "JobCellLinkCreate",
    "JobCellLinkKind",
    "JobCellLinkListResponse",
    "JobCellLinkResponse",
    "JobCellListResponse",
    "JobCellReadiness",
    "JobCellReadinessItem",
    "JobCellReadinessState",
    "JobCellRequirementUpdate",
    "JobCellResponse",
    "JobCycleGraphResponse",
    "JobDocumentFreshnessItem",
    "JobDocumentFreshnessResponse",
    "JobDocumentFreshnessState",
    "JobEvidenceReadinessResponse",
    "JobGraphEdgeKind",
    "JobGraphEdgeModel",
    "JobGraphNodeKind",
    "JobGraphNodeModel",
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
    "JobTypeBaselineCreate",
    "JobTypeBaselineDiffResponse",
    "JobTypeBaselineListResponse",
    "JobTypeBaselineResponse",
    "JobTypeCloneRequest",
    "JobTypeCloneResponse",
    "JobTypeCreate",
    "JobTypeListResponse",
    "JobTypeResponse",
    "JobTypeUpdate",
    "PortalJobCell",
    "PortalJobNestLink",
    "PortalNestedCycleResponse",
]
