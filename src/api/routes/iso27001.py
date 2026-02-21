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

from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from src.api.dependencies import CurrentUser, DbSession
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
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.iso27001 import (
    AccessControlRecord,
    BusinessContinuityPlan,
    InformationAsset,
    InformationSecurityRisk,
    ISO27001Control,
    SecurityIncident,
    SoAControlEntry,
    StatementOfApplicability,
    SupplierSecurityAssessment,
)
from src.domain.services.iso27001_service import ISO27001Service
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter()


# ============ ISO 27001-Specific Helpers ============


async def _generate_asset_id(db) -> str:
    """Generate next sequential asset ID (ASSET-NNNNN)."""
    result = await db.execute(select(func.count()).select_from(InformationAsset))
    count = result.scalar_one()
    return f"ASSET-{(count + 1):05d}"


def _calculate_risk_scores(likelihood: int, impact: int) -> tuple[int, int]:
    """Delegate to ISO27001Service."""
    return ISO27001Service.calculate_risk_scores(likelihood, impact)


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
    stmt = select(InformationAsset).where(
        InformationAsset.is_active == True,
        InformationAsset.tenant_id == current_user.tenant_id,
    )

    if asset_type:
        stmt = stmt.where(InformationAsset.asset_type == asset_type)
    if classification:
        stmt = stmt.where(InformationAsset.classification == classification)
    if department:
        stmt = stmt.where(InformationAsset.department == department)
    if criticality:
        stmt = stmt.where(InformationAsset.criticality == criticality)

    query = stmt.order_by(InformationAsset.criticality.desc())
    paginated = await paginate(db, query, params)

    return {
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
        "assets": [
            {
                "id": a.id,
                "asset_id": a.asset_id,
                "name": a.name,
                "asset_type": a.asset_type,
                "classification": a.classification,
                "criticality": a.criticality,
                "owner_name": a.owner_name,
                "department": a.department,
                "cia_score": a.confidentiality_requirement + a.integrity_requirement + a.availability_requirement,
            }
            for a in paginated.items
        ],
    }


@router.post("/assets", response_model=AssetCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    asset_data: AssetCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Create information asset"""
    asset_id = await _generate_asset_id(db)

    asset = InformationAsset(
        asset_id=asset_id,
        next_review_date=datetime.utcnow() + timedelta(days=365),
        tenant_id=current_user.tenant_id,
        **asset_data.model_dump(),
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    return {"id": asset.id, "asset_id": asset_id, "message": "Asset created"}


@router.get("/assets/{asset_id}", response_model=InformationAssetResponse)
async def get_asset(
    asset_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get asset details"""
    asset = await get_or_404(db, InformationAsset, asset_id, tenant_id=current_user.tenant_id)

    return {
        "id": asset.id,
        "asset_id": asset.asset_id,
        "name": asset.name,
        "description": asset.description,
        "asset_type": asset.asset_type,
        "classification": asset.classification,
        "handling_requirements": asset.handling_requirements,
        "owner_name": asset.owner_name,
        "custodian_name": asset.custodian_name,
        "department": asset.department,
        "location": asset.location,
        "physical_location": asset.physical_location,
        "logical_location": asset.logical_location,
        "criticality": asset.criticality,
        "business_value": asset.business_value,
        "confidentiality_requirement": asset.confidentiality_requirement,
        "integrity_requirement": asset.integrity_requirement,
        "availability_requirement": asset.availability_requirement,
        "cia_score": asset.confidentiality_requirement + asset.integrity_requirement + asset.availability_requirement,
        "dependencies": asset.dependencies,
        "dependent_processes": asset.dependent_processes,
        "applied_controls": asset.applied_controls,
        "status": asset.status,
        "last_review_date": asset.last_review_date.isoformat() if asset.last_review_date else None,
        "next_review_date": asset.next_review_date.isoformat() if asset.next_review_date else None,
    }


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
    stmt = select(ISO27001Control)

    if domain:
        stmt = stmt.where(ISO27001Control.domain == domain)
    if implementation_status:
        stmt = stmt.where(ISO27001Control.implementation_status == implementation_status)
    if is_applicable is not None:
        stmt = stmt.where(ISO27001Control.is_applicable == is_applicable)

    query = stmt.order_by(ISO27001Control.control_id)
    paginated = await paginate(db, query, params)
    track_metric("iso27001.controls_accessed")

    # Summary
    result = await db.execute(
        select(func.count()).select_from(ISO27001Control).where(ISO27001Control.implementation_status == "implemented")
    )
    implemented = result.scalar_one()

    result = await db.execute(
        select(func.count()).select_from(ISO27001Control).where(ISO27001Control.implementation_status == "partial")
    )
    partial = result.scalar_one()

    result = await db.execute(
        select(func.count())
        .select_from(ISO27001Control)
        .where(ISO27001Control.implementation_status == "not_implemented")
    )
    not_impl = result.scalar_one()

    result = await db.execute(
        select(func.count()).select_from(ISO27001Control).where(ISO27001Control.is_applicable == False)
    )
    excluded = result.scalar_one()

    return {
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
        "summary": {
            "implemented": implemented,
            "partially_implemented": partial,
            "not_implemented": not_impl,
            "excluded": excluded,
            "implementation_percentage": ISO27001Service.calculate_implementation_percentage(
                implemented, paginated.total, excluded
            ),
        },
        "controls": [
            {
                "id": c.id,
                "control_id": c.control_id,
                "control_name": c.control_name,
                "domain": c.domain,
                "category": c.category,
                "implementation_status": c.implementation_status,
                "is_applicable": c.is_applicable,
                "effectiveness_rating": c.effectiveness_rating,
                "control_owner_name": c.control_owner_name,
            }
            for c in paginated.items
        ],
    }


@router.put("/controls/{control_id}", response_model=ControlUpdateResponse)
async def update_control(
    control_id: int,
    control_data: ControlUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Update control implementation status"""
    control = await get_or_404(db, ISO27001Control, control_id)
    apply_updates(control, control_data)

    if control_data.implementation_status == "implemented":
        control.implementation_date = datetime.utcnow()
    if control_data.effectiveness_rating:
        control.last_effectiveness_review = datetime.utcnow()
    await db.commit()

    return {"message": "Control updated", "id": control.id}


# ============ Statement of Applicability ============


@router.get("/soa", response_model=SoAResponse)
async def get_current_soa(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get current Statement of Applicability"""
    result = await db.execute(select(StatementOfApplicability).where(StatementOfApplicability.is_current == True))
    soa = result.scalar_one_or_none()

    if not soa:
        result = await db.execute(select(func.count()).select_from(ISO27001Control))
        total = result.scalar_one()

        result = await db.execute(
            select(func.count()).select_from(ISO27001Control).where(ISO27001Control.is_applicable == True)
        )
        applicable = result.scalar_one()

        result = await db.execute(
            select(func.count())
            .select_from(ISO27001Control)
            .where(ISO27001Control.is_applicable == True, ISO27001Control.implementation_status == "implemented")
        )
        implemented = result.scalar_one()

        return {
            "version": "N/A",
            "status": "not_created",
            "total_controls": total,
            "applicable_controls": applicable,
            "excluded_controls": total - applicable,
            "implemented_controls": implemented,
            "implementation_percentage": ISO27001Service.calculate_soa_compliance_percentage(implemented, applicable),
        }

    return {
        "id": soa.id,
        "version": soa.version,
        "effective_date": soa.effective_date.isoformat() if soa.effective_date else None,
        "approved_by": soa.approved_by,
        "approved_date": soa.approved_date.isoformat() if soa.approved_date else None,
        "scope_description": soa.scope_description,
        "total_controls": soa.total_controls,
        "applicable_controls": soa.applicable_controls,
        "excluded_controls": soa.excluded_controls,
        "implemented_controls": soa.implemented_controls,
        "partially_implemented": soa.partially_implemented,
        "not_implemented": soa.not_implemented,
        "implementation_percentage": ISO27001Service.calculate_soa_compliance_percentage(
            soa.implemented_controls, soa.applicable_controls
        ),
        "status": soa.status,
        "document_link": soa.document_link,
    }


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
    stmt = select(InformationSecurityRisk).where(
        InformationSecurityRisk.status != "closed",
        InformationSecurityRisk.tenant_id == current_user.tenant_id,
    )

    if status:
        stmt = stmt.where(InformationSecurityRisk.status == status)
    if treatment_option:
        stmt = stmt.where(InformationSecurityRisk.treatment_option == treatment_option)
    if min_score:
        stmt = stmt.where(InformationSecurityRisk.residual_risk_score >= min_score)

    query = stmt.order_by(InformationSecurityRisk.residual_risk_score.desc())
    paginated = await paginate(db, query, params)

    return {
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
        "risks": [
            {
                "id": r.id,
                "risk_id": r.risk_id,
                "title": r.title,
                "threat_source": r.threat_source,
                "inherent_risk_score": r.inherent_risk_score,
                "residual_risk_score": r.residual_risk_score,
                "treatment_option": r.treatment_option,
                "treatment_status": r.treatment_status,
                "risk_owner_name": r.risk_owner_name,
                "status": r.status,
            }
            for r in paginated.items
        ],
    }


@router.post("/risks", response_model=SecurityRiskCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_security_risk(
    risk_data: SecurityRiskCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Create information security risk"""
    result = await db.execute(select(func.count()).select_from(InformationSecurityRisk))
    count = result.scalar_one()
    risk_id = f"ISR-{(count + 1):04d}"

    inherent_score, residual_score = _calculate_risk_scores(risk_data.likelihood, risk_data.impact)

    risk = InformationSecurityRisk(
        risk_id=risk_id,
        inherent_risk_score=inherent_score,
        residual_risk_score=residual_score,
        next_review_date=datetime.utcnow() + timedelta(days=90),
        tenant_id=current_user.tenant_id,
        **risk_data.model_dump(),
    )
    db.add(risk)
    await db.commit()
    await db.refresh(risk)

    return {"id": risk.id, "risk_id": risk_id, "message": "Security risk created"}


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
    stmt = select(SecurityIncident).where(
        SecurityIncident.tenant_id == current_user.tenant_id,
    )

    if status:
        stmt = stmt.where(SecurityIncident.status == status)
    if severity:
        stmt = stmt.where(SecurityIncident.severity == severity)
    if incident_type:
        stmt = stmt.where(SecurityIncident.incident_type == incident_type)

    query = stmt.order_by(SecurityIncident.detected_date.desc())
    paginated = await paginate(db, query, params)

    # Summary
    result = await db.execute(
        select(func.count())
        .select_from(SecurityIncident)
        .where(SecurityIncident.tenant_id == current_user.tenant_id, SecurityIncident.status == "open")
    )
    open_count = result.scalar_one()

    result = await db.execute(
        select(func.count())
        .select_from(SecurityIncident)
        .where(SecurityIncident.tenant_id == current_user.tenant_id, SecurityIncident.severity == "critical")
    )
    critical_count = result.scalar_one()

    return {
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
        "open_incidents": open_count,
        "critical_incidents": critical_count,
        "incidents": [
            {
                "id": i.id,
                "incident_id": i.incident_id,
                "title": i.title,
                "incident_type": i.incident_type,
                "severity": i.severity,
                "status": i.status,
                "detected_date": i.detected_date.isoformat() if i.detected_date else None,
                "assigned_to_name": i.assigned_to_name,
                "data_compromised": i.data_compromised,
            }
            for i in paginated.items
        ],
    }


@router.post("/incidents", response_model=SecurityIncidentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_security_incident(
    incident_data: SecurityIncidentCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Create security incident"""
    result = await db.execute(select(func.count()).select_from(SecurityIncident))
    count = result.scalar_one()
    incident_id = f"SEC-{(count + 1):05d}"

    incident = SecurityIncident(
        incident_id=incident_id,
        status="open",
        tenant_id=current_user.tenant_id,
        **incident_data.model_dump(),
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)

    return {"id": incident.id, "incident_id": incident_id, "message": "Security incident created"}


@router.put("/incidents/{incident_id}", response_model=IncidentUpdateResponse)
async def update_security_incident(
    incident_id: int,
    incident_data: IncidentUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Update security incident"""
    incident = await get_or_404(db, SecurityIncident, incident_id, tenant_id=current_user.tenant_id)
    apply_updates(incident, incident_data)

    if incident_data.status == "contained" and not incident.contained_date:
        incident.contained_date = datetime.utcnow()
    if incident_data.status == "closed" and not incident.resolved_date:
        incident.resolved_date = datetime.utcnow()
    await db.commit()

    return {"message": "Incident updated", "id": incident.id}


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
    stmt = select(SupplierSecurityAssessment).where(
        SupplierSecurityAssessment.status == "active",
        SupplierSecurityAssessment.tenant_id == current_user.tenant_id,
    )

    if rating:
        stmt = stmt.where(SupplierSecurityAssessment.overall_rating == rating)
    if risk_level:
        stmt = stmt.where(SupplierSecurityAssessment.risk_level == risk_level)

    query = stmt.order_by(SupplierSecurityAssessment.next_assessment_date)
    paginated = await paginate(db, query, params)

    return {
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
        "suppliers": [
            {
                "id": s.id,
                "supplier_name": s.supplier_name,
                "supplier_type": s.supplier_type,
                "data_access_level": s.data_access_level,
                "overall_rating": s.overall_rating,
                "security_score": s.security_score,
                "iso27001_certified": s.iso27001_certified,
                "soc2_certified": s.soc2_certified,
                "risk_level": s.risk_level,
                "next_assessment_date": s.next_assessment_date.isoformat() if s.next_assessment_date else None,
            }
            for s in paginated.items
        ],
    }


@router.post("/suppliers", response_model=SupplierAssessmentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_assessment(
    assessment_data: SupplierAssessmentCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Create supplier security assessment"""
    assessment = SupplierSecurityAssessment(
        assessment_date=datetime.utcnow(),
        tenant_id=current_user.tenant_id,
        next_assessment_date=datetime.utcnow()
        + timedelta(
            days=(
                assessment_data.assessment_frequency_months
                if hasattr(assessment_data, "assessment_frequency_months")
                else 365
            )
        ),
        **assessment_data.model_dump(),
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)

    return {"id": assessment.id, "message": "Supplier assessment created"}


# ============ ISMS Dashboard Summary ============


@router.get("/dashboard", response_model=ISMSDashboardResponse)
async def get_isms_dashboard(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get ISMS dashboard summary"""
    # Assets
    result = await db.execute(
        select(func.count())
        .select_from(InformationAsset)
        .where(InformationAsset.is_active == True, InformationAsset.tenant_id == current_user.tenant_id)
    )
    total_assets = result.scalar_one()

    result = await db.execute(
        select(func.count())
        .select_from(InformationAsset)
        .where(
            InformationAsset.is_active == True,
            InformationAsset.tenant_id == current_user.tenant_id,
            InformationAsset.criticality == "critical",
        )
    )
    critical_assets = result.scalar_one()

    # Controls
    result = await db.execute(select(func.count()).select_from(ISO27001Control))
    total_controls = result.scalar_one()

    result = await db.execute(
        select(func.count()).select_from(ISO27001Control).where(ISO27001Control.implementation_status == "implemented")
    )
    implemented_controls = result.scalar_one()

    result = await db.execute(
        select(func.count()).select_from(ISO27001Control).where(ISO27001Control.is_applicable == True)
    )
    applicable_controls = result.scalar_one()

    # Risks
    result = await db.execute(
        select(func.count())
        .select_from(InformationSecurityRisk)
        .where(
            InformationSecurityRisk.tenant_id == current_user.tenant_id,
            InformationSecurityRisk.status != "closed",
        )
    )
    open_risks = result.scalar_one()

    result = await db.execute(
        select(func.count())
        .select_from(InformationSecurityRisk)
        .where(
            InformationSecurityRisk.tenant_id == current_user.tenant_id,
            InformationSecurityRisk.residual_risk_score > 16,
            InformationSecurityRisk.status != "closed",
        )
    )
    high_risks = result.scalar_one()

    # Incidents
    result = await db.execute(
        select(func.count())
        .select_from(SecurityIncident)
        .where(
            SecurityIncident.tenant_id == current_user.tenant_id,
            SecurityIncident.status == "open",
        )
    )
    open_incidents = result.scalar_one()

    result = await db.execute(
        select(func.count())
        .select_from(SecurityIncident)
        .where(
            SecurityIncident.tenant_id == current_user.tenant_id,
            SecurityIncident.detected_date >= datetime.utcnow() - timedelta(days=30),
        )
    )
    incidents_30d = result.scalar_one()

    # Suppliers
    result = await db.execute(
        select(func.count())
        .select_from(SupplierSecurityAssessment)
        .where(
            SupplierSecurityAssessment.tenant_id == current_user.tenant_id,
            SupplierSecurityAssessment.risk_level == "high",
            SupplierSecurityAssessment.status == "active",
        )
    )
    high_risk_suppliers = result.scalar_one()

    return {
        "assets": {
            "total": total_assets,
            "critical": critical_assets,
        },
        "controls": {
            "total": total_controls,
            "applicable": applicable_controls,
            "implemented": implemented_controls,
            "implementation_percentage": ISO27001Service.calculate_soa_compliance_percentage(
                implemented_controls, applicable_controls
            ),
        },
        "risks": {
            "open": open_risks,
            "high_critical": high_risks,
        },
        "incidents": {
            "open": open_incidents,
            "last_30_days": incidents_30d,
        },
        "suppliers": {
            "high_risk": high_risk_suppliers,
        },
        "compliance_score": ISO27001Service.calculate_soa_compliance_percentage(
            implemented_controls, applicable_controls
        ),
    }
