"""Induction API Routes.

REST endpoints for induction/training runs and responses.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

logger = logging.getLogger(__name__)
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.induction import (
    InductionResponseCreate,
    InductionResponseResponse,
    InductionResponseUpdate,
    InductionRunCreate,
    InductionRunListResponse,
    InductionRunResponse,
    InductionRunUpdate,
)
from src.api.utils.tenant import apply_tenant_filter
from src.domain.models.engineer import CompetencyLifecycleState, CompetencyRecord, Engineer
from src.domain.models.induction import (
    InductionResponse,
    InductionRun,
    InductionStage,
    InductionStatus,
    UnderstandingVerdict,
)
from src.domain.services.capa_auto_service import CAPAAutoService
from src.domain.services.competency_scoring_service import CompetencyScoringService
from src.domain.services.governance_service import GovernanceService, NotificationService

router = APIRouter()


async def _generate_induction_reference_number(db: DbSession) -> str:
    """Generate next sequential reference number: IND-YYYY-NNNN."""
    year = datetime.now(timezone.utc).year
    pattern = f"IND-{year}-"
    stmt = (
        select(InductionRun.reference_number)
        .where(InductionRun.reference_number.like(f"{pattern}%"))
        .order_by(InductionRun.reference_number.desc())
        .limit(1)
        .with_for_update()
    )
    result = await db.execute(stmt)
    last_ref = result.scalar_one_or_none()
    if last_ref is None:
        seq = 1
    else:
        try:
            seq = int(last_ref.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{pattern}{seq:04d}"


@router.get("/", response_model=InductionRunListResponse)
async def list_induction_runs(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    engineer_id: Optional[int] = None,
    status: Optional[str] = None,
    asset_type_id: Optional[int] = None,
):
    """List induction runs with filtering and pagination."""
    query = select(InductionRun).options(selectinload(InductionRun.responses))
    query = apply_tenant_filter(query, InductionRun, user.tenant_id)
    if engineer_id is not None:
        query = query.where(InductionRun.engineer_id == engineer_id)
    if status is not None:
        query = query.where(InductionRun.status == status)
    if asset_type_id is not None:
        query = query.where(InductionRun.asset_type_id == asset_type_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.scalar(count_q)) or 0
    offset = (page - 1) * page_size
    items_result = await db.execute(query.offset(offset).limit(page_size).order_by(InductionRun.created_at.desc()))
    items = items_result.scalars().all()
    pages = (total + page_size - 1) // page_size if total > 0 else 0

    return InductionRunListResponse(
        items=[InductionRunResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/", response_model=InductionRunResponse, status_code=status.HTTP_201_CREATED)
async def create_induction_run(
    data: InductionRunCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create an induction run. Reference number is auto-generated as IND-YYYY-NNNN."""
    supervisor_check = await GovernanceService.validate_supervisor(
        db, user.id, data.engineer_id, tenant_id=user.tenant_id
    )
    if not supervisor_check["valid"]:
        raise HTTPException(status_code=400, detail=supervisor_check["reason"])

    template_check = await GovernanceService.check_template_approval(db, data.template_id, tenant_id=user.tenant_id)
    if not template_check["approved"]:
        raise HTTPException(status_code=400, detail=template_check["reason"])

    reference_number = await _generate_induction_reference_number(db)
    stage = InductionStage(data.stage) if data.stage else InductionStage.STAGE_1_ONSITE
    run = InductionRun(
        reference_number=reference_number,
        template_id=data.template_id,
        engineer_id=data.engineer_id,
        supervisor_id=user.id,
        asset_type_id=data.asset_type_id,
        title=data.title,
        location=data.location,
        notes=data.notes,
        stage=stage,
        scheduled_date=data.scheduled_date,
        status=InductionStatus.DRAFT,
        tenant_id=user.tenant_id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return InductionRunResponse.model_validate(run)


@router.get("/{run_id}", response_model=InductionRunResponse)
async def get_induction_run(
    run_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Get an induction run by ID."""
    query = select(InductionRun).options(selectinload(InductionRun.responses)).where(InductionRun.id == run_id)
    query = apply_tenant_filter(query, InductionRun, user.tenant_id)
    result = await db.execute(query)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Induction run not found")
    return InductionRunResponse.model_validate(run)


@router.patch("/{run_id}", response_model=InductionRunResponse)
async def update_induction_run(
    run_id: str,
    data: InductionRunUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update an induction run."""
    query = select(InductionRun).where(InductionRun.id == run_id)
    query = apply_tenant_filter(query, InductionRun, user.tenant_id)
    result = await db.execute(query)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Induction run not found")

    updates = data.model_dump(exclude_unset=True)
    if "stage" in updates and updates["stage"] is not None:
        updates["stage"] = InductionStage(updates["stage"])
    if "status" in updates and updates["status"] is not None:
        updates["status"] = InductionStatus(updates["status"])
    for k, v in updates.items():
        setattr(run, k, v)
    await db.commit()
    await db.refresh(run)
    return InductionRunResponse.model_validate(run)


@router.post("/{run_id}/start", response_model=InductionRunResponse)
async def start_induction(
    run_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Start an induction run."""
    query = select(InductionRun).where(InductionRun.id == run_id)
    query = apply_tenant_filter(query, InductionRun, user.tenant_id)
    result = await db.execute(query)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Induction run not found")
    if run.status != InductionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Induction can only be started from draft status")
    run.status = InductionStatus.IN_PROGRESS
    run.started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    return InductionRunResponse.model_validate(run)


@router.post("/{run_id}/complete", response_model=InductionRunResponse)
async def complete_induction(
    run_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Complete an induction and run CompetencyScoringService.score_induction()."""
    query = select(InductionRun).options(selectinload(InductionRun.responses)).where(InductionRun.id == run_id)
    query = apply_tenant_filter(query, InductionRun, user.tenant_id)
    result = await db.execute(query)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Induction run not found")

    if run.status not in (InductionStatus.DRAFT, InductionStatus.IN_PROGRESS):
        raise HTTPException(
            status_code=400,
            detail=f"Induction cannot be completed from status '{run.status.value}'",
        )

    score_result = CompetencyScoringService.score_induction(run.responses)
    run.status = InductionStatus.COMPLETED
    run.completed_at = datetime.now(timezone.utc)
    run.total_items = score_result.scorable_items
    run.competent_count = score_result.competent_count
    run.not_yet_competent_count = score_result.not_yet_competent_count

    # engineer_id FK now references engineers.id; look up Engineer for user_id
    eng_result = await db.execute(select(Engineer).where(Engineer.id == run.engineer_id))
    engineer = eng_result.scalar_one_or_none()

    if run.asset_type_id and engineer:
        from datetime import timedelta

        all_competent = score_result.not_yet_competent_count == 0
        expiry = datetime.now(timezone.utc) + timedelta(days=365) if all_competent else None
        competency = CompetencyRecord(
            engineer_id=run.engineer_id,
            asset_type_id=run.asset_type_id,
            template_id=run.template_id,
            source_type="induction",
            source_run_id=run.id,
            state=(CompetencyLifecycleState.ACTIVE if all_competent else CompetencyLifecycleState.FAILED),
            outcome="pass" if all_competent else "not_yet_competent",
            assessed_at=datetime.now(timezone.utc),
            assessed_by_id=run.supervisor_id,
            expires_at=expiry,
            tenant_id=run.tenant_id,
        )
        db.add(competency)

    if score_result.items_needing_capa:
        not_competent_items = []
        for q_id in score_result.items_needing_capa:
            resp = next((r for r in run.responses if r.question_id == q_id), None)
            not_competent_items.append(
                {
                    "question_id": q_id,
                    "question_text": "Skill item",
                    "supervisor_notes": resp.supervisor_notes if resp else "",
                }
            )
        await CAPAAutoService.create_from_induction(
            db=db,
            induction_run_id=run.id,
            engineer_id=run.engineer_id,
            supervisor_id=run.supervisor_id,
            not_competent_items=not_competent_items,
            tenant_id=run.tenant_id,
        )

    try:
        engineer_user_id = engineer.user_id if engineer else run.engineer_id
        await NotificationService.notify_induction_complete(
            db=db,
            induction_run_id=run.id,
            engineer_id=engineer_user_id,
            supervisor_id=run.supervisor_id,
            not_yet_competent_count=score_result.not_yet_competent_count,
        )
    except Exception:
        logger.exception("Failed to send induction completion notification for run %s", run.id)

    await db.commit()
    await db.refresh(run)
    return InductionRunResponse.model_validate(run)


@router.post(
    "/{run_id}/responses",
    response_model=InductionResponseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_induction_response(
    run_id: str,
    data: InductionResponseCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create an induction response for a run."""
    query = select(InductionRun).where(InductionRun.id == run_id)
    query = apply_tenant_filter(query, InductionRun, user.tenant_id)
    result = await db.execute(query)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Induction run not found")

    if run.status == InductionStatus.COMPLETED or run.status == InductionStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail="Cannot add responses to a completed or cancelled induction",
        )

    understanding_val = UnderstandingVerdict(data.understanding) if data.understanding else None
    response = InductionResponse(
        run_id=run_id,
        question_id=data.question_id,
        shown_explained=data.shown_explained,
        understanding=understanding_val,
        supervisor_notes=data.supervisor_notes,
    )
    db.add(response)
    await db.commit()
    await db.refresh(response)
    return InductionResponseResponse.model_validate(response)


@router.patch("/responses/{response_id}", response_model=InductionResponseResponse)
async def update_induction_response(
    response_id: str,
    data: InductionResponseUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update an induction response."""
    query = (
        select(InductionResponse)
        .options(selectinload(InductionResponse.run))
        .where(InductionResponse.id == response_id)
    )
    result = await db.execute(query)
    response = result.scalar_one_or_none()
    if response is None:
        raise HTTPException(status_code=404, detail="Induction response not found")

    query_run = select(InductionRun).where(InductionRun.id == response.run_id)
    query_run = apply_tenant_filter(query_run, InductionRun, user.tenant_id)
    run_result = await db.execute(query_run)
    if run_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Induction run not found")

    updates = data.model_dump(exclude_unset=True)
    if "understanding" in updates and updates["understanding"] is not None:
        updates["understanding"] = UnderstandingVerdict(updates["understanding"])
    for k, v in updates.items():
        setattr(response, k, v)
    await db.commit()
    await db.refresh(response)
    return InductionResponseResponse.model_validate(response)
