"""
Enterprise EnterpriseRisk Register API Routes

Provides endpoints for:
- EnterpriseRisk CRUD operations
- EnterpriseRisk scoring and assessment
- Heat maps and trends
- Bow-tie analysis
- Key EnterpriseRisk Indicators (KRIs)
"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.risk_register import (
    BowTieElement,
    EnterpriseKeyRiskIndicator,
    EnterpriseRisk,
    EnterpriseRiskControl,
    RiskAppetiteStatement,
    RiskAssessmentHistory,
    RiskControlMapping,
)
from src.domain.services.risk_service import (
    BowTieService,
    KRIService,
    RiskScoringEngine,
    RiskService,
)
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter()


# ============ Pydantic Schemas ============


class RiskCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    category: str = Field(
        ..., description="EnterpriseRisk category (strategic, operational, etc.)"
    )
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
    control_nature: str = Field(
        default="manual", description="manual, automated, hybrid"
    )
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
    element_type: str = Field(
        ..., description="cause, consequence, prevention, mitigation"
    )
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    barrier_type: Optional[str] = None
    linked_control_id: Optional[int] = None
    effectiveness: Optional[str] = None
    is_escalation_factor: bool = False


# ============ EnterpriseRisk CRUD Endpoints ============


@router.get("/", response_model=dict)
async def list_risks(
    db: DbSession,
    current_user: CurrentUser,
    category: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None, ge=1, le=25),
    outside_appetite: Optional[bool] = Query(None),
    params: PaginationParams = Depends(),
) -> dict[str, Any]:
    """List risks with filtering options"""
    conditions = [EnterpriseRisk.tenant_id == current_user.tenant_id]

    if category:
        conditions.append(EnterpriseRisk.category == category)
    if department:
        conditions.append(EnterpriseRisk.department == department)
    if status:
        conditions.append(EnterpriseRisk.status == status)
    if min_score:
        conditions.append(EnterpriseRisk.residual_score >= min_score)
    if outside_appetite:
        conditions.append(EnterpriseRisk.is_within_appetite == False)  # noqa: E712

    stmt = select(EnterpriseRisk)
    if conditions:
        stmt = stmt.where(and_(*conditions))

    query = stmt.order_by(EnterpriseRisk.residual_score.desc())
    paginated = await paginate(db, query, params)

    return {
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
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
                "next_review_date": (
                    r.next_review_date.isoformat() if r.next_review_date else None
                ),
            }
            for r in paginated.items
        ],
    }


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_risk(
    risk_data: RiskCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Create a new risk"""
    service = RiskService(db)
    data = risk_data.model_dump()
    data["tenant_id"] = current_user.tenant_id
    risk = await service.create_risk(data)
    await invalidate_tenant_cache(current_user.tenant_id, "risk_register")
    track_metric("risk_register.mutation", 1)

    return {
        "id": risk.id,
        "reference": risk.reference,
        "message": "EnterpriseRisk created successfully",
    }


@router.put("/{risk_id}", response_model=dict)
async def update_risk(
    risk_id: int,
    risk_data: RiskUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Update risk details (not scores)"""
    risk = await get_or_404(
        db, EnterpriseRisk, risk_id, tenant_id=current_user.tenant_id
    )
    apply_updates(risk, risk_data)
    await db.commit()
    await db.refresh(risk)
    await invalidate_tenant_cache(current_user.tenant_id, "risk_register")
    track_metric("risk_register.mutation", 1)

    return {"message": "EnterpriseRisk updated successfully", "id": risk.id}


@router.post("/{risk_id}/assess", response_model=dict)
async def assess_risk(
    risk_id: int,
    assessment: RiskAssessmentUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Update risk assessment scores"""
    await get_or_404(db, EnterpriseRisk, risk_id, tenant_id=current_user.tenant_id)
    service = RiskService(db)
    try:
        risk = await service.update_risk_assessment(
            risk_id, assessment.model_dump(exclude_unset=True)
        )
        return {
            "message": "EnterpriseRisk assessment updated",
            "inherent_score": risk.inherent_score,
            "residual_score": risk.residual_score,
            "risk_level": RiskScoringEngine.get_risk_level(risk.residual_score),
            "is_within_appetite": risk.is_within_appetite,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_risk(
    risk_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Delete a risk (soft delete by changing status)"""
    risk = await get_or_404(
        db, EnterpriseRisk, risk_id, tenant_id=current_user.tenant_id
    )

    risk.status = "closed"
    risk.updated_at = datetime.utcnow()
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "risk_register")
    track_metric("risk_register.mutation", 1)


# ============ Heat Map & Matrix Endpoints ============


@router.get("/matrix/config", response_model=dict)
async def get_risk_matrix_config(
    current_user: CurrentUser,
) -> dict[str, Any]:
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
    db: DbSession,
    current_user: CurrentUser,
    category: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
) -> dict[str, Any]:
    """Get risk heat map data"""
    service = RiskService(db)
    return await service.get_heat_map_data(category, department)


@router.get("/trends", response_model=list)
async def get_risk_trends(
    db: DbSession,
    current_user: CurrentUser,
    risk_id: Optional[int] = Query(None),
    days: int = Query(365, ge=30, le=1095),
) -> list[dict[str, Any]]:
    """Get risk score trends over time"""
    service = RiskService(db)
    return await service.get_risk_trends(risk_id, days)


@router.get("/forecast", response_model=list)
async def get_risk_forecast(
    db: DbSession,
    current_user: CurrentUser,
    months_ahead: int = Query(6, ge=1, le=12),
) -> list[dict[str, Any]]:
    """Get risk trend forecast"""
    service = RiskService(db)
    return await service.forecast_risk_trends(months_ahead)


# ============ Bow-Tie Analysis Endpoints ============


@router.get("/{risk_id}/bowtie", response_model=dict)
async def get_bow_tie(
    risk_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get bow-tie diagram data for a risk"""
    await get_or_404(db, EnterpriseRisk, risk_id, tenant_id=current_user.tenant_id)
    service = BowTieService(db)
    try:
        return await service.get_bow_tie(risk_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{risk_id}/bowtie/elements",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
async def add_bow_tie_element(
    risk_id: int,
    element: BowTieElementCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Add element to bow-tie diagram"""
    await get_or_404(db, EnterpriseRisk, risk_id, tenant_id=current_user.tenant_id)

    service = BowTieService(db)
    bow_tie_element = await service.add_bow_tie_element(
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


@router.delete(
    "/{risk_id}/bowtie/elements/{element_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_bow_tie_element(
    risk_id: int,
    element_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Delete bow-tie element"""
    result = await db.execute(
        select(BowTieElement).where(
            BowTieElement.id == element_id,
            BowTieElement.risk_id == risk_id,
            BowTieElement.tenant_id == current_user.tenant_id,
        )
    )
    element = result.scalar_one_or_none()

    if not element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Element not found"
        )

    await db.delete(element)
    await db.commit()


# ============ KRI Endpoints ============


@router.get("/kris/dashboard", response_model=dict)
async def get_kri_dashboard(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get KRI dashboard summary"""
    service = KRIService(db)
    return await service.get_kri_dashboard()


@router.post("/kris", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_kri(
    kri_data: KRICreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Create a Key EnterpriseRisk Indicator"""
    await get_or_404(
        db, EnterpriseRisk, kri_data.risk_id, tenant_id=current_user.tenant_id
    )

    kri = EnterpriseKeyRiskIndicator(**kri_data.model_dump())
    db.add(kri)
    await db.commit()
    await db.refresh(kri)
    await invalidate_tenant_cache(current_user.tenant_id, "risk_register")
    track_metric("risk_register.mutation", 1)

    return {"id": kri.id, "message": "KRI created successfully"}


@router.put("/kris/{kri_id}/value", response_model=dict)
async def update_kri_value(
    kri_id: int,
    value_update: KRIValueUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Update KRI value"""
    service = KRIService(db)
    try:
        kri = await service.update_kri_value(kri_id, value_update.value)
        return {
            "message": "KRI updated",
            "current_value": kri.current_value,
            "current_status": kri.current_status,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/kris/{kri_id}/history", response_model=list)
async def get_kri_history(
    kri_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[dict[str, Any]]:
    """Get KRI historical values"""
    kri = await get_or_404(db, EnterpriseKeyRiskIndicator, kri_id)

    return kri.historical_values or []


# ============ Controls Endpoints ============


@router.get("/controls", response_model=list)
async def list_controls(
    db: DbSession,
    current_user: CurrentUser,
) -> list[dict[str, Any]]:
    """List all risk controls"""
    result = await db.execute(
        select(EnterpriseRiskControl).where(
            EnterpriseRiskControl.is_active == True
        )  # noqa: E712
    )
    controls = result.scalars().all()

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


@router.post("/controls", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_control(
    control_data: ControlCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Create a risk control"""
    count = (
        await db.scalar(select(func.count()).select_from(EnterpriseRiskControl)) or 0
    )
    reference = f"CTRL-{(count + 1):04d}"

    control = EnterpriseRiskControl(
        reference=reference,
        **control_data.model_dump(),
    )
    db.add(control)
    await db.commit()
    await db.refresh(control)
    await invalidate_tenant_cache(current_user.tenant_id, "risk_register")
    track_metric("risk_register.mutation", 1)

    return {"id": control.id, "reference": reference, "message": "Control created"}


@router.post(
    "/{risk_id}/controls/{control_id}",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
async def link_control_to_risk(
    risk_id: int,
    control_id: int,
    db: DbSession,
    current_user: CurrentUser,
    reduces_likelihood: bool = True,
    reduces_impact: bool = False,
) -> dict[str, Any]:
    """Link a control to a risk"""
    await get_or_404(db, EnterpriseRisk, risk_id, tenant_id=current_user.tenant_id)
    await get_or_404(db, EnterpriseRiskControl, control_id)

    existing = (
        await db.execute(
            select(RiskControlMapping).where(
                RiskControlMapping.risk_id == risk_id,
                RiskControlMapping.control_id == control_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Control already linked to this risk",
        )

    mapping = RiskControlMapping(
        risk_id=risk_id,
        control_id=control_id,
        reduces_likelihood=reduces_likelihood,
        reduces_impact=reduces_impact,
    )
    db.add(mapping)
    await db.commit()

    return {"message": "Control linked to risk"}


# ============ EnterpriseRisk Appetite Endpoints ============


@router.get("/appetite/statements", response_model=list)
async def list_appetite_statements(
    db: DbSession,
    current_user: CurrentUser,
) -> list[dict[str, Any]]:
    """List risk appetite statements by category"""
    result = await db.execute(
        select(RiskAppetiteStatement).where(
            RiskAppetiteStatement.is_active == True
        )  # noqa: E712
    )
    statements = result.scalars().all()

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
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get overall risk register summary"""
    tenant_filter = EnterpriseRisk.tenant_id == current_user.tenant_id
    total_risks = await db.scalar(
        select(func.count())
        .select_from(EnterpriseRisk)
        .where(tenant_filter, EnterpriseRisk.status != "closed")
    )
    critical_risks = await db.scalar(
        select(func.count())
        .select_from(EnterpriseRisk)
        .where(
            tenant_filter,
            EnterpriseRisk.residual_score > 16,
            EnterpriseRisk.status != "closed",
        )
    )
    high_risks = await db.scalar(
        select(func.count())
        .select_from(EnterpriseRisk)
        .where(
            tenant_filter,
            EnterpriseRisk.residual_score.between(12, 16),
            EnterpriseRisk.status != "closed",
        )
    )
    medium_risks = await db.scalar(
        select(func.count())
        .select_from(EnterpriseRisk)
        .where(
            tenant_filter,
            EnterpriseRisk.residual_score.between(5, 11),
            EnterpriseRisk.status != "closed",
        )
    )
    low_risks = await db.scalar(
        select(func.count())
        .select_from(EnterpriseRisk)
        .where(
            tenant_filter,
            EnterpriseRisk.residual_score <= 4,
            EnterpriseRisk.status != "closed",
        )
    )
    outside_appetite = await db.scalar(
        select(func.count())
        .select_from(EnterpriseRisk)
        .where(
            tenant_filter,
            EnterpriseRisk.is_within_appetite == False,
            EnterpriseRisk.status != "closed",
        )  # noqa: E712
    )
    overdue_review = await db.scalar(
        select(func.count())
        .select_from(EnterpriseRisk)
        .where(
            tenant_filter,
            EnterpriseRisk.next_review_date < datetime.utcnow(),
            EnterpriseRisk.status != "closed",
        )
    )
    escalated = await db.scalar(
        select(func.count())
        .select_from(EnterpriseRisk)
        .where(
            tenant_filter,
            EnterpriseRisk.is_escalated == True,
            EnterpriseRisk.status != "closed",
        )  # noqa: E712
    )

    result = await db.execute(
        select(EnterpriseRisk.category, func.count(EnterpriseRisk.id))
        .where(tenant_filter, EnterpriseRisk.status != "closed")
        .group_by(EnterpriseRisk.category)
    )
    categories = result.all()

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


# ============ Individual Risk Detail (after all literal GET paths) ============


@router.get("/{risk_id}", response_model=dict)
async def get_risk(
    risk_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get detailed risk information"""
    risk = await get_or_404(
        db, EnterpriseRisk, risk_id, tenant_id=current_user.tenant_id
    )

    result = await db.execute(
        select(RiskControlMapping).where(RiskControlMapping.risk_id == risk_id)
    )
    control_mappings = result.scalars().all()
    control_ids = [m.control_id for m in control_mappings]
    if control_ids:
        result = await db.execute(
            select(EnterpriseRiskControl).where(
                EnterpriseRiskControl.id.in_(control_ids)
            )
        )
        controls = result.scalars().all()
    else:
        controls = []

    result = await db.execute(
        select(EnterpriseKeyRiskIndicator).where(
            EnterpriseKeyRiskIndicator.risk_id == risk_id
        )
    )
    kris = result.scalars().all()

    result = await db.execute(
        select(RiskAssessmentHistory)
        .where(RiskAssessmentHistory.risk_id == risk_id)
        .order_by(RiskAssessmentHistory.assessment_date.desc())
        .limit(10)
    )
    history = result.scalars().all()

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
        "last_review_date": (
            risk.last_review_date.isoformat() if risk.last_review_date else None
        ),
        "next_review_date": (
            risk.next_review_date.isoformat() if risk.next_review_date else None
        ),
        "review_notes": risk.review_notes,
        "is_escalated": risk.is_escalated,
        "escalation_reason": risk.escalation_reason,
        "identified_date": (
            risk.identified_date.isoformat() if risk.identified_date else None
        ),
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
