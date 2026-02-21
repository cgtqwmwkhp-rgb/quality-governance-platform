"""Auditor Competence API Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AuditorProfileCreateResponse(BaseModel):
    id: int
    user_id: int
    competence_level: str
    created_at: datetime


class AuditorProfileResponse(BaseModel):
    id: int
    user_id: int
    job_title: Optional[str] = None
    department: Optional[str] = None
    competence_level: str
    years_audit_experience: float
    total_audits_conducted: int
    total_audits_as_lead: int
    specializations: Optional[List[str]] = None
    competence_score: Optional[float] = None
    is_available: bool
    is_active: bool


class AuditorProfileUpdateResponse(BaseModel):
    id: int
    user_id: int
    updated: bool


class CompetenceScoreResponse(BaseModel):
    user_id: int
    competence_score: float


class CertificationCreateResponse(BaseModel):
    id: int
    certification_name: str
    status: str
    expiry_date: Optional[datetime] = None


class CertificationItem(BaseModel):
    id: int
    certification_name: str
    certification_body: str
    standard_code: Optional[str] = None
    status: str
    issued_date: datetime
    expiry_date: Optional[datetime] = None
    days_until_expiry: Optional[int] = None
    is_valid: bool


class CertificationListResponse(BaseModel):
    user_id: int
    certifications: List[CertificationItem]


class ExpiringCertificationsResponse(BaseModel):
    days_ahead: int
    expiring_count: int
    certifications: List[Any]


class ExpiredCertificationsUpdateResponse(BaseModel):
    updated_count: int
    message: str


class TrainingCreateResponse(BaseModel):
    id: int
    training_name: str
    completed: bool


class TrainingCompleteResponse(BaseModel):
    id: int
    completed: bool
    completion_date: datetime
    assessment_passed: Optional[bool] = None


class CompetencyAssessmentResponse(BaseModel):
    id: int
    competency_area_id: int
    current_level: int
    last_assessed: datetime


class CompetencyGapsResponse(BaseModel):
    user_id: int
    gap_count: int
    gaps: List[Any]


class QualifiedAuditorsResponse(BaseModel):
    audit_type: str
    total_auditors: int
    qualified_count: int
    qualified_auditors: List[Any]
    not_qualified_auditors: List[Any]


class CompetenceDashboardResponse(BaseModel):
    model_config = {"extra": "allow"}
