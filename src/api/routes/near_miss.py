"""Near Miss API routes."""

import logging
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.dependencies.request_context import get_request_id
from src.api.routes._runner_sheet import assert_can_delete_runner_sheet_entry
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.near_miss import NearMissCreate, NearMissListResponse, NearMissResponse, NearMissUpdate
from src.api.schemas.running_sheet import RunningSheetEntryCreate, RunningSheetEntryResponse
from src.api.utils.errors import api_error
from src.api.utils.tenant import apply_tenant_filter, require_tenant_id
from src.domain.exceptions import BadRequestError, StateTransitionError
from src.domain.models.near_miss import NearMiss, NearMissRunningSheetEntry
from src.domain.models.user import User
from src.domain.services.api_idempotency_service import (
    SCOPE_NEAR_MISS_CREATE,
    begin_idempotent_create,
    complete_idempotent_create,
)
from src.domain.services.audit_service import record_audit_event
from src.domain.services.case_risk_links import sync_case_risk_links_from_csv
from src.domain.services.near_miss_risk_links import (
    append_linked_risk_id,
    create_enterprise_risk_from_near_miss,
    near_miss_detail_href,
    resolve_enterprise_category,
    risk_register_href,
)
from src.domain.services.near_miss_service import NearMissService
from src.domain.services.reference_number import ReferenceNumberService

router = APIRouter(tags=["Near Misses"])
logger = logging.getLogger(__name__)


def _near_miss_assess_content(near_miss: NearMiss) -> str:
    parts = [
        near_miss.description,
        near_miss.potential_consequences or "",
        near_miss.preventive_action_suggested or "",
        f"Location: {near_miss.location}" if near_miss.location else "",
    ]
    return "\n\n".join(p for p in parts if p)


async def _trigger_operational_standards_assess(
    db: DbSession,
    near_miss: NearMiss,
    current_user: User,
) -> None:
    """Fire-and-forget standards assessment; never breaks near-miss save."""
    try:
        from src.domain.services.governed_knowledge_service import governed_knowledge_service

        await governed_knowledge_service.assess_operational_entity(
            db,
            entity_type="near_miss",
            entity_id=str(near_miss.id),
            content=_near_miss_assess_content(near_miss),
            tenant_id=near_miss.tenant_id,
            user=current_user,
        )
    except Exception:
        logger.warning(
            "Operational standards assess failed for near_miss %s; save continues",
            near_miss.id,
            exc_info=True,
        )


async def _get_near_miss_or_404(db, near_miss_id: int, current_user: CurrentUser) -> NearMiss:
    query = select(NearMiss).where(NearMiss.id == near_miss_id)
    if not current_user.is_superuser:
        query = query.where(NearMiss.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    near_miss = result.scalar_one_or_none()

    if not near_miss:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, f"Near Miss with ID {near_miss_id} not found"),
        )
    return near_miss


@router.post(
    "",
    response_model=NearMissResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@router.post("/", response_model=NearMissResponse, status_code=status.HTTP_201_CREATED)
async def create_near_miss(
    data: NearMissCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("near_miss:create"))],
    request_id: str = Depends(get_request_id),
    idempotency_key: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None,
) -> NearMiss:
    """
    Report a new near miss.

    Near misses are events that could have resulted in injury, damage, or loss
    but didn't. Tracking these helps prevent future incidents.

    Optional ``Idempotency-Key`` header (PX-001): retries return the same record.
    """
    claim = await begin_idempotent_create(
        db,
        tenant_id=current_user.tenant_id,
        scope=SCOPE_NEAR_MISS_CREATE,
        idempotency_key=idempotency_key,
        payload=data,
    )
    if claim is not None and claim.is_replay and claim.entity_id is not None:
        return await _get_near_miss_or_404(db, claim.entity_id, current_user)

    reference_number = await ReferenceNumberService.generate(db, "near_miss", NearMiss)

    near_miss = NearMiss(
        **data.model_dump(),
        reference_number=reference_number,
        status="REPORTED",
        priority="MEDIUM",
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )

    db.add(near_miss)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="near_miss.created",
        entity_type="near_miss",
        entity_id=str(near_miss.id),
        action="create",
        description=f"Near Miss {near_miss.reference_number} reported",
        payload=data.model_dump(mode="json"),
        user_id=current_user.id,
        request_id=request_id,
    )

    await complete_idempotent_create(
        db,
        record_id=claim.record_id if claim else None,
        entity_type="near_miss",
        entity_id=near_miss.id,
    )

    await db.commit()
    await db.refresh(near_miss)
    await _trigger_operational_standards_assess(db, near_miss, current_user)
    return near_miss


@router.get("", response_model=NearMissListResponse, include_in_schema=False)
@router.get("/", response_model=NearMissListResponse)
async def list_near_misses(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("near_miss:read"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    contract: Optional[str] = Query(None),
    reporter_email: Optional[str] = Query(None, description="Filter by reporter email"),
    asset_id: Optional[int] = Query(None, description="Filter by linked Asset registry id"),
    ids: Optional[str] = Query(
        None,
        description="Comma-separated near miss ids (Safety Insights theme deep-link)",
    ),
) -> NearMissListResponse:
    """
    List near misses with pagination and filtering.

    Ordered by event_date DESC, id ASC for deterministic results.
    """
    import math

    id_list: list[int] | None = None
    # Guard: unit tests may invoke the handler with FastAPI Query defaults unbound.
    if isinstance(ids, str) and ids.strip():
        try:
            id_list = [int(part.strip()) for part in ids.split(",") if part.strip()]
        except ValueError as exc:
            raise BadRequestError("ids must be comma-separated integers") from exc
        if not id_list:
            id_list = None

    query = select(NearMiss)

    if not current_user.is_superuser:
        tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
        query = apply_tenant_filter(query, NearMiss, tenant_id)

    # Apply filters — non-admin users can only filter by their own email
    if reporter_email:
        if not current_user.is_superuser and reporter_email != current_user.email:
            raise HTTPException(
                status_code=403,
                detail=api_error(ErrorCode.PERMISSION_DENIED, "You can only filter near misses by your own email"),
            )
        query = query.where(NearMiss.reporter_email == reporter_email)
    if status_filter:
        query = query.where(NearMiss.status == status_filter)
    if priority:
        query = query.where(NearMiss.priority == priority)
    if contract:
        query = query.where(NearMiss.contract == contract)
    if asset_id is not None:
        query = query.where(NearMiss.asset_id == asset_id)
    if id_list:
        query = query.where(NearMiss.id.in_(id_list))

    # Count total
    count_query = select(sa_func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Deterministic ordering
    query = query.order_by(NearMiss.event_date.desc(), NearMiss.id.asc())

    # Pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return NearMissListResponse(
        items=[NearMissResponse.model_validate(nm) for nm in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/{near_miss_id}", response_model=NearMissResponse)
async def get_near_miss(
    near_miss_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("near_miss:read"))],
) -> NearMiss:
    """Get a near miss by ID."""
    return await _get_near_miss_or_404(db, near_miss_id, current_user)


@router.patch("/{near_miss_id}", response_model=NearMissResponse)
async def update_near_miss(
    near_miss_id: int,
    data: NearMissUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("near_miss:update"))],
    request_id: str = Depends(get_request_id),
) -> NearMiss:
    """Update a near miss."""
    service = NearMissService(db)
    try:
        near_miss = await service.update_near_miss(
            near_miss_id=near_miss_id,
            data=data,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Near miss not found"))
    except StateTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await db.commit()
    await db.refresh(near_miss)
    await _trigger_operational_standards_assess(db, near_miss, current_user)
    return near_miss


@router.delete("/{near_miss_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_near_miss(
    near_miss_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("near_miss:update"))],
    request_id: str = Depends(get_request_id),
) -> None:
    """Delete a near miss."""
    near_miss = await _get_near_miss_or_404(db, near_miss_id, current_user)

    await record_audit_event(
        db=db,
        event_type="near_miss.deleted",
        entity_type="near_miss",
        entity_id=str(near_miss.id),
        action="delete",
        description=f"Near Miss {near_miss.reference_number} deleted",
        payload={"reference_number": near_miss.reference_number},
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.delete(near_miss)
    await db.commit()


@router.get("/{near_miss_id}/investigations", response_model=dict)
async def list_near_miss_investigations(
    near_miss_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("near_miss:read"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """List investigations for a near miss."""
    from math import ceil

    from src.api.schemas.investigation import InvestigationRunResponse
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun

    near_miss = await _get_near_miss_or_404(db, near_miss_id, current_user)

    # Get investigations
    count_query = (
        select(sa_func.count())
        .select_from(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.NEAR_MISS,
            InvestigationRun.assigned_entity_id == near_miss_id,
        )
    )
    total = (await db.execute(count_query)).scalar() or 0

    query = (
        select(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.NEAR_MISS,
            InvestigationRun.assigned_entity_id == near_miss_id,
        )
        .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    investigations = (await db.execute(query)).scalars().all()

    return {
        "items": [InvestigationRunResponse.model_validate(inv) for inv in investigations],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": ceil(total / page_size) if total > 0 else 1,
    }


@router.get("/{near_miss_id}/running-sheet", response_model=list[RunningSheetEntryResponse])
async def list_near_miss_running_sheet_entries(
    near_miss_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("near_miss:read"))],
):
    """List near-miss runner-sheet entries, newest first."""
    near_miss = await _get_near_miss_or_404(db, near_miss_id, current_user)

    query = select(NearMissRunningSheetEntry).where(NearMissRunningSheetEntry.near_miss_id == near_miss_id)
    if near_miss.tenant_id is None:
        query = query.where(NearMissRunningSheetEntry.tenant_id.is_(None))
    else:
        query = query.where(NearMissRunningSheetEntry.tenant_id == near_miss.tenant_id)

    result = await db.execute(
        query.order_by(NearMissRunningSheetEntry.created_at.desc(), NearMissRunningSheetEntry.id.asc())
    )
    return result.scalars().all()


@router.post(
    "/{near_miss_id}/running-sheet",
    response_model=RunningSheetEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_near_miss_running_sheet_entry(
    near_miss_id: int,
    payload: RunningSheetEntryCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Add a timestamped entry to the near-miss runner sheet."""
    near_miss = await _get_near_miss_or_404(db, near_miss_id, current_user)

    entry = NearMissRunningSheetEntry(
        tenant_id=near_miss.tenant_id,
        near_miss_id=near_miss.id,
        content=payload.content,
        entry_type=payload.entry_type.value,
        author_id=current_user.id,
        author_email=current_user.email,
    )
    db.add(entry)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="near_miss.runner_sheet_entry.created",
        entity_type="near_miss",
        entity_id=str(near_miss.id),
        action="create",
        description=f"Runner-sheet entry added to near miss {near_miss.reference_number}",
        payload={"entry_id": entry.id, "entry_type": entry.entry_type},
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{near_miss_id}/running-sheet/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_near_miss_running_sheet_entry(
    near_miss_id: int,
    entry_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> None:
    """Delete a near-miss runner-sheet entry."""
    near_miss = await _get_near_miss_or_404(db, near_miss_id, current_user)

    result = await db.execute(
        select(NearMissRunningSheetEntry).where(
            NearMissRunningSheetEntry.id == entry_id,
            NearMissRunningSheetEntry.near_miss_id == near_miss_id,
            NearMissRunningSheetEntry.tenant_id == near_miss.tenant_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Runner-sheet entry not found"),
        )

    assert_can_delete_runner_sheet_entry(current_user, entry.author_id, "near_miss")

    await record_audit_event(
        db=db,
        event_type="near_miss.runner_sheet_entry.deleted",
        entity_type="near_miss",
        entity_id=str(near_miss.id),
        action="delete",
        description=f"Runner-sheet entry deleted from near miss {near_miss.reference_number}",
        payload={"entry_id": entry.id, "entry_type": entry.entry_type},
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.delete(entry)
    await db.commit()


class RaiseRiskFromNearMissRequest(BaseModel):
    """Optional overrides when raising a risk from a near miss."""

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = Field(None, min_length=1)
    likelihood: int = Field(3, ge=1, le=5)
    impact: int = Field(3, ge=1, le=5)
    category: Literal[
        "strategic",
        "operational",
        "financial",
        "compliance",
        "reputational",
        "safety",
        "environmental",
        "information_security",
    ] = "safety"
    # Accept legacy CUJ values; mapped to enterprise treat/tolerate/transfer/terminate.
    treatment_strategy: Literal[
        "accept",
        "mitigate",
        "transfer",
        "avoid",
        "exploit",
        "treat",
        "tolerate",
        "terminate",
    ] = "mitigate"


class RaisedEnterpriseRiskSummary(BaseModel):
    """Slim risk payload for FE toast/navigation (enterprise register)."""

    id: int
    reference_number: str
    title: str
    risk_source: Optional[str] = None


class RaiseRiskFromNearMissResponse(BaseModel):
    risk: RaisedEnterpriseRiskSummary
    near_miss_id: int
    linked_risk_ids: str
    near_miss_href: str
    risk_register_href: str


@router.post(
    "/{near_miss_id}/raise-risk",
    response_model=RaiseRiskFromNearMissResponse,
    status_code=status.HTTP_201_CREATED,
)
async def raise_risk_from_near_miss(
    near_miss_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("risk:create"))],
    request_id: str = Depends(get_request_id),
    body: Optional[RaiseRiskFromNearMissRequest] = None,
):
    """Create an Enterprise Risk Register entry linked to this near miss."""
    if body is None:
        body = RaiseRiskFromNearMissRequest.model_validate({})
    near_miss = await _get_near_miss_or_404(db, near_miss_id, current_user)

    if (
        not current_user.is_superuser
        and current_user.tenant_id is not None
        and near_miss.tenant_id != current_user.tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, f"Near Miss with ID {near_miss_id} not found"),
        )

    severity_impact = {
        "low": 2,
        "medium": 3,
        "high": 4,
        "critical": 5,
    }
    impact = body.impact
    if body.impact == 3 and near_miss.potential_severity:
        impact = severity_impact.get(str(near_miss.potential_severity).lower(), 3)

    category = resolve_enterprise_category(body.category, near_miss.risk_category)
    title = body.title or f"Risk from near miss {near_miss.reference_number}"
    description = body.description or (
        f"Raised from near miss {near_miss.reference_number}.\n\n"
        f"{near_miss.description}"
        + (
            f"\n\nPotential consequences: {near_miss.potential_consequences}"
            if near_miss.potential_consequences
            else ""
        )
    )

    try:
        risk = await create_enterprise_risk_from_near_miss(
            db,
            near_miss=near_miss,
            actor_user_id=current_user.id,
            title=title,
            description=description,
            likelihood=body.likelihood,
            impact=impact,
            category=category,
            treatment_strategy=body.treatment_strategy,
        )
        near_miss.linked_risk_ids = append_linked_risk_id(near_miss.linked_risk_ids, risk.id)
        if near_miss.tenant_id is not None:
            await sync_case_risk_links_from_csv(
                db,
                tenant_id=near_miss.tenant_id,
                case_type="near_miss",
                case_id=near_miss.id,
                linked_risk_ids_raw=near_miss.linked_risk_ids,
            )

        await record_audit_event(
            db=db,
            event_type="near_miss.risk_raised",
            entity_type="near_miss",
            entity_id=str(near_miss.id),
            action="create",
            description=f"Risk {risk.reference} raised from near miss {near_miss.reference_number}",
            payload={"risk_id": risk.id, "risk_reference": risk.reference},
            user_id=current_user.id,
            request_id=request_id,
            tenant_id=near_miss.tenant_id,
        )

        await db.commit()
        await db.refresh(risk)
    except IntegrityError as exc:
        await db.rollback()
        logger.exception("raise-risk IntegrityError for near_miss_id=%s", near_miss_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=api_error(
                ErrorCode.DATABASE_ERROR,
                "Could not raise risk due to a data conflict. Check assignee and try again.",
            ),
        ) from exc
    except Exception as exc:
        await db.rollback()
        logger.exception("raise-risk failed for near_miss_id=%s", near_miss_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=api_error(ErrorCode.INTERNAL_ERROR, "Could not raise risk from near miss."),
        ) from exc

    return RaiseRiskFromNearMissResponse(
        risk=RaisedEnterpriseRiskSummary(
            id=risk.id,
            reference_number=risk.reference,
            title=risk.title,
            risk_source=risk.context,
        ),
        near_miss_id=near_miss.id,
        linked_risk_ids=near_miss.linked_risk_ids or str(risk.id),
        near_miss_href=near_miss_detail_href(near_miss.id),
        risk_register_href=risk_register_href(risk.id, near_miss_ref=near_miss.reference_number),
    )
