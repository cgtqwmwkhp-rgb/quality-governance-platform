"""Compliance Automation Pydantic schemas."""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _as_utc(value: datetime) -> datetime:
    """Comparable instant for a date that may or may not carry an offset.

    Pydantic parses each field independently, so ``2026-01-01`` arrives naive
    while ``2027-01-01T00:00:00Z`` arrives aware; comparing the two directly
    raises ``TypeError`` and would surface as a 500 from inside a validator. A
    naive value is read as UTC because that is how every reader of the
    ``certificates`` columns interprets one.

    This is for comparison only. Normalising the values that get stored belongs
    to the writer, which is the layer that knows the column type.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class RegulatoryUpdateResponse(BaseModel):
    updates: list[dict]
    total: int
    unreviewed: int


class ReviewUpdateResponse(BaseModel):
    update_id: int
    reviewed: bool
    requires_action: bool

    class Config:
        from_attributes = True


class GapAnalysisResponse(BaseModel):
    id: int
    status: Optional[str] = None
    gaps: list[dict] = []

    class Config:
        from_attributes = True


class GapAnalysisListResponse(BaseModel):
    analyses: list[dict]
    total: int


class CertificateListResponse(BaseModel):
    certificates: list[dict]
    total: int


class CertificateCreate(BaseModel):
    """Body of ``POST /compliance-automation/certificates``.

    Every field is named for the ``Certificate`` column it writes. The previous
    version of this schema named ``issued_by`` / ``issued_date``, which match no
    column and no caller: the register stores ``issuing_body`` / ``issue_date``,
    and the frontend client has always sent those. Because no route ever accepted
    this body, the mismatch was invisible rather than harmless — wiring it up as
    written would have dropped the issuer and the issue date on every write
    (PX-427).

    ``extra="forbid"`` so an unrecognised field is a 422 rather than a silent
    discard, which is the PX-168 shape the write-contract guards exist to stop.

    ``issue_date`` and ``expiry_date`` are required because both columns are NOT
    NULL, and an undated certificate is the specific thing the framework
    countdown cannot report on.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    certificate_type: str = Field(min_length=1, max_length=50)
    reference_number: Optional[str] = Field(default=None, max_length=100)
    entity_type: str = Field(min_length=1, max_length=50)
    #: Scoping key inside the tenant (a person, asset or site). Omitted for an
    #: organisation-level accreditation, where the tenant itself is the entity
    #: and the server supplies its id — a client has no reason to know it.
    entity_id: Optional[str] = Field(default=None, max_length=36)
    entity_name: Optional[str] = Field(default=None, max_length=255)
    issuing_body: Optional[str] = Field(default=None, max_length=255)
    issue_date: datetime
    expiry_date: datetime
    reminder_days: int = Field(default=30, ge=0, le=365)
    is_critical: bool = False
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _expiry_not_before_issue(self) -> "CertificateCreate":
        """Refuse a certificate that expires before it was issued.

        The register exists to be read as a countdown, and a negative validity
        period renders as an already-expired credential nobody can account for.
        """
        if _as_utc(self.expiry_date) < _as_utc(self.issue_date):
            raise ValueError("expiry_date must not be earlier than issue_date")
        return self


class ScheduledAuditListResponse(BaseModel):
    audits: list[dict]
    total: int


class AuditScheduleCreate(BaseModel):
    audit_type: str
    title: str
    scheduled_date: Optional[datetime] = None
    assigned_to: Optional[str] = None
    scope: Optional[str] = None
    notes: Optional[str] = None


class ComplianceScoreResponse(BaseModel):
    overall_score: float = 0.0
    scope_type: str
    scope_id: Optional[str] = None
    breakdown: dict = {}

    class Config:
        from_attributes = True


class ComplianceTrendResponse(BaseModel):
    trend: list[dict]
    period_months: int


class RIDDORSubmissionListResponse(BaseModel):
    submissions: list[dict]
    total: int


class RIDDORCheckRequest(BaseModel):
    incident_type: str
    severity: Optional[str] = None
    injury_type: Optional[str] = None
    days_absent: Optional[int] = None
    is_fatal: bool = False
    description: Optional[str] = None


class RIDDORCheckResponse(BaseModel):
    required: bool
    riddor_type: Optional[str] = None
    reason: Optional[str] = None
    deadline_days: Optional[int] = None


class RIDDORPrepareResponse(BaseModel):
    submission_data: dict = {}
    riddor_type: str
    incident_id: int


class RIDDORSubmitResponse(BaseModel):
    submission_id: Optional[int] = None
    status: str
    submitted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CertificateExpirySummaryResponse(BaseModel):
    total_certificates: int = 0
    expiring_30_days: int = 0
    expiring_60_days: int = 0
    expiring_90_days: int = 0
    expired: int = 0


class ReviewRegulatoryUpdateResponse(BaseModel):
    id: int
    source: str
    source_reference: str
    source_url: Optional[str] = None
    title: str
    summary: Optional[str] = None
    full_text: Optional[str] = None
    category: str
    subcategory: Optional[str] = None
    tags: Optional[Any] = None
    impact: str
    affected_standards: Optional[Any] = None
    affected_clauses: Optional[Any] = None
    published_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    detected_at: Optional[datetime] = None
    is_reviewed: bool
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    requires_action: bool
    action_notes: Optional[str] = None


class RunGapAnalysisResponse(BaseModel):
    id: int
    regulatory_update_id: Optional[int] = None
    standard_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    gaps: Any
    total_gaps: int
    critical_gaps: int
    high_gaps: int
    recommendations: Optional[Any] = None
    estimated_effort_hours: Optional[int] = None
    status: str
    assigned_to: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AddCertificateResponse(BaseModel):
    id: int
    name: str
    certificate_type: str
    reference_number: Optional[str] = None
    entity_type: str
    entity_id: str
    entity_name: Optional[str] = None
    issuing_body: Optional[str] = None
    issue_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    reminder_days: int = 30
    reminder_sent: bool = False
    reminder_sent_at: Optional[datetime] = None
    status: str = "valid"
    is_critical: bool = False
    primary_evidence_asset_id: Optional[int] = None
    document_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ScheduleAuditResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    audit_type: str
    template_id: Optional[int] = None
    frequency: str
    schedule_config: Optional[Any] = None
    next_due_date: Optional[datetime] = None
    last_completed_date: Optional[datetime] = None
    assigned_to: Optional[int] = None
    department: Optional[str] = None
    standard_ids: Optional[Any] = None
    reminder_days_before: int = 7
    reminder_sent: bool = False
    is_active: bool = True
    created_at: Optional[datetime] = None
    created_by: Optional[int] = None
    standards: list[Any] = []
    status: str = "scheduled"


class PrepareRIDDORSubmissionResponse(BaseModel):
    id: int
    incident_id: int
    riddor_type: str
    hse_reference: Optional[str] = None
    submission_status: str
    submission_data: Optional[Any] = None
    submitted_at: Optional[datetime] = None
    submitted_by: Optional[int] = None
    hse_response: Optional[Any] = None
    hse_response_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    is_overdue: bool = False
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class SubmitRIDDORResponse(BaseModel):
    id: int
    incident_id: int
    riddor_type: str
    hse_reference: Optional[str] = None
    submission_status: str
    submission_data: Optional[Any] = None
    submitted_at: Optional[datetime] = None
    submitted_by: Optional[int] = None
    hse_response: Optional[Any] = None
    hse_response_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    is_overdue: bool = False
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
