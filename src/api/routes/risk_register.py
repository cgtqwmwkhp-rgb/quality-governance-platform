"""
Enterprise EnterpriseRisk Register API Routes

Provides endpoints for:
- EnterpriseRisk CRUD operations
- EnterpriseRisk scoring and assessment
- Heat maps and trends
- Bow-tie analysis
- Key EnterpriseRisk Indicators (KRIs)
"""

import math
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.risk_register import (
    AssessmentHistoryItem,
    RiskActionCreate,
    RiskActionItem,
    RiskActionListResponse,
    RiskActivityEventItem,
    RiskActivityListResponse,
    RiskNoteCreate,
    RiskNoteItem,
    RiskNoteListResponse,
    RiskOwnerResponse,
    RiskOwnerUpdate,
    RiskProfileResponse,
    RiskUpstreamItem,
    RiskUpstreamResponse,
)
from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.risk_register import (
    BowTieElement,
    EnterpriseKeyRiskIndicator,
    EnterpriseRisk,
    EnterpriseRiskControl,
    RiskActivityEvent,
    RiskAppetiteStatement,
    RiskAssessmentHistory,
    RiskControlMapping,
    RiskNote,
)
from src.domain.models.user import User
from src.domain.services.audit_escalation_risk_title import backfill_descriptive_escalation_titles
from src.domain.services.risk_service import (
    BowTieService,
    KRIService,
    RiskScoringEngine,
    RiskService,
    read_score_trend_from_tags,
)
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache


def _optional_risk_level(score: Optional[int]) -> Optional[str]:
    if score is None:
        return None
    return RiskScoringEngine.get_risk_level(score)


router = APIRouter()


def _naive_utc_now() -> datetime:
    """Match the risk_register model's naive-UTC DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _get_tenant_risk_or_404(
    db: DbSession,
    tenant_id: int,
    risk_id: int,
) -> EnterpriseRisk:
    result = await db.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.id == risk_id,
            EnterpriseRisk.tenant_id == tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("EnterpriseRisk not found")
    return risk


async def _batch_resolve_user_emails(db: DbSession, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    result = await db.execute(select(User.id, User.email).where(User.id.in_(user_ids)))
    return {row.id: row.email for row in result.all() if row.email}


async def _resolve_user_email(db: DbSession, user_id: int) -> Optional[str]:
    result = await db.execute(select(User.email).where(User.id == user_id))
    return result.scalar_one_or_none()


def _register_visibility_clause():
    """Omit import-sourced risks that are still awaiting triage from headline views."""
    return or_(
        EnterpriseRisk.suggestion_triage_status.is_(None),
        EnterpriseRisk.suggestion_triage_status == "accepted",
    )


# ============ Pydantic Schemas ============


class RiskCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10)
    category: str = Field(..., description="EnterpriseRisk category (strategic, operational, etc.)")
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
    status: Optional[Literal["draft", "active", "monitoring", "mitigated", "closed", "archived"]] = None
    risk_owner_id: Optional[int] = None
    risk_owner_name: Optional[str] = None


class RiskAssessmentUpdate(BaseModel):
    inherent_likelihood: Optional[int] = Field(None, ge=1, le=5)
    inherent_impact: Optional[int] = Field(None, ge=1, le=5)
    residual_likelihood: Optional[int] = Field(None, ge=1, le=5)
    residual_impact: Optional[int] = Field(None, ge=1, le=5)
    review_notes: Optional[str] = None
    assessment_notes: Optional[str] = None
    last_review_date: Optional[datetime] = None
    next_review_date: Optional[datetime] = None
    trend: Optional[Literal["increasing", "stable", "decreasing"]] = Field(
        None,
        description="Manual net-score trend override; auto-derived from last two scores when omitted",
    )


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


class SuggestionTriageResolve(BaseModel):
    decision: Literal["accept", "reject"]
    notes: Optional[str] = Field(None, max_length=2000)


# ============ EnterpriseRisk CRUD Endpoints ============


@router.get("", response_model=dict, include_in_schema=False)
@router.get("/", response_model=dict)
async def list_risks(
    current_user: CurrentUser,
    db: DbSession,
    category: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Match reference, title, or owner (ilike)"),
    min_score: Optional[int] = Query(None, ge=1, le=25),
    outside_appetite: Optional[bool] = Query(None),
    residual_likelihood: Optional[int] = Query(None, ge=1, le=5),
    residual_impact: Optional[int] = Query(None, ge=1, le=5),
    inherent_likelihood: Optional[int] = Query(None, ge=1, le=5),
    inherent_impact: Optional[int] = Query(None, ge=1, le=5),
    suggestion_triage: Optional[str] = Query(
        None,
        description="pending=triage queue only; all=no triage filter; default=hide pending suggestions",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """List risks with filtering options"""
    base_stmt = select(EnterpriseRisk).where(EnterpriseRisk.tenant_id == current_user.tenant_id)

    if suggestion_triage == "pending":
        base_stmt = base_stmt.where(EnterpriseRisk.suggestion_triage_status == "pending")
    elif suggestion_triage == "all":
        pass
    else:
        base_stmt = base_stmt.where(_register_visibility_clause())

    if category:
        base_stmt = base_stmt.where(EnterpriseRisk.category == category)
    if department:
        base_stmt = base_stmt.where(EnterpriseRisk.department == department)
    if status:
        base_stmt = base_stmt.where(EnterpriseRisk.status == status)
    search_q = search if isinstance(search, str) else None
    if search_q and search_q.strip():
        needle = f"%{search_q.strip()}%"
        base_stmt = base_stmt.where(
            or_(
                EnterpriseRisk.reference.ilike(needle),
                EnterpriseRisk.title.ilike(needle),
                EnterpriseRisk.risk_owner_name.ilike(needle),
            )
        )
    if min_score:
        base_stmt = base_stmt.where(EnterpriseRisk.residual_score >= min_score)
    if outside_appetite:
        base_stmt = base_stmt.where(EnterpriseRisk.is_within_appetite == False)  # noqa: E712
    if residual_likelihood is not None:
        base_stmt = base_stmt.where(EnterpriseRisk.residual_likelihood == residual_likelihood)
    if residual_impact is not None:
        base_stmt = base_stmt.where(EnterpriseRisk.residual_impact == residual_impact)
    if inherent_likelihood is not None:
        base_stmt = base_stmt.where(EnterpriseRisk.inherent_likelihood == inherent_likelihood)
    if inherent_impact is not None:
        base_stmt = base_stmt.where(EnterpriseRisk.inherent_impact == inherent_impact)

    count_result = await db.execute(select(func.count()).select_from(base_stmt.subquery()))
    total = count_result.scalar_one()

    data_result = await db.execute(base_stmt.order_by(EnterpriseRisk.residual_score.desc()).offset(skip).limit(limit))
    risks = data_result.scalars().all()

    return {
        "total": total,
        "page": (skip // limit) + 1,
        "page_size": limit,
        "items": [
            {
                "id": r.id,
                "reference": r.reference,
                "title": r.title,
                "category": r.category,
                "department": r.department,
                "inherent_score": r.inherent_score,
                "inherent_likelihood": r.inherent_likelihood,
                "inherent_impact": r.inherent_impact,
                "residual_score": r.residual_score,
                "residual_likelihood": r.residual_likelihood,
                "residual_impact": r.residual_impact,
                "risk_level": RiskScoringEngine.get_risk_level(r.residual_score),
                "risk_color": RiskScoringEngine.get_risk_color(r.residual_score),
                "treatment_strategy": r.treatment_strategy,
                "status": r.status,
                "is_within_appetite": r.is_within_appetite,
                "is_escalated": r.is_escalated,
                "escalation_reason": r.escalation_reason,
                "risk_owner_name": r.risk_owner_name,
                "next_review_date": (r.next_review_date.isoformat() if r.next_review_date else None),
                "updated_at": (r.updated_at.isoformat() if getattr(r, "updated_at", None) else None),
                # Tag-persisted net trend only — no history N+1; null when unknown (FE honesty).
                "trend": read_score_trend_from_tags(getattr(r, "tags", None)),
                "linked_audits": r.linked_audits or [],
                "linked_actions": r.linked_actions or [],
                "linked_incidents": r.linked_incidents or [],
                "suggestion_triage_status": r.suggestion_triage_status,
            }
            for r in risks
        ],
    }


@router.post("/", response_model=dict, status_code=201)
async def create_risk(
    current_user: Annotated[User, Depends(require_permission("risk:create"))],
    risk_data: RiskCreate,
    db: DbSession,
) -> dict[str, Any]:
    """Create a new risk"""
    service = RiskService(db)
    data = risk_data.model_dump()
    data["tenant_id"] = current_user.tenant_id
    risk = await service.create_risk(data)

    return {
        "id": risk.id,
        "reference": risk.reference,
        "message": "EnterpriseRisk created successfully",
    }


@router.post("/backfill-descriptive-titles", response_model=dict)
async def backfill_descriptive_titles(
    current_user: Annotated[User, Depends(require_permission("risk:update"))],
    db: DbSession,
    commit: bool = Query(
        False,
        description="When false (default), dry-run only. When true, persist title upgrades.",
    ),
) -> dict[str, Any]:
    """Rewrite legacy audit-escalation risk titles using linked finding titles."""
    if current_user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Tenant context required")
    result = await backfill_descriptive_escalation_titles(
        db,
        current_user.tenant_id,
        commit=commit,
    )
    if commit and result.get("updated_count", 0):
        await invalidate_tenant_cache(current_user.tenant_id, "risk_register")
        await invalidate_tenant_cache(current_user.tenant_id, "risk-register")
    return result


# ============ Heat Map & Matrix Endpoints ============


@router.get("/matrix/config", response_model=dict)
async def get_risk_matrix_config(current_user: CurrentUser) -> dict[str, Any]:
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
    current_user: CurrentUser,
    db: DbSession,
    category: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    score_type: Literal["residual", "inherent", "delta"] = Query("residual"),
) -> dict[str, Any]:
    """Get interactive risk heat map data (residual / inherent / delta)."""
    service = RiskService(db)
    return await service.get_heat_map_data(
        category=category,
        department=department,
        status=status,
        tenant_id=current_user.tenant_id,
        score_type=score_type,
    )


@router.get("/trends")
async def get_risk_trends(
    current_user: CurrentUser,
    db: DbSession,
    risk_id: Optional[int] = Query(None),
    days: int = Query(365, ge=30, le=1095),
    include_movers: bool = Query(False),
) -> Any:
    """Get risk score trends over time.

    Default: list of monthly points (backward compatible).
    include_movers=true: {series, top_movers} for executive sparklines.
    """
    service = RiskService(db)
    return await service.get_risk_trends(
        risk_id,
        days,
        tenant_id=current_user.tenant_id,
        include_movers=include_movers,
    )


@router.get("/forecast", response_model=list)
async def get_risk_forecast(
    current_user: CurrentUser,
    db: DbSession,
    months_ahead: int = Query(6, ge=1, le=12),
) -> list[dict[str, Any]]:
    """Get risk trend forecast"""
    service = RiskService(db)
    return await service.forecast_risk_trends(months_ahead, tenant_id=current_user.tenant_id)


# ============ Bow-Tie Analysis Endpoints ============


@router.get("/{risk_id}/bowtie", response_model=dict)
async def get_bow_tie(
    current_user: CurrentUser,
    risk_id: int,
    db: DbSession,
) -> dict[str, Any]:
    """Get bow-tie diagram data for a risk"""
    result = await db.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.id == risk_id,
            EnterpriseRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("EnterpriseRisk not found")
    service = BowTieService(db)
    try:
        return await service.get_bow_tie(risk_id)
    except ValueError as e:
        raise NotFoundError(str(e))


@router.post("/{risk_id}/bowtie/elements", response_model=dict, status_code=201)
async def add_bow_tie_element(
    current_user: Annotated[User, Depends(require_permission("risk:update"))],
    risk_id: int,
    element: BowTieElementCreate,
    db: DbSession,
) -> dict[str, Any]:
    """Add element to bow-tie diagram"""
    result = await db.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.id == risk_id,
            EnterpriseRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("EnterpriseRisk not found")

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
        tenant_id=risk.tenant_id,
    )

    return {
        "id": bow_tie_element.id,
        "message": f"{element.element_type.title()} added to bow-tie",
    }


@router.delete("/{risk_id}/bowtie/elements/{element_id}", status_code=204)
async def delete_bow_tie_element(
    current_user: Annotated[User, Depends(require_permission("risk:update"))],
    risk_id: int,
    element_id: int,
    db: DbSession,
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
        raise NotFoundError("Element not found")

    await db.delete(element)
    await db.commit()


# ============ KRI Endpoints ============


@router.get("/kris/dashboard", response_model=dict)
async def get_kri_dashboard(
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, Any]:
    """Get KRI dashboard summary"""
    service = KRIService(db)
    return await service.get_kri_dashboard(tenant_id=current_user.tenant_id)


@router.post("/kris", response_model=dict, status_code=201)
async def create_kri(
    current_user: Annotated[User, Depends(require_permission("risk:create"))],
    kri_data: KRICreate,
    db: DbSession,
) -> dict[str, Any]:
    """Create a Key EnterpriseRisk Indicator"""
    result = await db.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.id == kri_data.risk_id,
            EnterpriseRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("EnterpriseRisk not found")

    kri = EnterpriseKeyRiskIndicator(
        **kri_data.model_dump(),
        tenant_id=risk.tenant_id,
    )
    db.add(kri)
    await db.commit()
    await db.refresh(kri)

    return {"id": kri.id, "message": "KRI created successfully"}


@router.put("/kris/{kri_id}/value", response_model=dict)
async def update_kri_value(
    current_user: Annotated[User, Depends(require_permission("risk:update"))],
    kri_id: int,
    value_update: KRIValueUpdate,
    db: DbSession,
) -> dict[str, Any]:
    """Update KRI value"""
    result = await db.execute(select(EnterpriseKeyRiskIndicator).where(EnterpriseKeyRiskIndicator.id == kri_id))
    kri = result.scalar_one_or_none()
    if not kri:
        raise NotFoundError("KRI not found")

    result = await db.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.id == kri.risk_id,
            EnterpriseRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("KRI not found")

    service = KRIService(db)
    try:
        kri = await service.update_kri_value(kri_id, value_update.value)
        return {
            "message": "KRI updated",
            "current_value": kri.current_value,
            "current_status": kri.current_status,
        }
    except ValueError as e:
        raise NotFoundError(str(e))


@router.get("/kris/{kri_id}/history", response_model=list)
async def get_kri_history(
    current_user: CurrentUser,
    kri_id: int,
    db: DbSession,
) -> list[dict[str, Any]]:
    """Get KRI historical values"""
    result = await db.execute(select(EnterpriseKeyRiskIndicator).where(EnterpriseKeyRiskIndicator.id == kri_id))
    kri = result.scalar_one_or_none()
    if not kri:
        raise NotFoundError("KRI not found")

    result = await db.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.id == kri.risk_id,
            EnterpriseRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("KRI not found")

    return kri.historical_values or []


# ============ Controls Endpoints ============


@router.get("/controls", response_model=list)
async def list_controls(
    current_user: CurrentUser,
    db: DbSession,
) -> list[dict[str, Any]]:
    """List all risk controls scoped to tenant."""
    result = await db.execute(
        select(EnterpriseRiskControl).where(
            EnterpriseRiskControl.is_active == True,  # noqa: E712
            EnterpriseRiskControl.tenant_id == current_user.tenant_id,
        )
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


@router.post("/controls", response_model=dict, status_code=201)
async def create_control(
    current_user: Annotated[User, Depends(require_permission("risk:create"))],
    control_data: ControlCreate,
    db: DbSession,
) -> dict[str, Any]:
    """Create a risk control (EnterpriseRiskControl has no tenant_id; auth required)"""
    count_result = await db.execute(select(func.count(EnterpriseRiskControl.id)))
    count = count_result.scalar_one()
    reference = f"CTRL-{(count + 1):04d}"

    control = EnterpriseRiskControl(
        reference=reference,
        tenant_id=current_user.tenant_id,
        **control_data.model_dump(),
    )
    db.add(control)
    await db.commit()
    await db.refresh(control)

    return {"id": control.id, "reference": reference, "message": "Control created"}


@router.post("/{risk_id}/controls/{control_id}", response_model=dict, status_code=201)
async def link_control_to_risk(
    current_user: Annotated[User, Depends(require_permission("risk:update"))],
    risk_id: int,
    control_id: int,
    db: DbSession,
    reduces_likelihood: bool = True,
    reduces_impact: bool = False,
) -> dict[str, Any]:
    """Link a control to a risk"""
    result = await db.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.id == risk_id,
            EnterpriseRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()

    result = await db.execute(select(EnterpriseRiskControl).where(EnterpriseRiskControl.id == control_id))
    control = result.scalar_one_or_none()

    if not risk:
        raise NotFoundError("EnterpriseRisk not found")
    if not control:
        raise NotFoundError("Control not found")

    result = await db.execute(
        select(RiskControlMapping).where(
            RiskControlMapping.risk_id == risk_id,
            RiskControlMapping.control_id == control_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise BadRequestError("Control already linked to this risk")

    mapping = RiskControlMapping(
        risk_id=risk_id,
        control_id=control_id,
        reduces_likelihood=reduces_likelihood,
        reduces_impact=reduces_impact,
        tenant_id=risk.tenant_id,
    )
    db.add(mapping)
    await db.commit()

    return {"message": "Control linked to risk"}


# ============ EnterpriseRisk Appetite Endpoints ============


@router.get("/appetite/statements", response_model=list)
async def list_appetite_statements(
    current_user: CurrentUser,
    db: DbSession,
) -> list[dict[str, Any]]:
    """List risk appetite statements by category, scoped to tenant."""
    result = await db.execute(
        select(RiskAppetiteStatement).where(
            RiskAppetiteStatement.is_active == True,  # noqa: E712
            RiskAppetiteStatement.tenant_id == current_user.tenant_id,
        )
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
    current_user: CurrentUser,
    db: DbSession,
    category: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
) -> dict[str, Any]:
    """Get overall risk register summary (canonical bands aligned with RiskScoringEngine)."""
    tenant_filter = EnterpriseRisk.tenant_id == current_user.tenant_id
    vis = _register_visibility_clause()
    status_clause = EnterpriseRisk.status == status if status else EnterpriseRisk.status != "closed"
    base = [status_clause, tenant_filter, vis]
    if category:
        base.append(EnterpriseRisk.category == category)
    if department:
        base.append(EnterpriseRisk.department == department)

    total_result = await db.execute(select(func.count(EnterpriseRisk.id)).where(*base))
    total_risks = total_result.scalar_one()

    # Canonical: low ≤4, medium 5–9, high 10–16, critical ≥17
    critical_result = await db.execute(
        select(func.count(EnterpriseRisk.id)).where(EnterpriseRisk.residual_score >= 17, *base)
    )
    critical_risks = critical_result.scalar_one()

    high_result = await db.execute(
        select(func.count(EnterpriseRisk.id)).where(EnterpriseRisk.residual_score.between(10, 16), *base)
    )
    high_risks = high_result.scalar_one()

    medium_result = await db.execute(
        select(func.count(EnterpriseRisk.id)).where(EnterpriseRisk.residual_score.between(5, 9), *base)
    )
    medium_risks = medium_result.scalar_one()

    low_result = await db.execute(
        select(func.count(EnterpriseRisk.id)).where(EnterpriseRisk.residual_score <= 4, *base)
    )
    low_risks = low_result.scalar_one()

    appetite_result = await db.execute(
        select(func.count(EnterpriseRisk.id)).where(
            EnterpriseRisk.is_within_appetite == False,  # noqa: E712
            *base,
        )
    )
    outside_appetite = appetite_result.scalar_one()

    overdue_result = await db.execute(
        select(func.count(EnterpriseRisk.id)).where(
            EnterpriseRisk.next_review_date < _naive_utc_now(),
            *base,
        )
    )
    overdue_review = overdue_result.scalar_one()

    escalated_result = await db.execute(
        select(func.count(EnterpriseRisk.id)).where(
            EnterpriseRisk.is_escalated == True,  # noqa: E712
            *base,
        )
    )
    escalated = escalated_result.scalar_one()

    cat_result = await db.execute(
        select(EnterpriseRisk.category, func.count(EnterpriseRisk.id)).where(*base).group_by(EnterpriseRisk.category)
    )
    categories = cat_result.all()

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
        "filters_applied": {"category": category, "department": department, "status": status},
    }


@router.post("/{risk_id}/suggestion-triage", response_model=dict)
async def resolve_suggestion_triage(
    risk_id: int,
    body: SuggestionTriageResolve,
    current_user: Annotated[User, Depends(require_permission("risk:update"))],
    db: DbSession,
) -> dict[str, Any]:
    """Accept or reject an enterprise risk raised from external audit import triage."""
    result = await db.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.id == risk_id,
            EnterpriseRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("EnterpriseRisk not found")
    if risk.suggestion_triage_status != "pending":
        raise BadRequestError("Risk is not awaiting import triage")

    if body.decision == "accept":
        risk.suggestion_triage_status = "accepted"
        risk.is_escalated = True
        base_reason = "Accepted from import triage."
        risk.escalation_reason = (f"{base_reason} {body.notes}".strip() if body.notes else base_reason)[:500]
    else:
        risk.suggestion_triage_status = "rejected"
        risk.status = "closed"
        risk.is_escalated = False
        reject_note = "Import triage rejected."
        if body.notes:
            reject_note = f"{reject_note} {body.notes}"
        prev = (risk.review_notes or "").strip()
        risk.review_notes = f"{prev}\n{reject_note}".strip()[:4000]

    risk.updated_at = _naive_utc_now()
    await db.commit()
    if current_user.tenant_id is not None:
        await invalidate_tenant_cache(current_user.tenant_id, "risk-register")
        await invalidate_tenant_cache(current_user.tenant_id, "risks")
    return {
        "id": risk.id,
        "reference": risk.reference,
        "suggestion_triage_status": risk.suggestion_triage_status,
        "status": risk.status,
    }


@router.get("/{risk_id}/profile", response_model=RiskProfileResponse)
async def get_risk_profile(
    current_user: CurrentUser,
    risk_id: int,
    db: DbSession,
    history_limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> RiskProfileResponse:
    """Typed risk profile (Excel Risk Card shell) — tenant fail-closed."""
    result = await db.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.id == risk_id,
            EnterpriseRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("EnterpriseRisk not found")

    history_result = await db.execute(
        select(RiskAssessmentHistory)
        .where(
            RiskAssessmentHistory.risk_id == risk_id,
            RiskAssessmentHistory.tenant_id == current_user.tenant_id,
        )
        .order_by(RiskAssessmentHistory.assessment_date.desc())
        .limit(history_limit)
    )
    history = history_result.scalars().all()

    service = RiskService(db)
    score_trend = service.resolve_score_trend(risk, list(history))

    return RiskProfileResponse(
        id=risk.id,
        reference=risk.reference,
        title=risk.title,
        description=risk.description,
        category=risk.category,
        status=risk.status,
        treatment=risk.treatment_strategy,
        inherent_likelihood=risk.inherent_likelihood,
        inherent_impact=risk.inherent_impact,
        inherent_score=risk.inherent_score,
        inherent_level=_optional_risk_level(risk.inherent_score),
        residual_likelihood=risk.residual_likelihood,
        residual_impact=risk.residual_impact,
        residual_score=risk.residual_score,
        residual_level=_optional_risk_level(risk.residual_score),
        trend=score_trend,
        risk_owner_id=risk.risk_owner_id,
        risk_owner_name=risk.risk_owner_name,
        last_review_date=(risk.last_review_date.isoformat() if risk.last_review_date else None),
        next_review_date=(risk.next_review_date.isoformat() if risk.next_review_date else None),
        updated_at=(risk.updated_at.isoformat() if risk.updated_at else None),
        created_at=(risk.created_at.isoformat() if risk.created_at else None),
        assessment_history=[
            AssessmentHistoryItem(
                date=h.assessment_date.isoformat() if h.assessment_date else None,
                inherent_score=h.inherent_score,
                residual_score=h.residual_score,
                status=h.status,
            )
            for h in history
        ],
        linked_actions=list(risk.linked_actions or []),
        review_notes=risk.review_notes,
    )


@router.get("/{risk_id}/notes", response_model=RiskNoteListResponse)
async def list_risk_notes(
    current_user: CurrentUser,
    risk_id: int,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> RiskNoteListResponse:
    """List risk commentary notes (newest first, paginated)."""
    await _get_tenant_risk_or_404(db, current_user.tenant_id, risk_id)

    filters = [
        RiskNote.risk_id == risk_id,
        RiskNote.tenant_id == current_user.tenant_id,
    ]
    total = await db.scalar(select(func.count(RiskNote.id)).where(*filters)) or 0
    query = (
        select(RiskNote)
        .where(*filters)
        .order_by(RiskNote.created_at.desc(), RiskNote.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    rows = result.scalars().all()
    author_ids = {n.created_by_id for n in rows}
    email_map = await _batch_resolve_user_emails(db, author_ids)

    return RiskNoteListResponse(
        items=[
            RiskNoteItem(
                id=n.id,
                risk_id=n.risk_id,
                body=n.body,
                created_by_id=n.created_by_id,
                created_by_email=email_map.get(n.created_by_id),
                created_at=n.created_at.isoformat() if n.created_at else None,
            )
            for n in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


@router.post("/{risk_id}/notes", response_model=RiskNoteItem, status_code=status.HTTP_201_CREATED)
async def create_risk_note(
    current_user: Annotated[User, Depends(require_permission("risk:update"))],
    risk_id: int,
    body: RiskNoteCreate,
    db: DbSession,
) -> RiskNoteItem:
    """Append a commentary note on a risk."""
    risk = await _get_tenant_risk_or_404(db, current_user.tenant_id, risk_id)
    service = RiskService(db)
    note = await service.append_risk_note(
        risk,
        body=body.body,
        created_by_id=current_user.id,
    )
    author_email = await _resolve_user_email(db, current_user.id)
    if current_user.tenant_id is not None:
        await invalidate_tenant_cache(current_user.tenant_id, "risk-register")
    return RiskNoteItem(
        id=note.id,
        risk_id=note.risk_id,
        body=note.body,
        created_by_id=note.created_by_id,
        created_by_email=author_email,
        created_at=note.created_at.isoformat() if note.created_at else None,
    )


@router.get("/{risk_id}/activity", response_model=RiskActivityListResponse)
async def list_risk_activity(
    current_user: CurrentUser,
    risk_id: int,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    event_type: Annotated[Optional[str], Query(max_length=64)] = None,
) -> RiskActivityListResponse:
    """List typed risk activity audit events (newest first, paginated)."""
    await _get_tenant_risk_or_404(db, current_user.tenant_id, risk_id)

    filters = [
        RiskActivityEvent.risk_id == risk_id,
        RiskActivityEvent.tenant_id == current_user.tenant_id,
    ]
    if event_type:
        filters.append(RiskActivityEvent.event_type == event_type)

    count_query = select(func.count(RiskActivityEvent.id)).where(*filters)
    total = await db.scalar(count_query) or 0
    query = (
        select(RiskActivityEvent)
        .where(*filters)
        .order_by(RiskActivityEvent.created_at.desc(), RiskActivityEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    rows = result.scalars().all()
    actor_ids = {e.actor_id for e in rows}
    email_map = await _batch_resolve_user_emails(db, actor_ids)

    return RiskActivityListResponse(
        items=[
            RiskActivityEventItem(
                id=e.id,
                risk_id=e.risk_id,
                event_type=e.event_type,
                summary=e.summary,
                payload=e.payload if isinstance(e.payload, dict) else None,
                actor_id=e.actor_id,
                actor_email=email_map.get(e.actor_id),
                created_at=e.created_at.isoformat() if e.created_at else None,
            )
            for e in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


def _capa_status_value(status: Any) -> Optional[str]:
    if status is None:
        return None
    return status.value if hasattr(status, "value") else str(status)


def _capa_priority_value(priority: Any) -> Optional[str]:
    if priority is None:
        return None
    return priority.value if hasattr(priority, "value") else str(priority)


@router.get("/{risk_id}/actions", response_model=RiskActionListResponse)
async def list_risk_actions(
    current_user: CurrentUser,
    risk_id: int,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> RiskActionListResponse:
    """List CAPA actions linked via source_type=risk & source_id (SSOT join)."""
    await _get_tenant_risk_or_404(db, current_user.tenant_id, risk_id)
    service = RiskService(db)
    rows, total = await service.list_capa_actions_for_risk(
        tenant_id=current_user.tenant_id,
        risk_id=risk_id,
        page=page,
        page_size=page_size,
    )
    return RiskActionListResponse(
        items=[
            RiskActionItem(
                id=a.id,
                reference_number=a.reference_number,
                title=a.title,
                description=a.description,
                status=_capa_status_value(a.status),
                priority=_capa_priority_value(a.priority),
                source_type="risk",
                source_id=risk_id,
                due_date=a.due_date.isoformat() if a.due_date else None,
                assigned_to_id=a.assigned_to_id,
                created_at=a.created_at.isoformat() if a.created_at else None,
                href=f"/actions?sourceType=risk&sourceId={risk_id}",
            )
            for a in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


@router.post(
    "/{risk_id}/actions",
    response_model=RiskActionItem,
    status_code=status.HTTP_201_CREATED,
)
async def create_risk_action(
    current_user: Annotated[User, Depends(require_permission("risk:update"))],
    risk_id: int,
    body: RiskActionCreate,
    db: DbSession,
) -> RiskActionItem:
    """Create a CAPA bound to this risk and emit a risk activity event."""
    risk = await _get_tenant_risk_or_404(db, current_user.tenant_id, risk_id)
    parsed_due: Optional[datetime] = None
    if body.due_date:
        try:
            parsed_due = datetime.fromisoformat(body.due_date.replace("Z", "+00:00"))
            if parsed_due.tzinfo is not None:
                parsed_due = parsed_due.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError as exc:
            raise BadRequestError("Invalid due_date; use YYYY-MM-DD") from exc

    service = RiskService(db)
    action = await service.create_capa_action_for_risk(
        risk,
        title=body.title,
        description=body.description or "",
        created_by_id=current_user.id,
        priority=body.priority or "medium",
        due_date=parsed_due,
        assigned_to_id=body.assigned_to_id,
    )
    if current_user.tenant_id is not None:
        await invalidate_tenant_cache(current_user.tenant_id, "risk-register")
        await invalidate_tenant_cache(current_user.tenant_id, "capa")
    return RiskActionItem(
        id=action.id,
        reference_number=action.reference_number,
        title=action.title,
        description=action.description,
        status=_capa_status_value(action.status),
        priority=_capa_priority_value(action.priority),
        source_type="risk",
        source_id=risk_id,
        due_date=action.due_date.isoformat() if action.due_date else None,
        assigned_to_id=action.assigned_to_id,
        created_at=action.created_at.isoformat() if action.created_at else None,
        href=f"/actions?sourceType=risk&sourceId={risk_id}",
    )


@router.get("/{risk_id}/upstream", response_model=RiskUpstreamResponse)
async def list_risk_upstream(
    current_user: CurrentUser,
    risk_id: int,
    db: DbSession,
) -> RiskUpstreamResponse:
    """Upstream 360: cases + audit findings linked to this risk (reverse joins)."""
    await _get_tenant_risk_or_404(db, current_user.tenant_id, risk_id)
    service = RiskService(db)
    raw = await service.list_upstream_for_risk(tenant_id=current_user.tenant_id, risk_id=risk_id)
    items = [RiskUpstreamItem(**row) for row in raw]
    return RiskUpstreamResponse(items=items, total=len(items))


@router.put("/{risk_id}/owner", response_model=RiskOwnerResponse)
async def update_risk_owner(
    current_user: Annotated[User, Depends(require_permission("risk:update"))],
    risk_id: int,
    body: RiskOwnerUpdate,
    db: DbSession,
) -> RiskOwnerResponse:
    """Set risk_owner_id + denormalized name; emit owner_changed activity."""
    risk = await _get_tenant_risk_or_404(db, current_user.tenant_id, risk_id)
    service = RiskService(db)
    try:
        risk = await service.update_risk_owner(
            risk,
            risk_owner_id=body.risk_owner_id,
            risk_owner_name=body.risk_owner_name,
            actor_id=current_user.id,
        )
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc
    if current_user.tenant_id is not None:
        await invalidate_tenant_cache(current_user.tenant_id, "risk-register")
    return RiskOwnerResponse(
        id=risk.id,
        risk_owner_id=risk.risk_owner_id,
        risk_owner_name=risk.risk_owner_name,
    )


@router.get("/{risk_id}", response_model=dict)
async def get_risk(
    current_user: CurrentUser,
    risk_id: int,
    db: DbSession,
) -> dict[str, Any]:
    """Get detailed risk information"""
    result = await db.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.id == risk_id,
            EnterpriseRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("EnterpriseRisk not found")

    result = await db.execute(select(RiskControlMapping).where(RiskControlMapping.risk_id == risk_id))
    control_mappings = result.scalars().all()
    control_ids = [m.control_id for m in control_mappings]

    if control_ids:
        result = await db.execute(select(EnterpriseRiskControl).where(EnterpriseRiskControl.id.in_(control_ids)))
        controls = result.scalars().all()
    else:
        controls = []

    result = await db.execute(select(EnterpriseKeyRiskIndicator).where(EnterpriseKeyRiskIndicator.risk_id == risk_id))
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
        "last_review_date": (risk.last_review_date.isoformat() if risk.last_review_date else None),
        "next_review_date": (risk.next_review_date.isoformat() if risk.next_review_date else None),
        "review_notes": risk.review_notes,
        "is_escalated": risk.is_escalated,
        "escalation_reason": risk.escalation_reason,
        "linked_audits": risk.linked_audits or [],
        "linked_incidents": risk.linked_incidents or [],
        "linked_actions": risk.linked_actions or [],
        "suggestion_triage_status": risk.suggestion_triage_status,
        "identified_date": (risk.identified_date.isoformat() if risk.identified_date else None),
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
    current_user: Annotated[User, Depends(require_permission("risk:update"))],
    risk_id: int,
    risk_data: RiskUpdate,
    db: DbSession,
) -> dict[str, Any]:
    """Update risk details (not scores). Owner changes emit activity events."""
    result = await db.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.id == risk_id,
            EnterpriseRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("EnterpriseRisk not found")

    update_data = risk_data.model_dump(exclude_unset=True)
    owner_touched = "risk_owner_id" in update_data or "risk_owner_name" in update_data
    if owner_touched:
        service = RiskService(db)
        try:
            risk = await service.update_risk_owner(
                risk,
                risk_owner_id=update_data.pop("risk_owner_id", risk.risk_owner_id),
                risk_owner_name=update_data.pop("risk_owner_name", risk.risk_owner_name),
                actor_id=current_user.id,
            )
        except ValueError as exc:
            raise NotFoundError(str(exc)) from exc

    for key, value in update_data.items():
        setattr(risk, key, value)

    if update_data:
        risk.updated_at = _naive_utc_now()
        await db.commit()
        await db.refresh(risk)

    if current_user.tenant_id is not None and (owner_touched or update_data):
        await invalidate_tenant_cache(current_user.tenant_id, "risk-register")

    return {"message": "EnterpriseRisk updated successfully", "id": risk.id}


@router.post("/{risk_id}/assess", response_model=dict)
async def assess_risk(
    current_user: Annotated[User, Depends(require_permission("risk:update"))],
    risk_id: int,
    assessment: RiskAssessmentUpdate,
    db: DbSession,
) -> dict[str, Any]:
    """Update risk assessment scores (SSOT: history + scores in one transaction)."""
    result = await db.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.id == risk_id,
            EnterpriseRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("EnterpriseRisk not found")
    service = RiskService(db)
    try:
        payload = assessment.model_dump(exclude_unset=True)
        for key in ("last_review_date", "next_review_date"):
            if key in payload and payload[key] is not None:
                dt_val = payload[key]
                if isinstance(dt_val, datetime) and dt_val.tzinfo is not None:
                    payload[key] = dt_val.astimezone(timezone.utc).replace(tzinfo=None)
                elif isinstance(dt_val, datetime):
                    payload[key] = dt_val.replace(tzinfo=None)

        risk = await service.update_risk_assessment(
            risk_id,
            payload,
            assessed_by=current_user.id,
        )
        from src.domain.services.risk_service import read_score_trend_from_tags

        trend = read_score_trend_from_tags(risk.tags) or "stable"
        if current_user.tenant_id is not None:
            await invalidate_tenant_cache(current_user.tenant_id, "risk-register")
            await invalidate_tenant_cache(current_user.tenant_id, "risks")
        return {
            "message": "EnterpriseRisk assessment updated",
            "inherent_score": risk.inherent_score,
            "residual_score": risk.residual_score,
            "risk_level": RiskScoringEngine.get_risk_level(risk.residual_score),
            "is_within_appetite": risk.is_within_appetite,
            "trend": trend,
            "last_review_date": (risk.last_review_date.isoformat() if risk.last_review_date else None),
            "next_review_date": (risk.next_review_date.isoformat() if risk.next_review_date else None),
        }
    except ValueError as e:
        raise NotFoundError(str(e))


@router.delete("/{risk_id}", status_code=204)
async def delete_risk(
    current_user: Annotated[User, Depends(require_permission("risk:update"))],
    risk_id: int,
    db: DbSession,
) -> None:
    """Delete a risk (soft delete by changing status)"""
    result = await db.execute(
        select(EnterpriseRisk).where(
            EnterpriseRisk.id == risk_id,
            EnterpriseRisk.tenant_id == current_user.tenant_id,
        )
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise NotFoundError("EnterpriseRisk not found")

    risk.status = "closed"
    risk.updated_at = _naive_utc_now()
    await db.commit()
