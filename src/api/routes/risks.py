"""Risk Register API routes."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.risk import (
    RiskAssessmentCreate,
    RiskAssessmentResponse,
    OperationalRiskControlCreate,
    OperationalRiskControlResponse,
    OperationalRiskControlUpdate,
    RiskCreate,
    RiskDetailResponse,
    RiskListResponse,
    RiskMatrixCell,
    RiskMatrixResponse,
    RiskResponse,
    RiskStatistics,
    RiskUpdate,
)
from src.domain.models.risk import OperationalRiskControl, Risk, RiskAssessment, RiskStatus
from src.services.reference_number import ReferenceNumberService

router = APIRouter()


# ============== Risk Matrix Configuration ==============

RISK_MATRIX = {
    1: {
        1: ("very_low", "#22c55e"),
        2: ("low", "#84cc16"),
        3: ("low", "#84cc16"),
        4: ("medium", "#eab308"),
        5: ("medium", "#eab308"),
    },
    2: {
        1: ("low", "#84cc16"),
        2: ("low", "#84cc16"),
        3: ("medium", "#eab308"),
        4: ("medium", "#eab308"),
        5: ("high", "#f97316"),
    },
    3: {
        1: ("low", "#84cc16"),
        2: ("medium", "#eab308"),
        3: ("medium", "#eab308"),
        4: ("high", "#f97316"),
        5: ("high", "#f97316"),
    },
    4: {
        1: ("medium", "#eab308"),
        2: ("medium", "#eab308"),
        3: ("high", "#f97316"),
        4: ("high", "#f97316"),
        5: ("critical", "#ef4444"),
    },
    5: {
        1: ("medium", "#eab308"),
        2: ("high", "#f97316"),
        3: ("high", "#f97316"),
        4: ("critical", "#ef4444"),
        5: ("critical", "#ef4444"),
    },
}


def calculate_risk_level(likelihood: int, impact: int) -> tuple[int, str, str]:
    """Calculate risk score and level from likelihood and impact."""
    score = likelihood * impact
    level, color = RISK_MATRIX.get(likelihood, {}).get(impact, ("medium", "#eab308"))
    return score, level, color


# ============== Risk Endpoints ==============


@router.get("/", response_model=RiskListResponse)
async def list_risks(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    risk_level: Optional[str] = None,
    owner_id: Optional[int] = None,
) -> RiskListResponse:
    """List all risks with pagination and filtering."""
    query = select(Risk).where(Risk.is_active == True)

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

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Risk.risk_score.desc(), Risk.created_at.desc())

    result = await db.execute(query)
    risks = result.scalars().all()

    return RiskListResponse(
        items=[RiskResponse.model_validate(r) for r in risks],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


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

    return RiskResponse.model_validate(risk)


@router.get("/statistics", response_model=RiskStatistics)
async def get_risk_statistics(
    db: DbSession,
    current_user: CurrentUser,
) -> RiskStatistics:
    """Get risk register statistics."""
    # Total and active risks
    total_result = await db.execute(select(func.count()).select_from(Risk))
    total_risks = total_result.scalar() or 0

    active_result = await db.execute(select(func.count()).select_from(Risk).where(Risk.is_active == True))
    active_risks = active_result.scalar() or 0

    # Risks by category
    category_result = await db.execute(
        select(Risk.category, func.count()).where(Risk.is_active == True).group_by(Risk.category)
    )
    risks_by_category = {row[0] or "uncategorized": row[1] for row in category_result.all()}

    # Risks by level
    level_result = await db.execute(
        select(Risk.risk_level, func.count()).where(Risk.is_active == True).group_by(Risk.risk_level)
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
            )
        )
    )
    overdue_treatments = overdue_result.scalar() or 0

    # Average risk score
    avg_result = await db.execute(select(func.avg(Risk.risk_score)).where(Risk.is_active == True))
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
        .where(Risk.is_active == True)
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
        .where(Risk.id == risk_id)
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
    result = await db.execute(select(Risk).where(Risk.id == risk_id))
    risk = result.scalar_one_or_none()

    if not risk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk not found",
        )

    update_data = risk_data.model_dump(exclude_unset=True)

    # Handle JSON array fields
    json_fields = ["clause_ids", "control_ids", "linked_audit_ids", "linked_incident_ids", "linked_policy_ids"]
    for field in json_fields:
        if field in update_data:
            setattr(risk, f"{field}_json", update_data.pop(field))

    # Recalculate risk score if likelihood or impact changed
    likelihood = update_data.get("likelihood", risk.likelihood)
    impact = update_data.get("impact", risk.impact)
    if "likelihood" in update_data or "impact" in update_data:
        score, level, _ = calculate_risk_level(likelihood, impact)
        risk.risk_score = score
        risk.risk_level = level

    for field, value in update_data.items():
        setattr(risk, field, value)

    await db.commit()
    await db.refresh(risk)

    return RiskResponse.model_validate(risk)


@router.delete("/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_risk(
    risk_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Soft delete a risk (superuser only)."""
    result = await db.execute(select(Risk).where(Risk.id == risk_id))
    risk = result.scalar_one_or_none()

    if not risk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk not found",
        )

    risk.is_active = False
    risk.status = RiskStatus.CLOSED
    await db.commit()


# ============== Risk Control Endpoints ==============


@router.post("/{risk_id}/controls", response_model=OperationalRiskControlResponse, status_code=status.HTTP_201_CREATED)
async def create_control(
    risk_id: int,
    control_data: OperationalRiskControlCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> OperationalRiskControlResponse:
    """Create a new control for a risk."""
    # Verify risk exists
    result = await db.execute(select(Risk).where(Risk.id == risk_id))
    risk = result.scalar_one_or_none()

    if not risk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk not found",
        )

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

    return OperationalRiskControlResponse.model_validate(control)


@router.get("/{risk_id}/controls", response_model=list[OperationalRiskControlResponse])
async def list_controls(
    risk_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[OperationalRiskControlResponse]:
    """List all controls for a risk."""
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

    return [OperationalRiskControlResponse.model_validate(c) for c in controls]


@router.patch("/controls/{control_id}", response_model=OperationalRiskControlResponse)
async def update_control(
    control_id: int,
    control_data: OperationalRiskControlUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> OperationalRiskControlResponse:
    """Update a risk control."""
    result = await db.execute(select(OperationalRiskControl).where(OperationalRiskControl.id == control_id))
    control = result.scalar_one_or_none()

    if not control:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Control not found",
        )

    update_data = control_data.model_dump(exclude_unset=True)

    # Handle JSON array fields
    if "clause_ids" in update_data:
        control.clause_ids_json = update_data.pop("clause_ids")
    if "control_ids" in update_data:
        control.control_ids_json = update_data.pop("control_ids")

    for field, value in update_data.items():
        setattr(control, field, value)

    await db.commit()
    await db.refresh(control)

    return OperationalRiskControlResponse.model_validate(control)


@router.delete("/controls/{control_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_control(
    control_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Soft delete a risk control."""
    result = await db.execute(select(OperationalRiskControl).where(OperationalRiskControl.id == control_id))
    control = result.scalar_one_or_none()

    if not control:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Control not found",
        )

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
    # Verify risk exists
    result = await db.execute(select(Risk).where(Risk.id == risk_id))
    risk = result.scalar_one_or_none()

    if not risk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk not found",
        )

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
    result = await db.execute(
        select(RiskAssessment).where(RiskAssessment.risk_id == risk_id).order_by(RiskAssessment.assessment_date.desc())
    )
    assessments = result.scalars().all()

    return [RiskAssessmentResponse.model_validate(a) for a in assessments]
