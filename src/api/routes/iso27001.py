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

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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
from src.api.dependencies import CurrentUser
from src.infrastructure.database import get_db

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


@router.get("/assets", response_model=dict)
async def list_assets(
    current_user: CurrentUser,
    asset_type: Optional[str] = Query(None),
    classification: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    criticality: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List information assets"""
    query = db.query(InformationAsset).filter(InformationAsset.is_active == True)

    if asset_type:
        query = query.filter(InformationAsset.asset_type == asset_type)
    if classification:
        query = query.filter(InformationAsset.classification == classification)
    if department:
        query = query.filter(InformationAsset.department == department)
    if criticality:
        query = query.filter(InformationAsset.criticality == criticality)

    total = query.count()
    assets = query.order_by(InformationAsset.criticality.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
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
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create information asset"""
    count = db.query(InformationAsset).count()
    asset_id = f"ASSET-{(count + 1):05d}"

    asset = InformationAsset(
        asset_id=asset_id,
        next_review_date=datetime.utcnow() + timedelta(days=365),
        **asset_data.model_dump(),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {"id": asset.id, "asset_id": asset_id, "message": "Asset created"}


@router.get("/assets/{asset_id}", response_model=dict)
async def get_asset(
    asset_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get asset details"""
    asset = db.query(InformationAsset).filter(InformationAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

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


@router.get("/controls", response_model=dict)
async def list_controls(
    current_user: CurrentUser,
    domain: Optional[str] = Query(None, description="organizational, people, physical, technological"),
    implementation_status: Optional[str] = Query(None),
    is_applicable: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List ISO 27001 Annex A controls"""
    query = db.query(ISO27001Control)

    if domain:
        query = query.filter(ISO27001Control.domain == domain)
    if implementation_status:
        query = query.filter(ISO27001Control.implementation_status == implementation_status)
    if is_applicable is not None:
        query = query.filter(ISO27001Control.is_applicable == is_applicable)

    total = query.count()
    controls = query.order_by(ISO27001Control.control_id).offset(skip).limit(limit).all()

    # Summary
    implemented = db.query(ISO27001Control).filter(ISO27001Control.implementation_status == "implemented").count()
    partial = db.query(ISO27001Control).filter(ISO27001Control.implementation_status == "partial").count()
    not_impl = db.query(ISO27001Control).filter(ISO27001Control.implementation_status == "not_implemented").count()
    excluded = db.query(ISO27001Control).filter(ISO27001Control.is_applicable == False).count()

    return {
        "total": total,
        "summary": {
            "implemented": implemented,
            "partially_implemented": partial,
            "not_implemented": not_impl,
            "excluded": excluded,
            "implementation_percentage": round((implemented / max(total - excluded, 1)) * 100, 1),
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
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update control implementation status"""
    control = db.query(ISO27001Control).filter(ISO27001Control.id == control_id).first()
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    update_data = control_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(control, key, value)

    if control_data.implementation_status == "implemented":
        control.implementation_date = datetime.utcnow()
    if control_data.effectiveness_rating:
        control.last_effectiveness_review = datetime.utcnow()

    control.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Control updated", "id": control.id}


# ============ Statement of Applicability ============


@router.get("/soa", response_model=dict)
async def get_current_soa(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get current Statement of Applicability"""
    soa = db.query(StatementOfApplicability).filter(StatementOfApplicability.is_current == True).first()

    if not soa:
        # Return summary from controls
        total = db.query(ISO27001Control).count()
        applicable = db.query(ISO27001Control).filter(ISO27001Control.is_applicable == True).count()
        implemented = (
            db.query(ISO27001Control)
            .filter(ISO27001Control.is_applicable == True, ISO27001Control.implementation_status == "implemented")
            .count()
        )

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
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List information security risks"""
    query = db.query(InformationSecurityRisk).filter(InformationSecurityRisk.status != "closed")

    if status:
        query = query.filter(InformationSecurityRisk.status == status)
    if treatment_option:
        query = query.filter(InformationSecurityRisk.treatment_option == treatment_option)
    if min_score:
        query = query.filter(InformationSecurityRisk.residual_risk_score >= min_score)

    total = query.count()
    risks = query.order_by(InformationSecurityRisk.residual_risk_score.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
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
            for r in risks
        ],
    }


@router.post("/risks", response_model=dict, status_code=201)
async def create_security_risk(
    risk_data: SecurityRiskCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create information security risk"""
    count = db.query(InformationSecurityRisk).count()
    risk_id = f"ISR-{(count + 1):04d}"

    inherent_score = risk_data.likelihood * risk_data.impact
    residual_score = (risk_data.likelihood - 1) * (risk_data.impact - 1)  # Simplified

    risk = InformationSecurityRisk(
        risk_id=risk_id,
        inherent_risk_score=inherent_score,
        residual_risk_score=max(residual_score, 1),
        next_review_date=datetime.utcnow() + timedelta(days=90),
        **risk_data.model_dump(),
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)

    return {"id": risk.id, "risk_id": risk_id, "message": "Security risk created"}


# ============ Security Incidents ============


@router.get("/incidents", response_model=dict)
async def list_security_incidents(
    current_user: CurrentUser,
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    incident_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List security incidents"""
    query = db.query(SecurityIncident)

    if status:
        query = query.filter(SecurityIncident.status == status)
    if severity:
        query = query.filter(SecurityIncident.severity == severity)
    if incident_type:
        query = query.filter(SecurityIncident.incident_type == incident_type)

    total = query.count()
    incidents = query.order_by(SecurityIncident.detected_date.desc()).offset(skip).limit(limit).all()

    # Summary
    open_count = db.query(SecurityIncident).filter(SecurityIncident.status == "open").count()
    critical_count = db.query(SecurityIncident).filter(SecurityIncident.severity == "critical").count()

    return {
        "total": total,
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
            for i in incidents
        ],
    }


@router.post("/incidents", response_model=dict, status_code=201)
async def create_security_incident(
    incident_data: SecurityIncidentCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create security incident"""
    count = db.query(SecurityIncident).count()
    incident_id = f"SEC-{(count + 1):05d}"

    incident = SecurityIncident(
        incident_id=incident_id,
        status="open",
        **incident_data.model_dump(),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    return {"id": incident.id, "incident_id": incident_id, "message": "Security incident created"}


@router.put("/incidents/{incident_id}", response_model=dict)
async def update_security_incident(
    incident_id: int,
    incident_data: IncidentUpdate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update security incident"""
    incident = db.query(SecurityIncident).filter(SecurityIncident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    update_data = incident_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(incident, key, value)

    if incident_data.status == "contained" and not incident.contained_date:
        incident.contained_date = datetime.utcnow()
    if incident_data.status == "closed" and not incident.resolved_date:
        incident.resolved_date = datetime.utcnow()

    incident.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Incident updated", "id": incident.id}


# ============ Supplier Assessments ============


@router.get("/suppliers", response_model=dict)
async def list_supplier_assessments(
    current_user: CurrentUser,
    rating: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List supplier security assessments"""
    query = db.query(SupplierSecurityAssessment).filter(SupplierSecurityAssessment.status == "active")

    if rating:
        query = query.filter(SupplierSecurityAssessment.overall_rating == rating)
    if risk_level:
        query = query.filter(SupplierSecurityAssessment.risk_level == risk_level)

    total = query.count()
    suppliers = query.order_by(SupplierSecurityAssessment.next_assessment_date).offset(skip).limit(limit).all()

    return {
        "total": total,
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
            for s in suppliers
        ],
    }


@router.post("/suppliers", response_model=dict, status_code=201)
async def create_supplier_assessment(
    assessment_data: SupplierAssessmentCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create supplier security assessment"""
    assessment = SupplierSecurityAssessment(
        assessment_date=datetime.utcnow(),
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
    db.commit()
    db.refresh(assessment)

    return {"id": assessment.id, "message": "Supplier assessment created"}


# ============ ISMS Dashboard Summary ============


@router.get("/dashboard", response_model=dict)
async def get_isms_dashboard(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get ISMS dashboard summary"""
    # Assets
    total_assets = db.query(InformationAsset).filter(InformationAsset.is_active == True).count()
    critical_assets = (
        db.query(InformationAsset)
        .filter(InformationAsset.is_active == True, InformationAsset.criticality == "critical")
        .count()
    )

    # Controls
    total_controls = db.query(ISO27001Control).count()
    implemented_controls = (
        db.query(ISO27001Control).filter(ISO27001Control.implementation_status == "implemented").count()
    )
    applicable_controls = db.query(ISO27001Control).filter(ISO27001Control.is_applicable == True).count()

    # Risks
    open_risks = db.query(InformationSecurityRisk).filter(InformationSecurityRisk.status != "closed").count()
    high_risks = (
        db.query(InformationSecurityRisk)
        .filter(InformationSecurityRisk.residual_risk_score > 16, InformationSecurityRisk.status != "closed")
        .count()
    )

    # Incidents
    open_incidents = db.query(SecurityIncident).filter(SecurityIncident.status == "open").count()
    incidents_30d = (
        db.query(SecurityIncident)
        .filter(SecurityIncident.detected_date >= datetime.utcnow() - timedelta(days=30))
        .count()
    )

    # Suppliers
    high_risk_suppliers = (
        db.query(SupplierSecurityAssessment)
        .filter(SupplierSecurityAssessment.risk_level == "high", SupplierSecurityAssessment.status == "active")
        .count()
    )

    return {
        "assets": {
            "total": total_assets,
            "critical": critical_assets,
        },
        "controls": {
            "total": total_controls,
            "applicable": applicable_controls,
            "implemented": implemented_controls,
            "implementation_percentage": round((implemented_controls / max(applicable_controls, 1)) * 100, 1),
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
        "compliance_score": round((implemented_controls / max(applicable_controls, 1)) * 100, 1),
    }
