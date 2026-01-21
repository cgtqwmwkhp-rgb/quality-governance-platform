"""
Enterprise Risk Register API Routes

Provides endpoints for:
- Risk CRUD operations
- Risk scoring and assessment
- Heat maps and trends
- Bow-tie analysis
- Key Risk Indicators (KRIs)
"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.infrastructure.database import get_db
from src.domain.models.risk_register import (
    BowTieElement,
    KeyRiskIndicator,
    Risk,
    RiskAppetiteStatement,
    RiskAssessmentHistory,
    RiskControl,
    RiskControlMapping,
)
from src.domain.services.risk_service import (
    BowTieService,
    KRIService,
    RiskScoringEngine,
    RiskService,
)

router = APIRouter()


# ============ Pydantic Schemas ============


class RiskCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    category: str = Field(..., description="Risk category (strategic, operational, etc.)")
    subcategory: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    process: Optional[str] = None
    inherent_likelihood: int = Field(..., ge=1, le=5)
    inherent_impact: int = Field(..., ge=1, le=5)
    residual_likelihood: int = Field(..., ge=1, le=5)
    residual_impact: int = Field(..., ge=1, le=5)
    treatment_strategy: str = Field(default="treat")
    treatment_plan: Optional[str] = None
    risk_owner_id: Optional[int] = None
    risk_owner_name: Optional[str] = None
    review_frequency_days: int = Field(default=90, ge=7, le=365)


class RiskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    process: Optional[str] = None
    treatment_strategy: Optional[str] = None
    treatment_plan: Optional[str] = None
    treatment_status: Optional[str] = None
    status: Optional[str] = None
    risk_owner_id: Optional[int] = None
    risk_owner_name: Optional[str] = None


class RiskAssessmentUpdate(BaseModel):
    inherent_likelihood: Optional[int] = Field(None, ge=1, le=5)
    inherent_impact: Optional[int] = Field(None, ge=1, le=5)
    residual_likelihood: Optional[int] = Field(None, ge=1, le=5)
    residual_impact: Optional[int] = Field(None, ge=1, le=5)
    review_notes: Optional[str] = None
    assessment_notes: Optional[str] = None


class ControlCreate(BaseModel):
    name: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    control_type: str = Field(..., description="preventive, detective, corrective")
    control_nature: str = Field(default="manual", description="manual, automated, hybrid")
    control_owner_id: Optional[int] = None
    control_owner_name: Optional[str] = None
    standard_clauses: Optional[list[str]] = None


class KRICreate(BaseModel):
    risk_id: int
    name: str = Field(..., min_length=5, max_length=255)
    description: Optional[str] = None
    metric_type: str = Field(..., description="count, percentage, ratio, value")
    green_threshold: float
    amber_threshold: float
    red_threshold: float
    threshold_direction: str = Field(default="above", description="above or below")
    data_source: Optional[str] = None
    update_frequency: str = Field(default="monthly")
    alert_enabled: bool = True
    alert_recipients: Optional[list[str]] = None


class KRIValueUpdate(BaseModel):
    value: float


class BowTieElementCreate(BaseModel):
    element_type: str = Field(..., description="cause, consequence, prevention, mitigation")
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    barrier_type: Optional[str] = None
    linked_control_id: Optional[int] = None
    effectiveness: Optional[str] = None
    is_escalation_factor: bool = False


# ============ Risk CRUD Endpoints ============


@router.get("/", response_model=dict)
async def list_risks(
    category: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None, ge=1, le=25),
    outside_appetite: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List risks with filtering options"""
    query = db.query(Risk)

    if category:
        query = query.filter(Risk.category == category)
    if department:
        query = query.filter(Risk.department == department)
    if status:
        query = query.filter(Risk.status == status)
    if min_score:
        query = query.filter(Risk.residual_score >= min_score)
    if outside_appetite:
        query = query.filter(Risk.is_within_appetite == False)

    total = query.count()
    risks = query.order_by(Risk.residual_score.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "risks": [
            {
                "id": r.id,
                "reference": r.reference,
                "title": r.title,
                "category": r.category,
                "department": r.department,
                "inherent_score": r.inherent_score,
                "residual_score": r.residual_score,
                "risk_level": RiskScoringEngine.get_risk_level(r.residual_score),
                "risk_color": RiskScoringEngine.get_risk_color(r.residual_score),
                "treatment_strategy": r.treatment_strategy,
                "status": r.status,
                "is_within_appetite": r.is_within_appetite,
                "risk_owner_name": r.risk_owner_name,
                "next_review_date": r.next_review_date.isoformat() if r.next_review_date else None,
            }
            for r in risks
        ],
    }


@router.post("/", response_model=dict, status_code=201)
async def create_risk(
    risk_data: RiskCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a new risk"""
    service = RiskService(db)
    risk = service.create_risk(risk_data.model_dump())

    return {
        "id": risk.id,
        "reference": risk.reference,
        "message": "Risk created successfully",
    }


@router.get("/{risk_id}", response_model=dict)
async def get_risk(
    risk_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get detailed risk information"""
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    # Get linked controls
    control_mappings = db.query(RiskControlMapping).filter(RiskControlMapping.risk_id == risk_id).all()
    control_ids = [m.control_id for m in control_mappings]
    controls = db.query(RiskControl).filter(RiskControl.id.in_(control_ids)).all() if control_ids else []

    # Get KRIs
    kris = db.query(KeyRiskIndicator).filter(KeyRiskIndicator.risk_id == risk_id).all()

    # Get assessment history
    history = (
        db.query(RiskAssessmentHistory)
        .filter(RiskAssessmentHistory.risk_id == risk_id)
        .order_by(RiskAssessmentHistory.assessment_date.desc())
        .limit(10)
        .all()
    )

    return {
        "id": risk.id,
        "reference": risk.reference,
        "title": risk.title,
        "description": risk.description,
        "category": risk.category,
        "subcategory": risk.subcategory,
        "department": risk.department,
        "location": risk.location,
        "process": risk.process,
        "inherent_likelihood": risk.inherent_likelihood,
        "inherent_impact": risk.inherent_impact,
        "inherent_score": risk.inherent_score,
        "residual_likelihood": risk.residual_likelihood,
        "residual_impact": risk.residual_impact,
        "residual_score": risk.residual_score,
        "target_score": risk.target_score,
        "risk_level": RiskScoringEngine.get_risk_level(risk.residual_score),
        "risk_color": RiskScoringEngine.get_risk_color(risk.residual_score),
        "risk_appetite": risk.risk_appetite,
        "appetite_threshold": risk.appetite_threshold,
        "is_within_appetite": risk.is_within_appetite,
        "treatment_strategy": risk.treatment_strategy,
        "treatment_plan": risk.treatment_plan,
        "treatment_status": risk.treatment_status,
        "status": risk.status,
        "risk_owner_id": risk.risk_owner_id,
        "risk_owner_name": risk.risk_owner_name,
        "review_frequency_days": risk.review_frequency_days,
        "last_review_date": risk.last_review_date.isoformat() if risk.last_review_date else None,
        "next_review_date": risk.next_review_date.isoformat() if risk.next_review_date else None,
        "review_notes": risk.review_notes,
        "is_escalated": risk.is_escalated,
        "escalation_reason": risk.escalation_reason,
        "identified_date": risk.identified_date.isoformat() if risk.identified_date else None,
        "controls": [
            {
                "id": c.id,
                "reference": c.reference,
                "name": c.name,
                "control_type": c.control_type,
                "effectiveness": c.effectiveness,
            }
            for c in controls
        ],
        "kris": [
            {
                "id": k.id,
                "name": k.name,
                "current_value": k.current_value,
                "current_status": k.current_status,
                "last_updated": k.last_updated.isoformat() if k.last_updated else None,
            }
            for k in kris
        ],
        "assessment_history": [
            {
                "date": h.assessment_date.isoformat() if h.assessment_date else None,
                "inherent_score": h.inherent_score,
                "residual_score": h.residual_score,
                "status": h.status,
            }
            for h in history
        ],
    }


@router.put("/{risk_id}", response_model=dict)
async def update_risk(
    risk_id: int,
    risk_data: RiskUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update risk details (not scores)"""
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    update_data = risk_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(risk, key, value)

    risk.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(risk)

    return {"message": "Risk updated successfully", "id": risk.id}


@router.post("/{risk_id}/assess", response_model=dict)
async def assess_risk(
    risk_id: int,
    assessment: RiskAssessmentUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update risk assessment scores"""
    service = RiskService(db)
    try:
        risk = service.update_risk_assessment(risk_id, assessment.model_dump(exclude_unset=True))
        return {
            "message": "Risk assessment updated",
            "inherent_score": risk.inherent_score,
            "residual_score": risk.residual_score,
            "risk_level": RiskScoringEngine.get_risk_level(risk.residual_score),
            "is_within_appetite": risk.is_within_appetite,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{risk_id}", status_code=204)
async def delete_risk(
    risk_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a risk (soft delete by changing status)"""
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    risk.status = "closed"
    risk.updated_at = datetime.utcnow()
    db.commit()


# ============ Heat Map & Matrix Endpoints ============


@router.get("/matrix/config", response_model=dict)
async def get_risk_matrix_config() -> dict[str, Any]:
    """Get risk matrix configuration"""
    return {
        "matrix": RiskScoringEngine.generate_matrix(),
        "likelihood_labels": RiskScoringEngine.LIKELIHOOD_LABELS,
        "likelihood_descriptions": RiskScoringEngine.LIKELIHOOD_DESCRIPTIONS,
        "impact_labels": RiskScoringEngine.IMPACT_LABELS,
        "impact_descriptions": RiskScoringEngine.IMPACT_DESCRIPTIONS,
        "levels": {
            "low": {"color": "#22c55e", "max_score": 4},
            "medium": {"color": "#eab308", "max_score": 9},
            "high": {"color": "#f97316", "max_score": 16},
            "critical": {"color": "#ef4444", "max_score": 25},
        },
    }


@router.get("/heatmap", response_model=dict)
async def get_risk_heat_map(
    category: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get risk heat map data"""
    service = RiskService(db)
    return service.get_heat_map_data(category, department)


@router.get("/trends", response_model=list)
async def get_risk_trends(
    risk_id: Optional[int] = Query(None),
    days: int = Query(365, ge=30, le=1095),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get risk score trends over time"""
    service = RiskService(db)
    return service.get_risk_trends(risk_id, days)


@router.get("/forecast", response_model=list)
async def get_risk_forecast(
    months_ahead: int = Query(6, ge=1, le=12),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get risk trend forecast"""
    service = RiskService(db)
    return service.forecast_risk_trends(months_ahead)


# ============ Bow-Tie Analysis Endpoints ============


@router.get("/{risk_id}/bowtie", response_model=dict)
async def get_bow_tie(
    risk_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get bow-tie diagram data for a risk"""
    service = BowTieService(db)
    try:
        return service.get_bow_tie(risk_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{risk_id}/bowtie/elements", response_model=dict, status_code=201)
async def add_bow_tie_element(
    risk_id: int,
    element: BowTieElementCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Add element to bow-tie diagram"""
    # Verify risk exists
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    service = BowTieService(db)
    bow_tie_element = service.add_bow_tie_element(
        risk_id,
        element.element_type,
        element.title,
        element.description,
        barrier_type=element.barrier_type,
        linked_control_id=element.linked_control_id,
        effectiveness=element.effectiveness,
        is_escalation_factor=element.is_escalation_factor,
    )

    return {
        "id": bow_tie_element.id,
        "message": f"{element.element_type.title()} added to bow-tie",
    }


@router.delete("/{risk_id}/bowtie/elements/{element_id}", status_code=204)
async def delete_bow_tie_element(
    risk_id: int,
    element_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete bow-tie element"""
    element = db.query(BowTieElement).filter(BowTieElement.id == element_id, BowTieElement.risk_id == risk_id).first()

    if not element:
        raise HTTPException(status_code=404, detail="Element not found")

    db.delete(element)
    db.commit()


# ============ KRI Endpoints ============


@router.get("/kris/dashboard", response_model=dict)
async def get_kri_dashboard(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get KRI dashboard summary"""
    service = KRIService(db)
    return service.get_kri_dashboard()


@router.post("/kris", response_model=dict, status_code=201)
async def create_kri(
    kri_data: KRICreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a Key Risk Indicator"""
    # Verify risk exists
    risk = db.query(Risk).filter(Risk.id == kri_data.risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    kri = KeyRiskIndicator(**kri_data.model_dump())
    db.add(kri)
    db.commit()
    db.refresh(kri)

    return {"id": kri.id, "message": "KRI created successfully"}


@router.put("/kris/{kri_id}/value", response_model=dict)
async def update_kri_value(
    kri_id: int,
    value_update: KRIValueUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update KRI value"""
    service = KRIService(db)
    try:
        kri = service.update_kri_value(kri_id, value_update.value)
        return {
            "message": "KRI updated",
            "current_value": kri.current_value,
            "current_status": kri.current_status,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/kris/{kri_id}/history", response_model=list)
async def get_kri_history(
    kri_id: int,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get KRI historical values"""
    kri = db.query(KeyRiskIndicator).filter(KeyRiskIndicator.id == kri_id).first()
    if not kri:
        raise HTTPException(status_code=404, detail="KRI not found")

    return kri.historical_values or []


# ============ Controls Endpoints ============


@router.get("/controls", response_model=list)
async def list_controls(
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all risk controls"""
    controls = db.query(RiskControl).filter(RiskControl.is_active == True).all()

    return [
        {
            "id": c.id,
            "reference": c.reference,
            "name": c.name,
            "description": c.description,
            "control_type": c.control_type,
            "control_nature": c.control_nature,
            "effectiveness": c.effectiveness,
            "control_owner_name": c.control_owner_name,
            "implementation_status": c.implementation_status,
        }
        for c in controls
    ]


@router.post("/controls", response_model=dict, status_code=201)
async def create_control(
    control_data: ControlCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a risk control"""
    count = db.query(RiskControl).count()
    reference = f"CTRL-{(count + 1):04d}"

    control = RiskControl(
        reference=reference,
        **control_data.model_dump(),
    )
    db.add(control)
    db.commit()
    db.refresh(control)

    return {"id": control.id, "reference": reference, "message": "Control created"}


@router.post("/{risk_id}/controls/{control_id}", response_model=dict, status_code=201)
async def link_control_to_risk(
    risk_id: int,
    control_id: int,
    reduces_likelihood: bool = True,
    reduces_impact: bool = False,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Link a control to a risk"""
    # Verify both exist
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    control = db.query(RiskControl).filter(RiskControl.id == control_id).first()

    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")
    if not control:
        raise HTTPException(status_code=404, detail="Control not found")

    # Check if already linked
    existing = (
        db.query(RiskControlMapping)
        .filter(
            RiskControlMapping.risk_id == risk_id,
            RiskControlMapping.control_id == control_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(status_code=400, detail="Control already linked to this risk")

    mapping = RiskControlMapping(
        risk_id=risk_id,
        control_id=control_id,
        reduces_likelihood=reduces_likelihood,
        reduces_impact=reduces_impact,
    )
    db.add(mapping)
    db.commit()

    return {"message": "Control linked to risk"}


# ============ Risk Appetite Endpoints ============


@router.get("/appetite/statements", response_model=list)
async def list_appetite_statements(
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List risk appetite statements by category"""
    statements = db.query(RiskAppetiteStatement).filter(RiskAppetiteStatement.is_active == True).all()

    return [
        {
            "id": s.id,
            "category": s.category,
            "appetite_level": s.appetite_level,
            "max_inherent_score": s.max_inherent_score,
            "max_residual_score": s.max_residual_score,
            "escalation_threshold": s.escalation_threshold,
            "statement": s.statement,
            "approved_by": s.approved_by,
            "approved_date": s.approved_date.isoformat() if s.approved_date else None,
        }
        for s in statements
    ]


# ============ Summary & Statistics ============


@router.get("/summary", response_model=dict)
async def get_risk_summary(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get overall risk register summary"""
    total_risks = db.query(Risk).filter(Risk.status != "closed").count()
    critical_risks = db.query(Risk).filter(Risk.residual_score > 16, Risk.status != "closed").count()
    high_risks = db.query(Risk).filter(Risk.residual_score.between(12, 16), Risk.status != "closed").count()
    medium_risks = db.query(Risk).filter(Risk.residual_score.between(5, 11), Risk.status != "closed").count()
    low_risks = db.query(Risk).filter(Risk.residual_score <= 4, Risk.status != "closed").count()
    outside_appetite = db.query(Risk).filter(Risk.is_within_appetite == False, Risk.status != "closed").count()
    overdue_review = db.query(Risk).filter(Risk.next_review_date < datetime.utcnow(), Risk.status != "closed").count()
    escalated = db.query(Risk).filter(Risk.is_escalated == True, Risk.status != "closed").count()

    # Category breakdown
    categories = (
        db.query(Risk.category, db.func.count(Risk.id)).filter(Risk.status != "closed").group_by(Risk.category).all()
    )

    return {
        "total_risks": total_risks,
        "by_level": {
            "critical": critical_risks,
            "high": high_risks,
            "medium": medium_risks,
            "low": low_risks,
        },
        "outside_appetite": outside_appetite,
        "overdue_review": overdue_review,
        "escalated": escalated,
        "by_category": {cat: count for cat, count in categories},
    }
