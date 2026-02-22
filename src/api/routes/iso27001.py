"""
ISO 27001:2022 Information Security Management System API Routes

Provides endpoints for:
- Information Asset Management
- ISO 27001 Annex A Controls
- Statement of Applicability (SoA)
- Information Security Risks
- Security Incidents
- Access Control Management
- Business Continuity Plans
- Supplier Security Assessments
"""

from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.domain.models.user import User
from src.api.schemas.iso27001 import (
    AssetCreateResponse,
    ControlUpdateResponse,
    IncidentUpdateResponse,
    InformationAssetListResponse,
    InformationAssetResponse,
    InformationSecurityRiskListResponse,
    ISMSDashboardResponse,
    ISO27001ControlListResponse,
    SecurityIncidentCreateResponse,
    SecurityIncidentListResponse,
    SecurityRiskCreateResponse,
    SoAResponse,
    SupplierAssessmentCreateResponse,
    SupplierSecurityAssessmentListResponse,
)
from src.api.utils.pagination import PaginationParams
from src.domain.services.iso27001_service import ISO27001Service

router = APIRouter()


# ============ Pydantic Schemas ============


class AssetCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    asset_type: str = Field(..., description="hardware, software, data, service, people, physical")
    classification: str = Field(default="internal")
    owner_name: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    criticality: str = Field(default="medium")
    confidentiality_requirement: int = Field(default=2, ge=1, le=3)
    integrity_requirement: int = Field(default=2, ge=1, le=3)
    availability_requirement: int = Field(default=2, ge=1, le=3)


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    classification: Optional[str] = None
    owner_name: Optional[str] = None
    criticality: Optional[str] = None
    status: Optional[str] = None


class ControlUpdate(BaseModel):
    implementation_status: Optional[str] = None
    implementation_notes: Optional[str] = None
    is_applicable: Optional[bool] = None
    exclusion_justification: Optional[str] = None
    effectiveness_rating: Optional[str] = None
    control_owner_name: Optional[str] = None


class SecurityRiskCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    threat_source: Optional[str] = None
    threat_description: Optional[str] = None
    vulnerability: Optional[str] = None
    affected_assets: Optional[list[int]] = None
    asset_classification: Optional[str] = None
    confidentiality_impact: int = Field(default=2, ge=1, le=3)
    integrity_impact: int = Field(default=2, ge=1, le=3)
    availability_impact: int = Field(default=2, ge=1, le=3)
    likelihood: int = Field(default=3, ge=1, le=5)
    impact: int = Field(default=3, ge=1, le=5)
    treatment_option: str = Field(default="mitigate")
    treatment_plan: Optional[str] = None
    applicable_controls: Optional[list[str]] = None
    risk_owner_name: Optional[str] = None


class SecurityIncidentCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    incident_type: str = Field(...)
    severity: str = Field(default="medium")
    detected_date: datetime
    occurred_date: Optional[datetime] = None
    cia_impact: Optional[list[str]] = None
    affected_assets: Optional[list[int]] = None
    data_compromised: bool = False
    reported_by_name: Optional[str] = None


class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    severity: Optional[str] = None
    assigned_to_name: Optional[str] = None
    root_cause: Optional[str] = None
    containment_actions: Optional[str] = None
    eradication_actions: Optional[str] = None
    recovery_actions: Optional[str] = None
    lessons_learned: Optional[str] = None
    resolved_date: Optional[datetime] = None


class SupplierAssessmentCreate(BaseModel):
    supplier_name: str = Field(..., min_length=3, max_length=255)
    supplier_type: str = Field(...)
    services_provided: Optional[str] = None
    data_access_level: str = Field(default="none")
    assessment_type: str = Field(default="initial")
    overall_rating: str = Field(...)
    security_score: Optional[int] = Field(None, ge=0, le=100)
    iso27001_certified: bool = False
    soc2_certified: bool = False
    findings_count: int = Field(default=0)
    critical_findings: int = Field(default=0)
    risk_level: str = Field(default="medium")


# ============ Information Assets ============


@router.get("/assets", response_model=InformationAssetListResponse)
async def list_assets(
    db: DbSession,
    current_user: CurrentUser,
    asset_type: Optional[str] = Query(None),
    classification: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    criticality: Optional[str] = Query(None),
    params: PaginationParams = Depends(),
) -> dict[str, Any]:
    """List information assets"""
    return await ISO27001Service.list_assets(
        db,
        current_user.tenant_id,
        params,
        asset_type=asset_type,
        classification=classification,
        department=department,
        criticality=criticality,
    )


@router.post("/assets", response_model=AssetCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    asset_data: AssetCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("iso27001:create"))],
) -> dict[str, Any]:
    """Create information asset"""
    return await ISO27001Service.create_asset(db, current_user.tenant_id, asset_data.model_dump())


@router.get("/assets/{asset_id}", response_model=InformationAssetResponse)
async def get_asset(
    asset_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get asset details"""
    return await ISO27001Service.get_asset(db, asset_id, current_user.tenant_id)


# ============ ISO 27001 Controls (Annex A) ============


@router.get("/controls", response_model=ISO27001ControlListResponse)
async def list_controls(
    db: DbSession,
    current_user: CurrentUser,
    domain: Optional[str] = Query(None, description="organizational, people, physical, technological"),
    implementation_status: Optional[str] = Query(None),
    is_applicable: Optional[bool] = Query(None),
    params: PaginationParams = Depends(),
) -> dict[str, Any]:
    """List ISO 27001 Annex A controls"""
    return await ISO27001Service.list_controls(
        db,
        params,
        domain=domain,
        implementation_status=implementation_status,
        is_applicable=is_applicable,
    )


@router.put("/controls/{control_id}", response_model=ControlUpdateResponse)
async def update_control(
    control_id: int,
    control_data: ControlUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("iso27001:update"))],
) -> dict[str, Any]:
    """Update control implementation status"""
    return await ISO27001Service.update_control(db, control_id, control_data.model_dump(exclude_unset=True))


# ============ Statement of Applicability ============


@router.get("/soa", response_model=SoAResponse)
async def get_current_soa(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get current Statement of Applicability"""
    return await ISO27001Service.get_current_soa(db)


# ============ Information Security Risks ============


@router.get("/risks", response_model=InformationSecurityRiskListResponse)
async def list_security_risks(
    db: DbSession,
    current_user: CurrentUser,
    status: Optional[str] = Query(None),
    treatment_option: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None, ge=1, le=25),
    params: PaginationParams = Depends(),
) -> dict[str, Any]:
    """List information security risks"""
    return await ISO27001Service.list_security_risks(
        db,
        current_user.tenant_id,
        params,
        risk_status=status,
        treatment_option=treatment_option,
        min_score=min_score,
    )


@router.post("/risks", response_model=SecurityRiskCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_security_risk(
    risk_data: SecurityRiskCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("iso27001:create"))],
) -> dict[str, Any]:
    """Create information security risk"""
    return await ISO27001Service.create_security_risk(db, current_user.tenant_id, risk_data.model_dump())


# ============ Security Incidents ============


@router.get("/incidents", response_model=SecurityIncidentListResponse)
async def list_security_incidents(
    db: DbSession,
    current_user: CurrentUser,
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    incident_type: Optional[str] = Query(None),
    params: PaginationParams = Depends(),
) -> dict[str, Any]:
    """List security incidents"""
    return await ISO27001Service.list_security_incidents(
        db,
        current_user.tenant_id,
        params,
        incident_status=status,
        severity=severity,
        incident_type=incident_type,
    )


@router.post("/incidents", response_model=SecurityIncidentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_security_incident(
    incident_data: SecurityIncidentCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("iso27001:create"))],
) -> dict[str, Any]:
    """Create security incident"""
    return await ISO27001Service.create_security_incident(db, current_user.tenant_id, incident_data.model_dump())


@router.put("/incidents/{incident_id}", response_model=IncidentUpdateResponse)
async def update_security_incident(
    incident_id: int,
    incident_data: IncidentUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("iso27001:update"))],
) -> dict[str, Any]:
    """Update security incident"""
    return await ISO27001Service.update_incident(
        db, incident_id, current_user.tenant_id, incident_data.model_dump(exclude_unset=True)
    )


# ============ Supplier Assessments ============


@router.get("/suppliers", response_model=SupplierSecurityAssessmentListResponse)
async def list_supplier_assessments(
    db: DbSession,
    current_user: CurrentUser,
    rating: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    params: PaginationParams = Depends(),
) -> dict[str, Any]:
    """List supplier security assessments"""
    return await ISO27001Service.list_supplier_assessments(
        db,
        current_user.tenant_id,
        params,
        rating=rating,
        risk_level=risk_level,
    )


@router.post("/suppliers", response_model=SupplierAssessmentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_assessment(
    assessment_data: SupplierAssessmentCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("iso27001:create"))],
) -> dict[str, Any]:
    """Create supplier security assessment"""
    return await ISO27001Service.create_supplier_assessment(db, current_user.tenant_id, assessment_data.model_dump())


# ============ ISMS Dashboard Summary ============


@router.get("/dashboard", response_model=ISMSDashboardResponse)
async def get_isms_dashboard(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get ISMS dashboard summary"""
    return await ISO27001Service.get_isms_dashboard(db, current_user.tenant_id)
