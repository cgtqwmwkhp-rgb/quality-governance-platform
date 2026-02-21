"""Compliance Automation Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


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
    certificate_type: str
    entity_type: str
    entity_id: Optional[str] = None
    name: str
    issued_by: Optional[str] = None
    issued_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    notes: Optional[str] = None


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
