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

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select, text

from src.api.dependencies import CurrentUser, DbSession
from src.domain.exceptions import NotFoundError
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

router = APIRouter()

# Criticality ordering for SQL CASE expression (critical first)
_CRITICALITY_ORDER = case(
    (InformationAsset.criticality == "critical", 0),
    (InformationAsset.criticality == "high", 1),
    (InformationAsset.criticality == "medium", 2),
    (InformationAsset.criticality == "low", 3),
    else_=4,
)

_VALID_ASSET_TYPES = Literal["hardware", "software", "data", "service", "people", "physical"]
_VALID_CLASSIFICATIONS = Literal["public", "internal", "confidential", "restricted", "secret"]
_VALID_CRITICALITY = Literal["low", "medium", "high", "critical"]
_VALID_SEVERITY = Literal["low", "medium", "high", "critical"]
_VALID_INCIDENT_TYPES = Literal[
    "malware",
    "phishing",
    "unauthorized_access",
    "data_breach",
    "dos",
    "insider_threat",
    "physical",
    "data_leak",
    "other",
]
_VALID_TREATMENT = Literal["accept", "avoid", "mitigate", "transfer"]
_VALID_SUPPLIER_RATINGS = Literal["compliant", "partially_compliant", "non_compliant"]
_VALID_RISK_LEVELS = Literal["low", "medium", "high", "critical"]
_VALID_DATA_ACCESS = Literal["none", "limited", "full"]
_VALID_ASSESSMENT_TYPES = Literal["initial", "periodic", "ad-hoc"]
_VALID_ACCESS_LEVEL = Literal["read", "write", "admin", "owner"]
_VALID_INCIDENT_STATUS = Literal["open", "investigating", "contained", "eradicating", "recovering", "closed"]
_VALID_CONTROL_IMPL_STATUS = Literal["not_implemented", "partial", "implemented", "excluded"]
_VALID_RISK_STATUS = Literal["open", "in_treatment", "accepted", "closed"]
_VALID_RISK_TREATMENT_STATUS = Literal["planned", "in_progress", "completed"]


def _tenant_scoped_id(prefix: str, tenant_id: int, suffix: int) -> str:
    """Generate a tenant-scoped human-readable ID that avoids cross-tenant collisions."""
    return f"{prefix}-{tenant_id}-{suffix:05d}"


# ============ Pydantic Schemas ============


class AssetCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    asset_type: _VALID_ASSET_TYPES
    classification: _VALID_CLASSIFICATIONS = "internal"
    owner_name: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    criticality: _VALID_CRITICALITY = "medium"
    confidentiality_requirement: int = Field(default=2, ge=1, le=3)
    integrity_requirement: int = Field(default=2, ge=1, le=3)
    availability_requirement: int = Field(default=2, ge=1, le=3)


class AssetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    classification: Optional[_VALID_CLASSIFICATIONS] = None
    owner_name: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    criticality: Optional[_VALID_CRITICALITY] = None
    status: Optional[str] = None
    confidentiality_requirement: Optional[int] = Field(None, ge=1, le=3)
    integrity_requirement: Optional[int] = Field(None, ge=1, le=3)
    availability_requirement: Optional[int] = Field(None, ge=1, le=3)


class ControlUpdate(BaseModel):
    implementation_status: Optional[_VALID_CONTROL_IMPL_STATUS] = None
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
    asset_classification: Optional[_VALID_CLASSIFICATIONS] = None
    confidentiality_impact: int = Field(default=2, ge=1, le=3)
    integrity_impact: int = Field(default=2, ge=1, le=3)
    availability_impact: int = Field(default=2, ge=1, le=3)
    likelihood: int = Field(default=3, ge=1, le=5)
    impact: int = Field(default=3, ge=1, le=5)
    residual_likelihood: int = Field(default=2, ge=1, le=5)
    residual_impact: int = Field(default=2, ge=1, le=5)
    treatment_option: _VALID_TREATMENT = "mitigate"
    treatment_plan: Optional[str] = None
    applicable_controls: Optional[list[str]] = None
    risk_owner_name: Optional[str] = None


class RiskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    likelihood: Optional[int] = Field(None, ge=1, le=5)
    impact: Optional[int] = Field(None, ge=1, le=5)
    residual_likelihood: Optional[int] = Field(None, ge=1, le=5)
    residual_impact: Optional[int] = Field(None, ge=1, le=5)
    treatment_option: Optional[_VALID_TREATMENT] = None
    treatment_plan: Optional[str] = None
    treatment_status: Optional[_VALID_RISK_TREATMENT_STATUS] = None
    risk_owner_name: Optional[str] = None
    status: Optional[_VALID_RISK_STATUS] = None


class SecurityIncidentCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    incident_type: _VALID_INCIDENT_TYPES
    severity: _VALID_SEVERITY = "medium"
    priority: _VALID_SEVERITY = "medium"
    detected_date: datetime
    occurred_date: Optional[datetime] = None
    cia_impact: Optional[list[str]] = None
    affected_assets: Optional[list[int]] = None
    affected_users: Optional[int] = Field(None, ge=0)
    data_compromised: bool = False
    regulatory_notification_required: bool = False
    reported_by_name: Optional[str] = None


class IncidentUpdate(BaseModel):
    status: Optional[_VALID_INCIDENT_STATUS] = None
    severity: Optional[_VALID_SEVERITY] = None
    priority: Optional[_VALID_SEVERITY] = None
    assigned_to_name: Optional[str] = None
    root_cause: Optional[str] = None
    attack_vector: Optional[str] = None
    containment_actions: Optional[str] = None
    eradication_actions: Optional[str] = None
    recovery_actions: Optional[str] = None
    lessons_learned: Optional[str] = None
    resolved_date: Optional[datetime] = None
    regulatory_notification_required: Optional[bool] = None
    regulatory_body: Optional[str] = None
    regulatory_notification_date: Optional[datetime] = None


class SupplierAssessmentCreate(BaseModel):
    supplier_name: str = Field(..., min_length=3, max_length=255)
    supplier_type: str = Field(...)
    services_provided: Optional[str] = None
    data_access_level: _VALID_DATA_ACCESS = "none"
    assessment_type: _VALID_ASSESSMENT_TYPES = "initial"
    overall_rating: _VALID_SUPPLIER_RATINGS
    security_score: Optional[int] = Field(None, ge=0, le=100)
    iso27001_certified: bool = False
    soc2_certified: bool = False
    findings_count: int = Field(default=0, ge=0)
    critical_findings: int = Field(default=0, ge=0)
    risk_level: _VALID_RISK_LEVELS = "medium"
    assessment_frequency_months: int = Field(default=12, ge=1, le=60)


class AccessControlCreate(BaseModel):
    user_id: int
    user_name: str = Field(..., min_length=1, max_length=255)
    user_email: Optional[str] = None
    user_department: Optional[str] = None
    system_name: str = Field(..., min_length=1, max_length=255)
    access_level: _VALID_ACCESS_LEVEL
    granted_date: datetime
    granted_by: Optional[str] = None
    expiry_date: Optional[datetime] = None


# ============ Information Assets ============


@router.get("/assets", response_model=dict)
async def list_assets(
    current_user: CurrentUser,
    asset_type: Optional[str] = Query(None),
    classification: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    criticality: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: DbSession = None,
) -> dict[str, Any]:
    """List information assets sorted by criticality (critical first)."""
    tid = current_user.tenant_id
    stmt = select(InformationAsset).where(
        InformationAsset.is_active == True,  # noqa: E712
        InformationAsset.tenant_id == tid,
    )

    if asset_type:
        stmt = stmt.where(InformationAsset.asset_type == asset_type)
    if classification:
        stmt = stmt.where(InformationAsset.classification == classification)
    if department:
        stmt = stmt.where(InformationAsset.department == department)
    if criticality:
        stmt = stmt.where(InformationAsset.criticality == criticality)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar()

    result = await db.execute(stmt.order_by(_CRITICALITY_ORDER).offset(skip).limit(limit))
    assets = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
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
            for a in assets
        ],
    }


@router.post("/assets", response_model=dict, status_code=201)
async def create_asset(
    asset_data: AssetCreate,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Create information asset with tenant-scoped unique ID."""
    tid = current_user.tenant_id
    count_result = await db.execute(
        select(func.count()).select_from(InformationAsset).where(InformationAsset.tenant_id == tid)
    )
    count = count_result.scalar()
    asset_id = _tenant_scoped_id("ASSET", tid, count + 1)

    asset = InformationAsset(
        asset_id=asset_id,
        tenant_id=tid,
        next_review_date=datetime.utcnow() + timedelta(days=365),
        **asset_data.model_dump(),
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    return {"id": asset.id, "asset_id": asset_id, "message": "Asset created"}


@router.get("/assets/{asset_id}", response_model=dict)
async def get_asset(
    asset_id: int,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Get asset details."""
    result = await db.execute(
        select(InformationAsset).where(
            InformationAsset.id == asset_id,
            InformationAsset.tenant_id == current_user.tenant_id,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise NotFoundError("Asset not found")

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
        "last_review_date": (asset.last_review_date.isoformat() if asset.last_review_date else None),
        "next_review_date": (asset.next_review_date.isoformat() if asset.next_review_date else None),
    }


@router.put("/assets/{asset_id}", response_model=dict)
async def update_asset(
    asset_id: int,
    asset_data: AssetUpdate,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Update an information asset."""
    result = await db.execute(
        select(InformationAsset).where(
            InformationAsset.id == asset_id,
            InformationAsset.tenant_id == current_user.tenant_id,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise NotFoundError("Asset not found")

    update_data = asset_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(asset, key, value)

    asset.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Asset updated", "id": asset.id}


# ============ ISO 27001 Controls (Annex A) ============


@router.get("/controls", response_model=dict)
async def list_controls(
    current_user: CurrentUser,
    domain: Optional[str] = Query(None, description="organizational, people, physical, technological"),
    implementation_status: Optional[str] = Query(None),
    is_applicable: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: DbSession = None,
) -> dict[str, Any]:
    """List ISO 27001 Annex A controls."""
    tid = current_user.tenant_id
    stmt = select(ISO27001Control).where(ISO27001Control.tenant_id == tid)

    if domain:
        stmt = stmt.where(ISO27001Control.domain == domain)
    if implementation_status:
        stmt = stmt.where(ISO27001Control.implementation_status == implementation_status)
    if is_applicable is not None:
        stmt = stmt.where(ISO27001Control.is_applicable == is_applicable)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar()

    result = await db.execute(stmt.order_by(ISO27001Control.control_id).offset(skip).limit(limit))
    controls = result.scalars().all()

    impl_result = await db.execute(
        select(func.count(ISO27001Control.id)).where(
            ISO27001Control.tenant_id == tid,
            ISO27001Control.implementation_status == "implemented",
        )
    )
    implemented = impl_result.scalar()

    partial_result = await db.execute(
        select(func.count(ISO27001Control.id)).where(
            ISO27001Control.tenant_id == tid,
            ISO27001Control.implementation_status == "partial",
        )
    )
    partial = partial_result.scalar()

    not_impl_result = await db.execute(
        select(func.count(ISO27001Control.id)).where(
            ISO27001Control.tenant_id == tid,
            ISO27001Control.implementation_status == "not_implemented",
        )
    )
    not_impl = not_impl_result.scalar()

    excl_result = await db.execute(
        select(func.count(ISO27001Control.id)).where(
            ISO27001Control.tenant_id == tid,
            ISO27001Control.is_applicable == False,  # noqa: E712
        )
    )
    excluded = excl_result.scalar()

    applicable = total - excluded
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "summary": {
            "implemented": implemented,
            "partially_implemented": partial,
            "not_implemented": not_impl,
            "excluded": excluded,
            "applicable": applicable,
            "implementation_percentage": round((implemented / max(applicable, 1)) * 100, 1),
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
            for c in controls
        ],
    }


@router.put("/controls/{control_id}", response_model=dict)
async def update_control(
    control_id: int,
    control_data: ControlUpdate,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Update control implementation status."""
    result = await db.execute(
        select(ISO27001Control).where(
            ISO27001Control.id == control_id,
            ISO27001Control.tenant_id == current_user.tenant_id,
        )
    )
    control = result.scalar_one_or_none()
    if not control:
        raise NotFoundError("Control not found")

    update_data = control_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(control, key, value)

    if control_data.implementation_status == "implemented":
        control.implementation_date = datetime.now(timezone.utc)
    if control_data.effectiveness_rating:
        control.last_effectiveness_review = datetime.now(timezone.utc)

    control.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Control updated", "id": control.id}


# ============ Statement of Applicability ============


@router.get("/soa", response_model=dict)
async def get_current_soa(
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Get current Statement of Applicability."""
    tid = current_user.tenant_id

    # Use LIMIT 1 to prevent MultipleResultsFound if data integrity is violated
    result = await db.execute(
        select(StatementOfApplicability)
        .where(
            StatementOfApplicability.is_current == True,  # noqa: E712
            StatementOfApplicability.tenant_id == tid,
        )
        .limit(1)
    )
    soa = result.scalars().first()

    if not soa:
        total_result = await db.execute(
            select(func.count()).select_from(ISO27001Control).where(ISO27001Control.tenant_id == tid)
        )
        total = total_result.scalar()

        applicable_result = await db.execute(
            select(func.count(ISO27001Control.id)).where(
                ISO27001Control.tenant_id == tid,
                ISO27001Control.is_applicable == True,  # noqa: E712
            )
        )
        applicable = applicable_result.scalar()

        implemented_result = await db.execute(
            select(func.count(ISO27001Control.id)).where(
                ISO27001Control.tenant_id == tid,
                ISO27001Control.is_applicable == True,  # noqa: E712
                ISO27001Control.implementation_status == "implemented",
            )
        )
        implemented = implemented_result.scalar()

        return {
            "version": "N/A",
            "status": "not_created",
            "total_controls": total,
            "applicable_controls": applicable,
            "excluded_controls": total - applicable,
            "implemented_controls": implemented,
            "implementation_percentage": round((implemented / max(applicable, 1)) * 100, 1),
        }

    return {
        "id": soa.id,
        "version": soa.version,
        "effective_date": (soa.effective_date.isoformat() if soa.effective_date else None),
        "approved_by": soa.approved_by,
        "approved_date": soa.approved_date.isoformat() if soa.approved_date else None,
        "scope_description": soa.scope_description,
        "total_controls": soa.total_controls,
        "applicable_controls": soa.applicable_controls,
        "excluded_controls": soa.excluded_controls,
        "implemented_controls": soa.implemented_controls,
        "partially_implemented": soa.partially_implemented,
        "not_implemented": soa.not_implemented,
        "implementation_percentage": round((soa.implemented_controls / max(soa.applicable_controls, 1)) * 100, 1),
        "status": soa.status,
        "document_link": soa.document_link,
    }


# ============ Information Security Risks ============


@router.get("/risks", response_model=dict)
async def list_security_risks(
    current_user: CurrentUser,
    status: Optional[str] = Query(None),
    treatment_option: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None, ge=1, le=25),
    include_closed: bool = Query(False, description="Include closed risks in results"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: DbSession = None,
) -> dict[str, Any]:
    """List information security risks."""
    tid = current_user.tenant_id
    stmt = select(InformationSecurityRisk).where(
        InformationSecurityRisk.tenant_id == tid,
    )

    # Apply status filter — when a specific status is requested, honour it directly
    if status:
        stmt = stmt.where(InformationSecurityRisk.status == status)
    elif not include_closed:
        stmt = stmt.where(InformationSecurityRisk.status != "closed")
    if treatment_option:
        stmt = stmt.where(InformationSecurityRisk.treatment_option == treatment_option)
    if min_score:
        stmt = stmt.where(InformationSecurityRisk.inherent_risk_score >= min_score)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar()

    result = await db.execute(
        stmt.order_by(InformationSecurityRisk.inherent_risk_score.desc()).offset(skip).limit(limit)
    )
    risks = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "risks": [
            {
                "id": r.id,
                "risk_id": r.risk_id,
                "title": r.title,
                "threat_source": r.threat_source,
                "likelihood": r.likelihood,
                "impact": r.impact,
                "inherent_risk_score": r.inherent_risk_score,
                "residual_likelihood": r.residual_likelihood,
                "residual_impact": r.residual_impact,
                "residual_risk_score": r.residual_risk_score,
                "treatment_option": r.treatment_option,
                "treatment_status": r.treatment_status,
                "risk_owner_name": r.risk_owner_name,
                "status": r.status,
            }
            for r in risks
        ],
    }


@router.get("/risks/{risk_id}", response_model=dict)
async def get_security_risk(
    risk_id: int,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Get a specific information security risk."""
    result = await db.execute(
        select(InformationSecurityRisk).where(
            InformationSecurityRisk.id == risk_id,
            InformationSecurityRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("Risk not found")

    return {
        "id": risk.id,
        "risk_id": risk.risk_id,
        "title": risk.title,
        "description": risk.description,
        "threat_source": risk.threat_source,
        "threat_description": risk.threat_description,
        "vulnerability": risk.vulnerability,
        "affected_assets": risk.affected_assets,
        "asset_classification": risk.asset_classification,
        "confidentiality_impact": risk.confidentiality_impact,
        "integrity_impact": risk.integrity_impact,
        "availability_impact": risk.availability_impact,
        "likelihood": risk.likelihood,
        "impact": risk.impact,
        "inherent_risk_score": risk.inherent_risk_score,
        "residual_likelihood": risk.residual_likelihood,
        "residual_impact": risk.residual_impact,
        "residual_risk_score": risk.residual_risk_score,
        "treatment_option": risk.treatment_option,
        "treatment_plan": risk.treatment_plan,
        "treatment_status": risk.treatment_status,
        "applicable_controls": risk.applicable_controls,
        "risk_owner_name": risk.risk_owner_name,
        "last_review_date": risk.last_review_date.isoformat() if risk.last_review_date else None,
        "next_review_date": risk.next_review_date.isoformat() if risk.next_review_date else None,
        "status": risk.status,
    }


@router.post("/risks", response_model=dict, status_code=201)
async def create_security_risk(
    risk_data: SecurityRiskCreate,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Create information security risk with correct residual score calculation."""
    tid = current_user.tenant_id
    count_result = await db.execute(
        select(func.count()).select_from(InformationSecurityRisk).where(InformationSecurityRisk.tenant_id == tid)
    )
    count = count_result.scalar()
    risk_id = _tenant_scoped_id("ISR", tid, count + 1)

    inherent_score = risk_data.likelihood * risk_data.impact
    # Residual score uses the actual post-treatment likelihood/impact fields
    residual_score = risk_data.residual_likelihood * risk_data.residual_impact

    data = risk_data.model_dump()
    risk = InformationSecurityRisk(
        risk_id=risk_id,
        tenant_id=tid,
        inherent_risk_score=inherent_score,
        residual_risk_score=residual_score,
        next_review_date=datetime.utcnow() + timedelta(days=90),
        **data,
    )
    db.add(risk)
    await db.commit()
    await db.refresh(risk)

    return {"id": risk.id, "risk_id": risk_id, "message": "Security risk created"}


@router.put("/risks/{risk_id}", response_model=dict)
async def update_security_risk(
    risk_id: int,
    risk_data: RiskUpdate,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Update a security risk (for periodic review updates)."""
    result = await db.execute(
        select(InformationSecurityRisk).where(
            InformationSecurityRisk.id == risk_id,
            InformationSecurityRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("Risk not found")

    update_data = risk_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(risk, key, value)

    # Recalculate scores if rating fields changed
    if any(k in update_data for k in ("likelihood", "impact")):
        risk.inherent_risk_score = risk.likelihood * risk.impact
    if any(k in update_data for k in ("residual_likelihood", "residual_impact")):
        risk.residual_risk_score = risk.residual_likelihood * risk.residual_impact

    risk.last_review_date = datetime.now(timezone.utc)
    risk.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Risk updated", "id": risk.id}


# ============ Security Incidents ============


@router.get("/incidents", response_model=dict)
async def list_security_incidents(
    current_user: CurrentUser,
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    incident_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: DbSession = None,
) -> dict[str, Any]:
    """List security incidents."""
    tid = current_user.tenant_id
    stmt = select(SecurityIncident).where(SecurityIncident.tenant_id == tid)

    if status:
        stmt = stmt.where(SecurityIncident.status == status)
    if severity:
        stmt = stmt.where(SecurityIncident.severity == severity)
    if incident_type:
        stmt = stmt.where(SecurityIncident.incident_type == incident_type)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar()

    result = await db.execute(stmt.order_by(SecurityIncident.detected_date.desc()).offset(skip).limit(limit))
    incidents = result.scalars().all()

    open_result = await db.execute(
        select(func.count(SecurityIncident.id)).where(
            SecurityIncident.tenant_id == tid,
            SecurityIncident.status == "open",
        )
    )
    open_count = open_result.scalar()

    critical_result = await db.execute(
        select(func.count(SecurityIncident.id)).where(
            SecurityIncident.tenant_id == tid,
            SecurityIncident.severity == "critical",
        )
    )
    critical_count = critical_result.scalar()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
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
                "detected_date": (i.detected_date.isoformat() if i.detected_date else None),
                "assigned_to_name": i.assigned_to_name,
                "data_compromised": i.data_compromised,
            }
            for i in incidents
        ],
    }


@router.post("/incidents", response_model=dict, status_code=201)
async def create_security_incident(
    incident_data: SecurityIncidentCreate,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Create security incident with tenant-scoped ID."""
    tid = current_user.tenant_id
    count_result = await db.execute(
        select(func.count()).select_from(SecurityIncident).where(SecurityIncident.tenant_id == tid)
    )
    count = count_result.scalar()
    incident_id = _tenant_scoped_id("SEC", tid, count + 1)

    incident = SecurityIncident(
        incident_id=incident_id,
        tenant_id=tid,
        status="open",
        **incident_data.model_dump(),
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)

    return {
        "id": incident.id,
        "incident_id": incident_id,
        "message": "Security incident created",
    }


@router.get("/incidents/{incident_id}", response_model=dict)
async def get_security_incident(
    incident_id: int,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Get a specific security incident by ID."""
    result = await db.execute(
        select(SecurityIncident).where(
            SecurityIncident.id == incident_id,
            SecurityIncident.tenant_id == current_user.tenant_id,
        )
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise NotFoundError("Incident not found")

    return {
        "id": incident.id,
        "incident_id": incident.incident_id,
        "title": incident.title,
        "description": incident.description,
        "incident_type": incident.incident_type,
        "severity": incident.severity,
        "priority": incident.priority,
        "status": incident.status,
        "cia_impact": incident.cia_impact,
        "affected_assets": incident.affected_assets,
        "affected_users": incident.affected_users,
        "data_compromised": incident.data_compromised,
        "data_types_affected": incident.data_types_affected,
        "detected_date": incident.detected_date.isoformat() if incident.detected_date else None,
        "occurred_date": incident.occurred_date.isoformat() if incident.occurred_date else None,
        "reported_date": incident.reported_date.isoformat() if incident.reported_date else None,
        "contained_date": incident.contained_date.isoformat() if incident.contained_date else None,
        "resolved_date": incident.resolved_date.isoformat() if incident.resolved_date else None,
        "reported_by_name": incident.reported_by_name,
        "assigned_to_name": incident.assigned_to_name,
        "root_cause": incident.root_cause,
        "attack_vector": incident.attack_vector,
        "indicators_of_compromise": incident.indicators_of_compromise,
        "containment_actions": incident.containment_actions,
        "eradication_actions": incident.eradication_actions,
        "recovery_actions": incident.recovery_actions,
        "lessons_learned": incident.lessons_learned,
        "regulatory_notification_required": incident.regulatory_notification_required,
        "regulatory_notification_date": (
            incident.regulatory_notification_date.isoformat() if incident.regulatory_notification_date else None
        ),
        "regulatory_body": incident.regulatory_body,
    }


@router.put("/incidents/{incident_id}", response_model=dict)
async def update_security_incident(
    incident_id: int,
    incident_data: IncidentUpdate,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Update security incident."""
    result = await db.execute(
        select(SecurityIncident).where(
            SecurityIncident.id == incident_id,
            SecurityIncident.tenant_id == current_user.tenant_id,
        )
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise NotFoundError("Incident not found")

    update_data = incident_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(incident, key, value)

    if incident_data.status == "contained" and not incident.contained_date:
        incident.contained_date = datetime.now(timezone.utc)
    if incident_data.status == "closed" and not incident.resolved_date:
        incident.resolved_date = datetime.now(timezone.utc)

    incident.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Incident updated", "id": incident.id}


# ============ Supplier Assessments ============


@router.get("/suppliers", response_model=dict)
async def list_supplier_assessments(
    current_user: CurrentUser,
    rating: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: DbSession = None,
) -> dict[str, Any]:
    """List supplier security assessments."""
    tid = current_user.tenant_id
    stmt = select(SupplierSecurityAssessment).where(
        SupplierSecurityAssessment.status == "active",
        SupplierSecurityAssessment.tenant_id == tid,
    )

    if rating:
        stmt = stmt.where(SupplierSecurityAssessment.overall_rating == rating)
    if risk_level:
        stmt = stmt.where(SupplierSecurityAssessment.risk_level == risk_level)

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar()

    result = await db.execute(
        stmt.order_by(SupplierSecurityAssessment.next_assessment_date.asc().nullslast()).offset(skip).limit(limit)
    )
    suppliers = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
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
                "next_assessment_date": (s.next_assessment_date.isoformat() if s.next_assessment_date else None),
            }
            for s in suppliers
        ],
    }


@router.get("/suppliers/{supplier_id}", response_model=dict)
async def get_supplier_assessment(
    supplier_id: int,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Get a specific supplier security assessment."""
    result = await db.execute(
        select(SupplierSecurityAssessment).where(
            SupplierSecurityAssessment.id == supplier_id,
            SupplierSecurityAssessment.tenant_id == current_user.tenant_id,
        )
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise NotFoundError("Supplier assessment not found")

    return {
        "id": supplier.id,
        "supplier_name": supplier.supplier_name,
        "supplier_type": supplier.supplier_type,
        "services_provided": supplier.services_provided,
        "data_access_level": supplier.data_access_level,
        "assessment_date": supplier.assessment_date.isoformat() if supplier.assessment_date else None,
        "assessment_type": supplier.assessment_type,
        "assessor_name": supplier.assessor_name,
        "overall_rating": supplier.overall_rating,
        "security_score": supplier.security_score,
        "iso27001_certified": supplier.iso27001_certified,
        "soc2_certified": supplier.soc2_certified,
        "other_certifications": supplier.other_certifications,
        "findings_count": supplier.findings_count,
        "critical_findings": supplier.critical_findings,
        "findings_details": supplier.findings_details,
        "risk_level": supplier.risk_level,
        "risk_accepted": supplier.risk_accepted,
        "risk_accepted_by": supplier.risk_accepted_by,
        "next_assessment_date": (supplier.next_assessment_date.isoformat() if supplier.next_assessment_date else None),
        "assessment_frequency_months": supplier.assessment_frequency_months,
        "status": supplier.status,
    }


@router.post("/suppliers", response_model=dict, status_code=201)
async def create_supplier_assessment(
    assessment_data: SupplierAssessmentCreate,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Create supplier security assessment."""
    assessment = SupplierSecurityAssessment(
        tenant_id=current_user.tenant_id,
        assessment_date=datetime.now(timezone.utc),
        next_assessment_date=datetime.now(timezone.utc)
        + timedelta(days=assessment_data.assessment_frequency_months * 30),
        **assessment_data.model_dump(),
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)

    return {"id": assessment.id, "message": "Supplier assessment created"}


# ============ Access Control Records ============


@router.get("/access-control", response_model=dict)
async def list_access_control(
    current_user: CurrentUser,
    active_only: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: DbSession = None,
) -> dict[str, Any]:
    """List access control records for access review."""
    tid = current_user.tenant_id
    stmt = select(AccessControlRecord).where(AccessControlRecord.tenant_id == tid)

    if active_only:
        stmt = stmt.where(AccessControlRecord.is_active == True)  # noqa: E712

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar()

    result = await db.execute(
        stmt.order_by(AccessControlRecord.next_review_date.asc().nullslast()).offset(skip).limit(limit)
    )
    records = result.scalars().all()

    overdue_result = await db.execute(
        select(func.count(AccessControlRecord.id)).where(
            AccessControlRecord.tenant_id == tid,
            AccessControlRecord.is_active == True,  # noqa: E712
            AccessControlRecord.next_review_date < datetime.utcnow(),
        )
    )
    overdue = overdue_result.scalar()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "overdue_reviews": overdue,
        "records": [
            {
                "id": r.id,
                "user_name": r.user_name,
                "user_email": r.user_email,
                "user_department": r.user_department,
                "system_name": r.system_name,
                "access_level": r.access_level,
                "access_type": r.access_type,
                "granted_date": r.granted_date.isoformat() if r.granted_date else None,
                "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
                "next_review_date": r.next_review_date.isoformat() if r.next_review_date else None,
                "is_active": r.is_active,
                "status": r.status,
            }
            for r in records
        ],
    }


@router.post("/access-control", response_model=dict, status_code=201)
async def create_access_control(
    ac_data: AccessControlCreate,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Record an access control grant."""
    record = AccessControlRecord(
        tenant_id=current_user.tenant_id,
        next_review_date=datetime.utcnow() + timedelta(days=90),
        **ac_data.model_dump(),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return {"id": record.id, "message": "Access control record created"}


# ============ Business Continuity Plans ============


class BCPCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=10)
    scope: str = Field(..., min_length=5)
    rto_hours: int = Field(..., ge=0, le=8760)
    rpo_hours: int = Field(..., ge=0, le=8760)
    mtpd_hours: Optional[int] = Field(None, ge=0, le=8760)
    covered_systems: Optional[list[str]] = None
    covered_processes: Optional[list[str]] = None
    activation_criteria: Optional[str] = None
    notification_procedures: Optional[str] = None
    recovery_procedures: Optional[str] = None
    resumption_procedures: Optional[str] = None
    plan_owner_name: Optional[str] = None
    team_members: Optional[list] = None
    escalation_contacts: Optional[list] = None
    test_frequency_months: int = Field(default=12, ge=1, le=60)
    version: str = Field(default="1.0", max_length=20)
    effective_date: datetime
    approved_by: Optional[str] = None


class BCPUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    scope: Optional[str] = None
    rto_hours: Optional[int] = Field(None, ge=0, le=8760)
    rpo_hours: Optional[int] = Field(None, ge=0, le=8760)
    mtpd_hours: Optional[int] = Field(None, ge=0, le=8760)
    activation_criteria: Optional[str] = None
    notification_procedures: Optional[str] = None
    recovery_procedures: Optional[str] = None
    resumption_procedures: Optional[str] = None
    plan_owner_name: Optional[str] = None
    last_test_date: Optional[datetime] = None
    last_test_type: Optional[str] = None
    last_test_result: Optional[str] = None
    next_test_date: Optional[datetime] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/business-continuity", response_model=dict)
async def list_bcps(
    current_user: CurrentUser,
    active_only: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: DbSession = None,
) -> dict[str, Any]:
    """List business continuity plans."""
    tid = current_user.tenant_id
    stmt = select(BusinessContinuityPlan).where(BusinessContinuityPlan.tenant_id == tid)
    if active_only:
        stmt = stmt.where(BusinessContinuityPlan.is_active == True)  # noqa: E712

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar()

    result = await db.execute(
        stmt.order_by(BusinessContinuityPlan.next_review_date.asc().nullslast()).offset(skip).limit(limit)
    )
    plans = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "plans": [
            {
                "id": p.id,
                "plan_id": p.plan_id,
                "name": p.name,
                "scope": p.scope,
                "rto_hours": p.rto_hours,
                "rpo_hours": p.rpo_hours,
                "last_test_date": p.last_test_date.isoformat() if p.last_test_date else None,
                "next_test_date": p.next_test_date.isoformat() if p.next_test_date else None,
                "last_test_result": p.last_test_result,
                "plan_owner_name": p.plan_owner_name,
                "version": p.version,
                "is_active": p.is_active,
            }
            for p in plans
        ],
    }


@router.get("/business-continuity/{plan_id}", response_model=dict)
async def get_bcp(
    plan_id: int,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Get a business continuity plan by ID."""
    result = await db.execute(
        select(BusinessContinuityPlan).where(
            BusinessContinuityPlan.id == plan_id,
            BusinessContinuityPlan.tenant_id == current_user.tenant_id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise NotFoundError("Business continuity plan not found")

    return {
        "id": plan.id,
        "plan_id": plan.plan_id,
        "name": plan.name,
        "description": plan.description,
        "scope": plan.scope,
        "rto_hours": plan.rto_hours,
        "rpo_hours": plan.rpo_hours,
        "mtpd_hours": plan.mtpd_hours,
        "covered_systems": plan.covered_systems,
        "covered_processes": plan.covered_processes,
        "activation_criteria": plan.activation_criteria,
        "notification_procedures": plan.notification_procedures,
        "recovery_procedures": plan.recovery_procedures,
        "resumption_procedures": plan.resumption_procedures,
        "plan_owner_name": plan.plan_owner_name,
        "team_members": plan.team_members,
        "escalation_contacts": plan.escalation_contacts,
        "last_test_date": plan.last_test_date.isoformat() if plan.last_test_date else None,
        "last_test_type": plan.last_test_type,
        "last_test_result": plan.last_test_result,
        "next_test_date": plan.next_test_date.isoformat() if plan.next_test_date else None,
        "test_frequency_months": plan.test_frequency_months,
        "version": plan.version,
        "effective_date": plan.effective_date.isoformat() if plan.effective_date else None,
        "approved_by": plan.approved_by,
        "next_review_date": plan.next_review_date.isoformat() if plan.next_review_date else None,
        "is_active": plan.is_active,
    }


@router.post("/business-continuity", response_model=dict, status_code=201)
async def create_bcp(
    bcp_data: BCPCreate,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Create a business continuity plan."""
    tid = current_user.tenant_id
    count_result = await db.execute(
        select(func.count()).select_from(BusinessContinuityPlan).where(BusinessContinuityPlan.tenant_id == tid)
    )
    count = count_result.scalar()
    plan_id = _tenant_scoped_id("BCP", tid, count + 1)

    plan = BusinessContinuityPlan(
        plan_id=plan_id,
        tenant_id=tid,
        next_review_date=datetime.utcnow() + timedelta(days=365),
        **bcp_data.model_dump(),
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    return {"id": plan.id, "plan_id": plan_id, "message": "Business continuity plan created"}


@router.put("/business-continuity/{plan_id}", response_model=dict)
async def update_bcp(
    plan_id: int,
    bcp_data: BCPUpdate,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Update a business continuity plan."""
    result = await db.execute(
        select(BusinessContinuityPlan).where(
            BusinessContinuityPlan.id == plan_id,
            BusinessContinuityPlan.tenant_id == current_user.tenant_id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise NotFoundError("Business continuity plan not found")

    update_data = bcp_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)

    plan.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Business continuity plan updated", "id": plan.id}


# ============ ISMS Dashboard Summary ============


@router.get("/dashboard", response_model=dict)
async def get_isms_dashboard(
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Get ISMS dashboard summary with all live metrics."""
    tid = current_user.tenant_id

    # Assets
    assets_result = await db.execute(
        select(func.count(InformationAsset.id)).where(
            InformationAsset.tenant_id == tid,
            InformationAsset.is_active == True,  # noqa: E712
        )
    )
    total_assets = assets_result.scalar()

    critical_assets_result = await db.execute(
        select(func.count(InformationAsset.id)).where(
            InformationAsset.tenant_id == tid,
            InformationAsset.is_active == True,  # noqa: E712
            InformationAsset.criticality == "critical",
        )
    )
    critical_assets = critical_assets_result.scalar()

    # Controls
    total_controls_result = await db.execute(
        select(func.count()).select_from(ISO27001Control).where(ISO27001Control.tenant_id == tid)
    )
    total_controls = total_controls_result.scalar()

    impl_controls_result = await db.execute(
        select(func.count(ISO27001Control.id)).where(
            ISO27001Control.tenant_id == tid,
            ISO27001Control.implementation_status == "implemented",
        )
    )
    implemented_controls = impl_controls_result.scalar()

    applicable_controls_result = await db.execute(
        select(func.count(ISO27001Control.id)).where(
            ISO27001Control.tenant_id == tid,
            ISO27001Control.is_applicable == True,  # noqa: E712
        )
    )
    applicable_controls = applicable_controls_result.scalar()

    # Risks
    open_risks_result = await db.execute(
        select(func.count(InformationSecurityRisk.id)).where(
            InformationSecurityRisk.tenant_id == tid,
            InformationSecurityRisk.status != "closed",
        )
    )
    open_risks = open_risks_result.scalar()

    # High risks: inherent_risk_score >= 15 (L>=3 * I>=5 or L>=5 * I>=3)
    high_risks_result = await db.execute(
        select(func.count(InformationSecurityRisk.id)).where(
            InformationSecurityRisk.tenant_id == tid,
            InformationSecurityRisk.inherent_risk_score >= 15,
            InformationSecurityRisk.status != "closed",
        )
    )
    high_risks = high_risks_result.scalar()

    # Incidents
    open_incidents_result = await db.execute(
        select(func.count(SecurityIncident.id)).where(
            SecurityIncident.tenant_id == tid,
            SecurityIncident.status == "open",
        )
    )
    open_incidents = open_incidents_result.scalar()

    incidents_30d_result = await db.execute(
        select(func.count(SecurityIncident.id)).where(
            SecurityIncident.tenant_id == tid,
            SecurityIncident.detected_date >= datetime.utcnow() - timedelta(days=30),
        )
    )
    incidents_30d = incidents_30d_result.scalar()

    # Suppliers
    high_risk_suppliers_result = await db.execute(
        select(func.count(SupplierSecurityAssessment.id)).where(
            SupplierSecurityAssessment.tenant_id == tid,
            SupplierSecurityAssessment.risk_level == "high",
            SupplierSecurityAssessment.status == "active",
        )
    )
    high_risk_suppliers = high_risk_suppliers_result.scalar()

    # Recent incidents for dashboard feed
    recent_result = await db.execute(
        select(SecurityIncident)
        .where(SecurityIncident.tenant_id == tid)
        .order_by(SecurityIncident.detected_date.desc())
        .limit(5)
    )
    recent_incidents = recent_result.scalars().all()

    # Per-domain control breakdown
    domains = ["organizational", "people", "physical", "technological"]
    domain_counts: dict[str, dict] = {}
    for domain in domains:
        d_total_r = await db.execute(
            select(func.count(ISO27001Control.id)).where(
                ISO27001Control.tenant_id == tid,
                ISO27001Control.domain == domain,
            )
        )
        d_impl_r = await db.execute(
            select(func.count(ISO27001Control.id)).where(
                ISO27001Control.tenant_id == tid,
                ISO27001Control.domain == domain,
                ISO27001Control.implementation_status == "implemented",
            )
        )
        d_total = d_total_r.scalar()
        d_impl = d_impl_r.scalar()
        domain_counts[domain] = {
            "domain": domain,
            "total": d_total,
            "implemented": d_impl,
            "percentage": round((d_impl / max(d_total, 1)) * 100, 1),
        }

    compliance_score = round((implemented_controls / max(applicable_controls, 1)) * 100, 1)

    return {
        "assets": {
            "total": total_assets,
            "critical": critical_assets,
        },
        "controls": {
            "total": total_controls,
            "applicable": applicable_controls,
            "implemented": implemented_controls,
            "implementation_percentage": compliance_score,
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
        "compliance_score": compliance_score,
        "domains": list(domain_counts.values()),
        "recent_incidents": [
            {
                "id": i.incident_id,
                "title": i.title,
                "incident_type": i.incident_type,
                "severity": i.severity,
                "status": i.status,
                "date": i.detected_date.isoformat() if i.detected_date else None,
            }
            for i in recent_incidents
        ],
    }
