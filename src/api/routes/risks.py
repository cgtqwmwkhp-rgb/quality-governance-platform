"""Risk Register API routes."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.risk import (
    RiskAssessmentCreate,
    RiskAssessmentResponse,
    RiskControlCreate,
    RiskControlResponse,
    RiskControlUpdate,
    RiskCreate,
    RiskDetailResponse,
    RiskListResponse,
    RiskMatrixCell,
    RiskMatrixResponse,
    RiskResponse,
    RiskStatistics,
    RiskUpdate,
)
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.risk import OperationalRiskControl, Risk, RiskAssessment, RiskStatus
from src.domain.services.reference_number import ReferenceNumberService
from src.domain.services.risk_scoring import calculate_risk_level
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter()


# ============== Risk Endpoints ==============


@router.get("/", response_model=RiskListResponse)
async def list_risks(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    search: Optional[str] = None,
    category: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    risk_level: Optional[str] = None,
    owner_id: Optional[int] = None,
) -> RiskListResponse:
    """List all risks with pagination and filtering."""
    query = select(Risk).where(Risk.is_active == True, Risk.tenant_id == current_user.tenant_id)

    if search:
        search_filter = f"%{search}%"
        query = query.where((Risk.title.ilike(search_filter)) | (Risk.description.ilike(search_filter)))
    if category:
        query = query.where(Risk.category == category)
    if status_filter:
        query = query.where(Risk.status == status_filter)
    if risk_level:
        query = query.where(Risk.risk_level == risk_level)
    if owner_id:
        query = query.where(Risk.owner_id == owner_id)

    query = query.order_by(Risk.risk_score.desc(), Risk.created_at.desc())

    return await paginate(db, query, params)


@router.post("/", response_model=RiskResponse, status_code=status.HTTP_201_CREATED)
async def create_risk(
    risk_data: RiskCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> RiskResponse:
    """Create a new risk."""
    # Calculate risk score and level
    score, level, _ = calculate_risk_level(risk_data.likelihood, risk_data.impact)

    risk_dict = risk_data.model_dump(
        exclude={"clause_ids", "control_ids", "linked_audit_ids", "linked_incident_ids", "linked_policy_ids"}
    )

    risk = Risk(
        **risk_dict,
        risk_score=score,
        risk_level=level,
        status=RiskStatus.IDENTIFIED,
        created_by_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )

    # Handle JSON array fields
    if risk_data.clause_ids:
        risk.clause_ids_json = risk_data.clause_ids
    if risk_data.control_ids:
        risk.control_ids_json = risk_data.control_ids
    if risk_data.linked_audit_ids:
        risk.linked_audit_ids_json = risk_data.linked_audit_ids
    if risk_data.linked_incident_ids:
        risk.linked_incident_ids_json = risk_data.linked_incident_ids
    if risk_data.linked_policy_ids:
        risk.linked_policy_ids_json = risk_data.linked_policy_ids

    # Generate reference number
    risk.reference_number = await ReferenceNumberService.generate(db, "risk", Risk)

    db.add(risk)
    await db.commit()
    await db.refresh(risk)
    await invalidate_tenant_cache(current_user.tenant_id, "risks")
    track_metric("risks.created")

    return RiskResponse.model_validate(risk)


@router.get("/statistics", response_model=RiskStatistics)
async def get_risk_statistics(
    db: DbSession,
    current_user: CurrentUser,
) -> RiskStatistics:
    """Get risk register statistics."""
    tenant_filter = Risk.tenant_id == current_user.tenant_id

    # Total and active risks
    total_result = await db.execute(select(func.count()).select_from(Risk).where(tenant_filter))
    total_risks = total_result.scalar() or 0

    active_result = await db.execute(
        select(func.count()).select_from(Risk).where(Risk.is_active == True, tenant_filter)
    )
    active_risks = active_result.scalar() or 0

    # Risks by category
    category_result = await db.execute(
        select(Risk.category, func.count()).where(Risk.is_active == True, tenant_filter).group_by(Risk.category)
    )
    risks_by_category = {row[0] or "uncategorized": row[1] for row in category_result.all()}

    # Risks by level
    level_result = await db.execute(
        select(Risk.risk_level, func.count()).where(Risk.is_active == True, tenant_filter).group_by(Risk.risk_level)
    )
    risks_by_level = {row[0] or "unknown": row[1] for row in level_result.all()}

    # Risks requiring review (next_review_date in past)
    review_result = await db.execute(
        select(func.count())
        .select_from(Risk)
        .where(
            and_(
                Risk.is_active == True,
                Risk.next_review_date <= datetime.now(timezone.utc),
                tenant_filter,
            )
        )
    )
    risks_requiring_review = review_result.scalar() or 0

    # Overdue treatments
    overdue_result = await db.execute(
        select(func.count())
        .select_from(Risk)
        .where(
            and_(
                Risk.is_active == True,
                Risk.treatment_due_date <= datetime.now(timezone.utc),
                Risk.status != RiskStatus.CLOSED,
                tenant_filter,
            )
        )
    )
    overdue_treatments = overdue_result.scalar() or 0

    # Average risk score
    avg_result = await db.execute(select(func.avg(Risk.risk_score)).where(Risk.is_active == True, tenant_filter))
    average_risk_score = float(avg_result.scalar() or 0)

    return RiskStatistics(
        total_risks=total_risks,
        active_risks=active_risks,
        risks_by_category=risks_by_category,
        risks_by_level=risks_by_level,
        risks_requiring_review=risks_requiring_review,
        overdue_treatments=overdue_treatments,
        average_risk_score=round(average_risk_score, 2),
    )


@router.get("/matrix", response_model=RiskMatrixResponse)
async def get_risk_matrix(
    db: DbSession,
    current_user: CurrentUser,
) -> RiskMatrixResponse:
    """Get the risk matrix with risk counts per cell."""
    # Get risk counts by likelihood and impact
    result = await db.execute(
        select(Risk.likelihood, Risk.impact, func.count())
        .where(Risk.is_active == True, Risk.tenant_id == current_user.tenant_id)
        .group_by(Risk.likelihood, Risk.impact)
    )
    risk_counts = {(row[0], row[1]): row[2] for row in result.all()}

    # Build matrix
    matrix = []
    risks_by_level = {"very_low": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}
    total_risks = 0

    for likelihood in range(5, 0, -1):  # 5 to 1 (top to bottom)
        row = []
        for impact in range(1, 6):  # 1 to 5 (left to right)
            score, level, color = calculate_risk_level(likelihood, impact)
            count = risk_counts.get((likelihood, impact), 0)

            row.append(
                RiskMatrixCell(
                    likelihood=likelihood,
                    impact=impact,
                    score=score,
                    level=level,
                    color=color,
                    risk_count=count,
                )
            )

            risks_by_level[level] += count
            total_risks += count
        matrix.append(row)

    return RiskMatrixResponse(
        matrix=matrix,
        total_risks=total_risks,
        risks_by_level=risks_by_level,
    )


@router.get("/{risk_id}", response_model=RiskDetailResponse)
async def get_risk(
    risk_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> RiskDetailResponse:
    """Get a specific risk with controls and assessments."""
    result = await db.execute(
        select(Risk)
        .options(
            selectinload(Risk.controls),
            selectinload(Risk.assessments),
        )
        .where(Risk.id == risk_id, Risk.tenant_id == current_user.tenant_id)
    )
    risk = result.scalar_one_or_none()

    if not risk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk not found",
        )

    response = RiskDetailResponse.model_validate(risk)
    response.control_count = len(risk.controls)

    # Count open actions (simplified - would need action linkage)
    response.open_action_count = 0

    return response


@router.patch("/{risk_id}", response_model=RiskResponse)
async def update_risk(
    risk_id: int,
    risk_data: RiskUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> RiskResponse:
    """Update a risk."""
    risk = await get_or_404(db, Risk, risk_id, "Risk not found", tenant_id=current_user.tenant_id)

    update_data = risk_data.model_dump(exclude_unset=True)

    # Handle JSON array fields (schema → model field remapping)
    _json_fields = {"clause_ids", "control_ids", "linked_audit_ids", "linked_incident_ids", "linked_policy_ids"}
    for field in _json_fields:
        if field in update_data:
            setattr(risk, f"{field}_json", update_data[field])

    # Recalculate risk score if likelihood or impact changed
    likelihood = update_data.get("likelihood", risk.likelihood)
    impact = update_data.get("impact", risk.impact)
    if "likelihood" in update_data or "impact" in update_data:
        score, level, _ = calculate_risk_level(likelihood, impact)
        risk.risk_score = score
        risk.risk_level = level

    apply_updates(risk, risk_data, exclude=_json_fields)

    await db.commit()
    await db.refresh(risk)
    await invalidate_tenant_cache(current_user.tenant_id, "risks")

    return RiskResponse.model_validate(risk)


@router.delete("/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_risk(
    risk_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Soft delete a risk (superuser only)."""
    risk = await get_or_404(db, Risk, risk_id, "Risk not found", tenant_id=current_user.tenant_id)

    risk.is_active = False
    risk.status = RiskStatus.CLOSED
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "risks")


# ============== Risk Control Endpoints ==============


@router.post("/{risk_id}/controls", response_model=RiskControlResponse, status_code=status.HTTP_201_CREATED)
async def create_control(
    risk_id: int,
    control_data: RiskControlCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> RiskControlResponse:
    """Create a new control for a risk."""
    await get_or_404(db, Risk, risk_id, "Risk not found", tenant_id=current_user.tenant_id)

    control_dict = control_data.model_dump(exclude={"clause_ids", "control_ids"})

    control = OperationalRiskControl(
        risk_id=risk_id,
        **control_dict,
    )

    # Handle JSON array fields
    if control_data.clause_ids:
        control.clause_ids_json = control_data.clause_ids
    if control_data.control_ids:
        control.control_ids_json = control_data.control_ids

    db.add(control)
    await db.commit()
    await db.refresh(control)

    return RiskControlResponse.model_validate(control)


@router.get("/{risk_id}/controls", response_model=list[RiskControlResponse])
async def list_controls(
    risk_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[RiskControlResponse]:
    """List all controls for a risk."""
    await get_or_404(db, Risk, risk_id, "Risk not found", tenant_id=current_user.tenant_id)

    result = await db.execute(
        select(OperationalRiskControl)
        .where(
            and_(
                OperationalRiskControl.risk_id == risk_id,
                OperationalRiskControl.is_active == True,
            )
        )
        .order_by(OperationalRiskControl.created_at)
    )
    controls = result.scalars().all()

    return [RiskControlResponse.model_validate(c) for c in controls]


@router.patch("/controls/{control_id}", response_model=RiskControlResponse)
async def update_control(
    control_id: int,
    control_data: RiskControlUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> RiskControlResponse:
    """Update a risk control."""
    control = await get_or_404(db, OperationalRiskControl, control_id, "Control not found")
    await get_or_404(db, Risk, control.risk_id, "Risk not found", tenant_id=current_user.tenant_id)

    update_data = control_data.model_dump(exclude_unset=True)

    # Handle JSON array fields (schema → model field remapping)
    if "clause_ids" in update_data:
        control.clause_ids_json = update_data["clause_ids"]
    if "control_ids" in update_data:
        control.control_ids_json = update_data["control_ids"]

    apply_updates(control, control_data, exclude={"clause_ids", "control_ids"})

    await db.commit()
    await db.refresh(control)

    return RiskControlResponse.model_validate(control)


@router.delete("/controls/{control_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_control(
    control_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Soft delete a risk control."""
    control = await get_or_404(db, OperationalRiskControl, control_id, "Control not found")
    await get_or_404(db, Risk, control.risk_id, "Risk not found", tenant_id=current_user.tenant_id)

    control.is_active = False
    await db.commit()


# ============== Risk Assessment Endpoints ==============


@router.post("/{risk_id}/assessments", response_model=RiskAssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    risk_id: int,
    assessment_data: RiskAssessmentCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> RiskAssessmentResponse:
    """Create a new assessment for a risk."""
    risk = await get_or_404(db, Risk, risk_id, "Risk not found", tenant_id=current_user.tenant_id)

    # Calculate scores and levels
    inherent_score, inherent_level, _ = calculate_risk_level(
        assessment_data.inherent_likelihood, assessment_data.inherent_impact
    )
    residual_score, residual_level, _ = calculate_risk_level(
        assessment_data.residual_likelihood, assessment_data.residual_impact
    )

    target_score = None
    target_level = None
    if assessment_data.target_likelihood and assessment_data.target_impact:
        target_score, target_level, _ = calculate_risk_level(
            assessment_data.target_likelihood, assessment_data.target_impact
        )

    assessment = RiskAssessment(
        risk_id=risk_id,
        **assessment_data.model_dump(),
        inherent_score=inherent_score,
        inherent_level=inherent_level,
        residual_score=residual_score,
        residual_level=residual_level,
        target_score=target_score,
        target_level=target_level,
        assessed_by_id=assessment_data.assessed_by_id or current_user.id,
    )

    db.add(assessment)

    # Update risk with latest residual values
    risk.likelihood = assessment_data.residual_likelihood
    risk.impact = assessment_data.residual_impact
    risk.risk_score = residual_score
    risk.risk_level = residual_level

    await db.commit()
    await db.refresh(assessment)

    return RiskAssessmentResponse.model_validate(assessment)


@router.get("/{risk_id}/assessments", response_model=list[RiskAssessmentResponse])
async def list_assessments(
    risk_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[RiskAssessmentResponse]:
    """List all assessments for a risk (history)."""
    await get_or_404(db, Risk, risk_id, "Risk not found", tenant_id=current_user.tenant_id)

    result = await db.execute(
        select(RiskAssessment).where(RiskAssessment.risk_id == risk_id).order_by(RiskAssessment.assessment_date.desc())
    )
    assessments = result.scalars().all()

    return [RiskAssessmentResponse.model_validate(a) for a in assessments]
