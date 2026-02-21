from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# ============================================================================
# Protocol / Section endpoints
# ============================================================================


class ProtocolScoringDescription(BaseModel):
    """Scoring levels 0-3."""

    model_config = {"extra": "allow"}


class ProtocolResponse(BaseModel):
    protocol_name: str
    version: str
    reference: str
    description: str
    sections: List[Any]
    total_sections: int
    scoring: Dict[str, str]
    iso_cross_mapping: Dict[str, str]


class SectionSummaryItem(BaseModel):
    number: str
    title: str
    max_score: int
    question_count: int
    iso_mapping: Dict[str, Any] = {}


class ListSectionsResponse(BaseModel):
    total_sections: int
    sections: List[SectionSummaryItem]


class GetSectionQuestionsResponse(BaseModel):
    section_number: str
    section_title: str
    max_score: int
    iso_mapping: Dict[str, Any] = {}
    questions: List[Any] = []


# ============================================================================
# Audit management endpoints
# ============================================================================


class AuditListItem(BaseModel):
    id: int
    audit_reference: Optional[str] = None
    company_name: str
    audit_type: Optional[str] = None
    audit_date: Optional[str] = None
    status: Optional[str] = None
    percentage_score: Optional[float] = None
    lead_auditor: Optional[str] = None


class ListAuditsResponse(BaseModel):
    items: List[AuditListItem]
    total: int
    page: int
    page_size: int
    pages: int


class CreateAuditResponse(BaseModel):
    id: int
    audit_reference: str
    message: str


class CertificationsDetail(BaseModel):
    iso_9001: Optional[bool] = None
    iso_14001: Optional[bool] = None
    iso_45001: Optional[bool] = None
    iso_27001: Optional[bool] = None
    ukas_accredited: Optional[bool] = None


class GetAuditResponse(BaseModel):
    id: int
    audit_reference: Optional[str] = None
    company_name: str
    company_id: Optional[str] = None
    audit_type: Optional[str] = None
    audit_scope: Optional[str] = None
    audit_date: Optional[str] = None
    status: Optional[str] = None
    lead_auditor: Optional[str] = None
    total_score: Optional[float] = None
    percentage_score: Optional[float] = None
    section_scores: Any = None
    findings_count: Optional[int] = None
    major_findings: Optional[int] = None
    minor_findings: Optional[int] = None
    observations: Optional[int] = None
    certifications: CertificationsDetail = CertificationsDetail()
    cdm_compliant: Optional[bool] = None
    fors_accredited: Optional[bool] = None
    fors_level: Optional[str] = None
    audit_notes: Optional[str] = None


class UpdateAuditResponse(BaseModel):
    message: str
    id: int


# ============================================================================
# Audit response endpoints
# ============================================================================


class CreateAuditResponseResponse(BaseModel):
    id: int
    message: str


class AuditResponseItem(BaseModel):
    id: int
    question_id: int
    mse_response: Optional[int] = None
    site_response: Optional[int] = None
    finding_type: Optional[str] = None
    finding_description: Optional[str] = None


class GetAuditResponsesResponse(BaseModel):
    audit_id: int
    total_responses: int
    responses: List[AuditResponseItem]


# ============================================================================
# KPI endpoints
# ============================================================================


class AddKPIResponse(BaseModel):
    id: int
    message: str
    ltifr: Optional[float] = None


class KPIRecordItem(BaseModel):
    year: int
    total_man_hours: Optional[int] = None
    fatalities: int = 0
    riddor_reportable: int = 0
    lost_time_incidents: int = 0
    medical_treatment_incidents: int = 0
    first_aid_incidents: int = 0
    dangerous_occurrences: int = 0
    near_misses: int = 0
    hse_notices: int = 0
    hse_prosecutions: int = 0
    env_incidents: int = 0
    ltifr: Optional[float] = None


class GetAuditKPIsResponse(BaseModel):
    audit_id: int
    kpi_records: List[KPIRecordItem]


# ============================================================================
# ISO cross-mapping endpoint
# ============================================================================


class ISOCrossMappingItem(BaseModel):
    uvdb_section: str
    uvdb_question: str
    uvdb_text: str
    iso_9001: Any = []
    iso_14001: Any = []
    iso_45001: Any = []
    iso_27001: Any = []


class ISOCrossMappingSummary(BaseModel):
    iso_9001_aligned: str
    iso_14001_aligned: str
    iso_45001_aligned: str
    iso_27001_aligned: str


class GetISOCrossMappingResponse(BaseModel):
    description: str
    total_mappings: int
    mappings: List[ISOCrossMappingItem]
    summary: ISOCrossMappingSummary


# ============================================================================
# Dashboard endpoint
# ============================================================================


class DashboardSummary(BaseModel):
    total_audits: int = 0
    active_audits: int = 0
    completed_audits: int = 0
    average_score: float = 0.0


class DashboardProtocol(BaseModel):
    name: str
    version: str
    sections: int


class DashboardCertificationAlignment(BaseModel):
    iso_9001: str
    iso_14001: str
    iso_45001: str
    iso_27001: str


class GetDashboardResponse(BaseModel):
    summary: DashboardSummary
    protocol: DashboardProtocol
    certification_alignment: DashboardCertificationAlignment
