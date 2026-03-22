"""Assessment API Routes.

REST endpoints for competency assessment runs and responses.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.assessment import (
    AssessmentResponseCreate,
    AssessmentResponseResponse,
    AssessmentResponseUpdate,
    AssessmentRunCreate,
    AssessmentRunListResponse,
    AssessmentRunResponse,
    AssessmentRunUpdate,
)
from src.api.schemas.error_codes import ErrorCode
from src.api.utils.errors import api_error
from src.api.utils.tenant import apply_tenant_filter
from src.domain.models.assessment import (
    AssessmentOutcome,
    AssessmentResponse,
    AssessmentRun,
    AssessmentStatus,
    CompetencyVerdict,
)
from src.domain.models.audit import AuditQuestion, AuditTemplate
from src.domain.models.engineer import CompetencyLifecycleState, CompetencyRecord, Engineer
from src.domain.services.capa_auto_service import CAPAAutoService
from src.domain.services.competency_scoring_service import CompetencyScoringService
from src.domain.services.governance_service import GovernanceService, NotificationService

logger = logging.getLogger(__name__)

router = APIRouter()


def _is_workforce_admin(user: CurrentUser) -> bool:
    role_names = {r.name.lower() for r in getattr(user, "roles", []) or []}
    return bool(getattr(user, "is_superuser", False) or "admin" in role_names)


async def _assessment_engineer_user_id(db: AsyncSession, engineer_id: int) -> int | None:
    return await db.scalar(select(Engineer.user_id).where(Engineer.id == engineer_id))


def _missing_assessment_question_ids(run: AssessmentRun, template: AuditTemplate) -> list[int]:
    expected_question_ids = {q.id for q in template.questions if getattr(q, "is_active", True)}
    answered_question_ids = {r.question_id for r in run.responses if getattr(r, "verdict", None) is not None}
    return sorted(expected_question_ids - answered_question_ids)


async def _assert_assessment_access(
    db: AsyncSession,
    user: CurrentUser,
    run: AssessmentRun,
    *,
    allow_engineer_read: bool = False,
) -> None:
    if _is_workforce_admin(user) or run.supervisor_id == user.id:
        return

    if allow_engineer_read:
        engineer_user_id = await _assessment_engineer_user_id(db, run.engineer_id)
        if engineer_user_id == user.id:
            return

    raise HTTPException(
        status_code=403,
        detail=api_error(
            ErrorCode.PERMISSION_DENIED,
            "You do not have permission to access this assessment run",
        ),
    )


async def _generate_assessment_reference_number(db: AsyncSession) -> str:
    """Generate next sequential reference number: ASM-YYYY-NNNN."""
    year = datetime.now(timezone.utc).year
    pattern = f"ASM-{year}-"
    stmt = (
        select(AssessmentRun.reference_number)
        .where(AssessmentRun.reference_number.like(f"{pattern}%"))
        .order_by(AssessmentRun.reference_number.desc())
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


@router.get("/", response_model=AssessmentRunListResponse)
async def list_assessment_runs(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    engineer_id: Optional[int] = None,
    status: Optional[str] = None,
    asset_type_id: Optional[int] = None,
):
    """List assessment runs with filtering and pagination."""
    query = select(AssessmentRun).options(selectinload(AssessmentRun.responses))
    query = apply_tenant_filter(query, AssessmentRun, user.tenant_id)
    if not _is_workforce_admin(user):
        engineer_id_result = await db.execute(
            apply_tenant_filter(select(Engineer.id), Engineer, user.tenant_id).where(Engineer.user_id == user.id)
        )
        engineer_ids = engineer_id_result.scalars().all()
        query = query.where(
            (AssessmentRun.supervisor_id == user.id) | (AssessmentRun.engineer_id.in_(engineer_ids or [-1]))
        )
    if engineer_id is not None:
        query = query.where(AssessmentRun.engineer_id == engineer_id)
    if status is not None:
        query = query.where(AssessmentRun.status == status)
    if asset_type_id is not None:
        query = query.where(AssessmentRun.asset_type_id == asset_type_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.scalar(count_q)) or 0
    offset = (page - 1) * page_size
    items_result = await db.execute(query.offset(offset).limit(page_size).order_by(AssessmentRun.created_at.desc()))
    items = items_result.scalars().all()
    pages = (total + page_size - 1) // page_size if total > 0 else 0

    return AssessmentRunListResponse(
        items=[AssessmentRunResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/", response_model=AssessmentRunResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment_run(
    data: AssessmentRunCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create an assessment run. Reference number is auto-generated as ASM-YYYY-NNNN."""
    supervisor_check = await GovernanceService.validate_supervisor(
        db, user.id, data.engineer_id, tenant_id=user.tenant_id
    )
    if not supervisor_check["valid"]:
        raise HTTPException(
            status_code=400, detail=api_error(ErrorCode.VALIDATION_ERROR, "Supervisor validation failed")
        )

    template_check = await GovernanceService.check_template_approval(db, data.template_id, tenant_id=user.tenant_id)
    if not template_check["approved"]:
        raise HTTPException(
            status_code=400, detail=api_error(ErrorCode.VALIDATION_ERROR, "Template approval check failed")
        )

    reference_number = await _generate_assessment_reference_number(db)
    run = AssessmentRun(
        reference_number=reference_number,
        template_id=data.template_id,
        engineer_id=data.engineer_id,
        supervisor_id=user.id,
        asset_type_id=data.asset_type_id,
        asset_id=data.asset_id,
        title=data.title,
        location=data.location,
        notes=data.notes,
        scheduled_date=data.scheduled_date,
        status=AssessmentStatus.DRAFT,
        tenant_id=user.tenant_id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return AssessmentRunResponse.model_validate(run)


@router.get("/{run_id}", response_model=AssessmentRunResponse)
async def get_assessment_run(
    run_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Get an assessment run by ID."""
    query = select(AssessmentRun).options(selectinload(AssessmentRun.responses)).where(AssessmentRun.id == run_id)
    query = apply_tenant_filter(query, AssessmentRun, user.tenant_id)
    result = await db.execute(query)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Assessment run not found"))
    await _assert_assessment_access(db, user, run, allow_engineer_read=True)
    return AssessmentRunResponse.model_validate(run)


@router.patch("/{run_id}", response_model=AssessmentRunResponse)
async def update_assessment_run(
    run_id: str,
    data: AssessmentRunUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update an assessment run."""
    query = select(AssessmentRun).where(AssessmentRun.id == run_id)
    query = apply_tenant_filter(query, AssessmentRun, user.tenant_id)
    result = await db.execute(query)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Assessment run not found"))
    await _assert_assessment_access(db, user, run)

    updates = data.model_dump(exclude_unset=True)
    if "status" in updates:
        raise HTTPException(
            status_code=400,
            detail=api_error(
                ErrorCode.INVALID_STATE_TRANSITION,
                "Assessment status can only be changed via workflow actions",
            ),
        )
    for k, v in updates.items():
        setattr(run, k, v)
    await db.commit()
    await db.refresh(run)
    return AssessmentRunResponse.model_validate(run)


@router.post("/{run_id}/start", response_model=AssessmentRunResponse)
async def start_assessment(
    run_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Start an assessment run."""
    query = select(AssessmentRun).where(AssessmentRun.id == run_id)
    query = apply_tenant_filter(query, AssessmentRun, user.tenant_id)
    result = await db.execute(query)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Assessment run not found"))
    await _assert_assessment_access(db, user, run)
    if run.status != AssessmentStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail=api_error(ErrorCode.INVALID_STATE_TRANSITION, "Assessment can only be started from draft status"),
        )
    run.status = AssessmentStatus.IN_PROGRESS
    run.started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    return AssessmentRunResponse.model_validate(run)


@router.post("/{run_id}/complete", response_model=AssessmentRunResponse)
async def complete_assessment(
    run_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Complete an assessment and run CompetencyScoringService."""
    query = select(AssessmentRun).options(selectinload(AssessmentRun.responses)).where(AssessmentRun.id == run_id)
    query = apply_tenant_filter(query, AssessmentRun, user.tenant_id)
    result = await db.execute(query)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Assessment run not found"))
    await _assert_assessment_access(db, user, run)

    if run.status not in (AssessmentStatus.DRAFT, AssessmentStatus.IN_PROGRESS):
        raise HTTPException(
            status_code=400,
            detail=api_error(
                ErrorCode.INVALID_STATE_TRANSITION,
                "Assessment cannot be completed from current status",
                details={"current_status": run.status.value},
            ),
        )

    template_result = await db.execute(
        select(AuditTemplate).options(selectinload(AuditTemplate.questions)).where(AuditTemplate.id == run.template_id)
    )
    template = template_result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Template not found"))

    score_result = CompetencyScoringService.score_assessment(run.responses, template.questions)
    missing_question_ids = _missing_assessment_question_ids(run, template)
    if missing_question_ids:
        raise HTTPException(
            status_code=400,
            detail=api_error(
                ErrorCode.VALIDATION_ERROR,
                "All active assessment questions must be answered before completion",
                details={
                    "run_id": run.id,
                    "template_id": run.template_id,
                    "missing_question_ids": missing_question_ids,
                },
            ),
        )
    if score_result.scorable_items == 0:
        raise HTTPException(
            status_code=400,
            detail=api_error(
                ErrorCode.VALIDATION_ERROR,
                "At least one competency item must be assessed before completing assessment",
                details={
                    "run_id": run.id,
                    "response_count": len(run.responses),
                    "scorable_items": score_result.scorable_items,
                },
            ),
        )
    run.status = AssessmentStatus.COMPLETED
    run.completed_at = datetime.now(timezone.utc)
    run.outcome = AssessmentOutcome(score_result.outcome)

    # engineer_id FK now references engineers.id; look up Engineer for user_id
    eng_result = await db.execute(select(Engineer).where(Engineer.id == run.engineer_id))
    engineer = eng_result.scalar_one_or_none()

    if run.asset_type_id and engineer:
        from datetime import timedelta

        expiry = datetime.now(timezone.utc) + timedelta(days=365) if score_result.outcome == "pass" else None
        competency = CompetencyRecord(
            engineer_id=run.engineer_id,
            asset_type_id=run.asset_type_id,
            template_id=run.template_id,
            source_type="assessment",
            source_run_id=run.id,
            state=(
                CompetencyLifecycleState.ACTIVE if score_result.outcome == "pass" else CompetencyLifecycleState.FAILED
            ),
            outcome=score_result.outcome,
            assessed_at=datetime.now(timezone.utc),
            assessed_by_id=run.supervisor_id,
            expires_at=expiry,
            tenant_id=run.tenant_id,
        )
        db.add(competency)

    if score_result.outcome in ("fail", "conditional"):
        failed_questions = []
        for resp in run.responses:
            verdict_val = (
                resp.verdict.value if hasattr(resp.verdict, "value") else str(resp.verdict) if resp.verdict else None
            )
            if verdict_val == "not_competent":
                q = next((q for q in template.questions if q.id == resp.question_id), None)
                q_text = q.question_text if q else "Unknown"
                q_crit = q.criticality.value if q and hasattr(q.criticality, "value") else "good_to_have"
                failed_questions.append(
                    {
                        "question_id": resp.question_id,
                        "question_text": q_text,
                        "criticality": q_crit,
                        "feedback": resp.feedback or "",
                    }
                )
        if failed_questions:
            await CAPAAutoService.create_from_assessment(
                db=db,
                assessment_run_id=run.id,
                engineer_id=run.engineer_id,
                supervisor_id=run.supervisor_id,
                outcome=score_result.outcome,
                failed_questions=failed_questions,
                tenant_id=run.tenant_id,
            )

    try:
        await NotificationService.notify_assessment_complete(
            db=db,
            assessment_run_id=run.id,
            engineer_user_id=engineer.user_id if engineer else None,
            supervisor_id=run.supervisor_id,
            outcome=score_result.outcome,
        )
    except Exception:
        logger.exception("Failed to send assessment completion notification for run %s", run.id)

    await db.commit()
    await db.refresh(run)
    return AssessmentRunResponse.model_validate(run)


@router.post(
    "/{run_id}/responses",
    response_model=AssessmentResponseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assessment_response(
    run_id: str,
    data: AssessmentResponseCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create an assessment response for a run."""
    query = select(AssessmentRun).where(AssessmentRun.id == run_id)
    query = apply_tenant_filter(query, AssessmentRun, user.tenant_id)
    result = await db.execute(query)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Assessment run not found"))
    await _assert_assessment_access(db, user, run)

    if run.status == AssessmentStatus.COMPLETED or run.status == AssessmentStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail=api_error(
                ErrorCode.INVALID_STATE_TRANSITION, "Cannot add responses to a completed or cancelled assessment"
            ),
        )

    question_id = await db.scalar(
        select(AuditQuestion.id).where(
            AuditQuestion.template_id == run.template_id,
            AuditQuestion.id == data.question_id,
            AuditQuestion.is_active.is_(True),
        )
    )
    if question_id is None:
        raise HTTPException(
            status_code=400,
            detail=api_error(
                ErrorCode.VALIDATION_ERROR,
                "Question does not belong to this assessment template",
                details={"run_id": run.id, "template_id": run.template_id, "question_id": data.question_id},
            ),
        )

    verdict_val = CompetencyVerdict(data.verdict) if data.verdict else None
    existing_query = select(AssessmentResponse).where(
        AssessmentResponse.run_id == run_id,
        AssessmentResponse.question_id == data.question_id,
    )
    existing_result = await db.execute(existing_query)
    response = existing_result.scalar_one_or_none()

    if response is None:
        response = AssessmentResponse(
            run_id=run_id,
            question_id=data.question_id,
            verdict=verdict_val,
            feedback=data.feedback,
            supervisor_notes=data.supervisor_notes,
        )
        db.add(response)
    else:
        response.verdict = verdict_val
        response.feedback = data.feedback
        response.supervisor_notes = data.supervisor_notes

    await db.commit()
    await db.refresh(response)
    return AssessmentResponseResponse.model_validate(response)


@router.patch("/responses/{response_id}", response_model=AssessmentResponseResponse)
async def update_assessment_response(
    response_id: str,
    data: AssessmentResponseUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update an assessment response."""
    query = (
        select(AssessmentResponse)
        .options(selectinload(AssessmentResponse.run))
        .where(AssessmentResponse.id == response_id)
    )
    result = await db.execute(query)
    response = result.scalar_one_or_none()
    if response is None:
        raise HTTPException(
            status_code=404, detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Assessment response not found")
        )

    query_run = select(AssessmentRun).where(AssessmentRun.id == response.run_id)
    query_run = apply_tenant_filter(query_run, AssessmentRun, user.tenant_id)
    run_result = await db.execute(query_run)
    run = run_result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Assessment run not found"))
    await _assert_assessment_access(db, user, run)
    if run.status in (AssessmentStatus.COMPLETED, AssessmentStatus.CANCELLED):
        raise HTTPException(
            status_code=400,
            detail=api_error(
                ErrorCode.INVALID_STATE_TRANSITION,
                "Cannot update responses for a completed or cancelled assessment",
            ),
        )

    updates = data.model_dump(exclude_unset=True)
    if "verdict" in updates and updates["verdict"] is not None:
        updates["verdict"] = CompetencyVerdict(updates["verdict"])
    for k, v in updates.items():
        setattr(response, k, v)
    await db.commit()
    await db.refresh(response)
    return AssessmentResponseResponse.model_validate(response)
