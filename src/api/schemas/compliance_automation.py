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
