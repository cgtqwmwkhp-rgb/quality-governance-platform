"""Response schemas for ISO 27001 endpoints."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

# ============ Information Assets ============


class InformationAssetListItemResponse(BaseModel):
    id: int
    asset_id: str
    name: str
    asset_type: str
    classification: str
    criticality: str
    owner_name: Optional[str] = None
    department: Optional[str] = None
    cia_score: int

    class Config:
        from_attributes = True


class InformationAssetListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    assets: list[InformationAssetListItemResponse]


class InformationAssetResponse(BaseModel):
    id: int
    asset_id: str
    name: str
    description: Optional[str] = None
    asset_type: str
    classification: str
    handling_requirements: Optional[str] = None
    owner_name: Optional[str] = None
    custodian_name: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    physical_location: Optional[str] = None
    logical_location: Optional[str] = None
    criticality: str
    business_value: Optional[str] = None
    confidentiality_requirement: int
    integrity_requirement: int
    availability_requirement: int
    cia_score: int
    dependencies: Optional[list] = None
    dependent_processes: Optional[list] = None
    applied_controls: Optional[list] = None
    status: str
    last_review_date: Optional[str] = None
    next_review_date: Optional[str] = None

    class Config:
        from_attributes = True


# ============ ISO 27001 Controls ============


class ISO27001ControlListItemResponse(BaseModel):
    id: int
    control_id: str
    control_name: str
    domain: str
    category: str
    implementation_status: str
    is_applicable: bool
    effectiveness_rating: Optional[str] = None
    control_owner_name: Optional[str] = None

    class Config:
        from_attributes = True


class ControlsSummaryResponse(BaseModel):
    implemented: int
    partially_implemented: int
    not_implemented: int
    excluded: int
    implementation_percentage: float


class ISO27001ControlListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    summary: ControlsSummaryResponse
    controls: list[ISO27001ControlListItemResponse]


# ============ Statement of Applicability ============


class SoAResponse(BaseModel):
    id: Optional[int] = None
    version: str
    effective_date: Optional[str] = None
    approved_by: Optional[str] = None
    approved_date: Optional[str] = None
    scope_description: Optional[str] = None
    total_controls: int
    applicable_controls: int
    excluded_controls: Optional[int] = None
    implemented_controls: int
    partially_implemented: Optional[int] = None
    not_implemented: Optional[int] = None
    implementation_percentage: float
    status: str
    document_link: Optional[str] = None


# ============ Information Security Risks ============


class InformationSecurityRiskListItemResponse(BaseModel):
    id: int
    risk_id: str
    title: str
    threat_source: Optional[str] = None
    inherent_risk_score: int
    residual_risk_score: int
    treatment_option: str
    treatment_status: str
    risk_owner_name: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class InformationSecurityRiskListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    risks: list[InformationSecurityRiskListItemResponse]


# ============ Security Incidents ============


class SecurityIncidentListItemResponse(BaseModel):
    id: int
    incident_id: str
    title: str
    incident_type: str
    severity: str
    status: str
    detected_date: Optional[str] = None
    assigned_to_name: Optional[str] = None
    data_compromised: bool

    class Config:
        from_attributes = True


class SecurityIncidentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    open_incidents: int
    critical_incidents: int
    incidents: list[SecurityIncidentListItemResponse]


# ============ Supplier Security Assessments ============


class SupplierSecurityAssessmentListItemResponse(BaseModel):
    id: int
    supplier_name: str
    supplier_type: str
    data_access_level: str
    overall_rating: str
    security_score: Optional[int] = None
    iso27001_certified: bool
    soc2_certified: bool
    risk_level: str
    next_assessment_date: Optional[str] = None

    class Config:
        from_attributes = True


class SupplierSecurityAssessmentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int
    suppliers: list[SupplierSecurityAssessmentListItemResponse]


# ============ ISMS Dashboard ============


class ISMSAssetsSummary(BaseModel):
    total: int
    critical: int


class ISMSControlsSummary(BaseModel):
    total: int
    applicable: int
    implemented: int
    implementation_percentage: float


class ISMSRisksSummary(BaseModel):
    open: int
    high_critical: int


class ISMSIncidentsSummary(BaseModel):
    open: int
    last_30_days: int


class ISMSSuppliersSummary(BaseModel):
    high_risk: int


class ISMSDashboardResponse(BaseModel):
    assets: ISMSAssetsSummary
    controls: ISMSControlsSummary
    risks: ISMSRisksSummary
    incidents: ISMSIncidentsSummary
    suppliers: ISMSSuppliersSummary
    compliance_score: float


# ============ Mutation Responses ============


class AssetCreateResponse(BaseModel):
    id: int
    asset_id: str
    message: str


class ControlUpdateResponse(BaseModel):
    message: str
    id: int


class SecurityRiskCreateResponse(BaseModel):
    id: int
    risk_id: str
    message: str


class SecurityIncidentCreateResponse(BaseModel):
    id: int
    incident_id: str
    message: str


class IncidentUpdateResponse(BaseModel):
    message: str
    id: int


class SupplierAssessmentCreateResponse(BaseModel):
    id: int
    message: str
