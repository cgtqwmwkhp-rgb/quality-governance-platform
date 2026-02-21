"""CAPA (Corrective and Preventive Action) API routes."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.capa import CAPAListResponse, CAPAResponse, CAPAStatsResponse
from src.api.schemas.error_codes import ErrorCode
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter()


class CAPACreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    capa_type: CAPAType
    priority: CAPAPriority = CAPAPriority.MEDIUM
    source_type: CAPASource | None = None
    source_id: int | None = None
    root_cause: str | None = None
    proposed_action: str | None = None
    verification_method: str | None = None
    effectiveness_criteria: str | None = None
    assigned_to_id: int | None = None
    due_date: datetime | None = None
    iso_standard: str | None = None
    clause_reference: str | None = None


class CAPAUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: CAPAPriority | None = None
    root_cause: str | None = None
    proposed_action: str | None = None
    verification_method: str | None = None
    verification_result: str | None = None
    effectiveness_criteria: str | None = None
    assigned_to_id: int | None = None
    due_date: datetime | None = None


class CAPAStatusTransition(BaseModel):
    status: CAPAStatus
    comment: str | None = None


@router.get("", response_model=CAPAListResponse)
async def list_capa_actions(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[CAPAStatus] = Query(None, alias="status"),
    capa_type: Optional[CAPAType] = Query(None),
    priority: Optional[CAPAPriority] = Query(None),
    source_type: Optional[CAPASource] = Query(None),
    overdue_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(CAPAAction).where(CAPAAction.tenant_id == current_user.tenant_id)

    if status_filter:
        query = query.where(CAPAAction.status == status_filter)
    if capa_type:
        query = query.where(CAPAAction.capa_type == capa_type)
    if priority:
        query = query.where(CAPAAction.priority == priority)
    if source_type:
        query = query.where(CAPAAction.source_type == source_type)
    if overdue_only:
        query = query.where(
            CAPAAction.due_date < datetime.now(timezone.utc),
            CAPAAction.status.notin_([CAPAStatus.CLOSED]),
        )

    query = query.order_by(CAPAAction.created_at.desc())
    params = PaginationParams(page=page, page_size=page_size)
    return await paginate(db, query, params)


@router.post("", response_model=CAPAResponse, status_code=status.HTTP_201_CREATED)
async def create_capa_action(
    db: DbSession,
    current_user: CurrentUser,
    data: CAPACreate,
):
    _span = tracer.start_span("create_capa") if tracer else None
    if _span:
        _span.set_attribute("tenant_id", str(getattr(current_user, "tenant_id", 0) or 0))
    ref = await ReferenceNumberService.generate(db, "capa", CAPAAction)
    action = CAPAAction(
        reference_number=ref,
        created_by_id=current_user.id,
        tenant_id=getattr(current_user, "tenant_id", None),
        **data.model_dump(),
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    await invalidate_tenant_cache(current_user.tenant_id, "capa")
    track_metric("capa.created")
    if _span:
        _span.end()

    from src.domain.services.audit_service import record_audit_event

    await record_audit_event(
        db=db,
        event_type="capa.created",
        entity_type="capa",
        entity_id=str(action.id),
        action="create",
        description=f"CAPA {action.reference_number} created",
        payload=data.model_dump(mode="json"),
        user_id=current_user.id,
    )

    return action


@router.get("/stats", response_model=CAPAStatsResponse)
async def get_capa_stats(
    db: DbSession,
    current_user: CurrentUser,
):
    tenant_filter = CAPAAction.tenant_id == current_user.tenant_id
    total = await db.execute(select(func.count(CAPAAction.id)).where(tenant_filter))
    open_count = await db.execute(
        select(func.count(CAPAAction.id)).where(tenant_filter, CAPAAction.status == CAPAStatus.OPEN)
    )
    in_progress = await db.execute(
        select(func.count(CAPAAction.id)).where(tenant_filter, CAPAAction.status == CAPAStatus.IN_PROGRESS)
    )
    overdue = await db.execute(
        select(func.count(CAPAAction.id)).where(
            tenant_filter,
            CAPAAction.due_date < datetime.now(timezone.utc),
            CAPAAction.status.notin_([CAPAStatus.CLOSED]),
        )
    )
    return {
        "total": total.scalar_one(),
        "open": open_count.scalar_one(),
        "in_progress": in_progress.scalar_one(),
        "overdue": overdue.scalar_one(),
    }


@router.get("/{capa_id}", response_model=CAPAResponse)
async def get_capa_action(
    capa_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    return await get_or_404(db, CAPAAction, capa_id, tenant_id=current_user.tenant_id)


@router.patch("/{capa_id}", response_model=CAPAResponse)
async def update_capa_action(
    capa_id: int,
    db: DbSession,
    current_user: CurrentUser,
    data: CAPAUpdate,
):
    action = await get_or_404(db, CAPAAction, capa_id, tenant_id=current_user.tenant_id)
    apply_updates(action, data)
    await db.commit()
    await db.refresh(action)
    await invalidate_tenant_cache(current_user.tenant_id, "capa")
    return action


@router.post("/{capa_id}/transition", response_model=CAPAResponse)
async def transition_capa_status(
    capa_id: int,
    db: DbSession,
    current_user: CurrentUser,
    data: CAPAStatusTransition,
):
    action = await get_or_404(db, CAPAAction, capa_id, tenant_id=current_user.tenant_id)

    valid_transitions = {
        CAPAStatus.OPEN: [CAPAStatus.IN_PROGRESS],
        CAPAStatus.IN_PROGRESS: [CAPAStatus.VERIFICATION, CAPAStatus.OPEN],
        CAPAStatus.VERIFICATION: [CAPAStatus.CLOSED, CAPAStatus.IN_PROGRESS],
        CAPAStatus.OVERDUE: [CAPAStatus.IN_PROGRESS, CAPAStatus.CLOSED],
    }

    current = action.status
    if data.status not in valid_transitions.get(current, []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.INVALID_STATE_TRANSITION,
        )

    action.status = data.status
    if data.status == CAPAStatus.VERIFICATION:
        action.completed_at = datetime.now(timezone.utc)
    elif data.status == CAPAStatus.CLOSED:
        action.verified_at = datetime.now(timezone.utc)
        action.verified_by_id = current_user.id
        track_metric("capa.closed")

    from src.domain.services.audit_service import record_audit_event

    await record_audit_event(
        db=db,
        event_type="capa.status_changed",
        entity_type="capa",
        entity_id=str(action.id),
        action="update",
        description=f"CAPA {action.reference_number} transitioned from {current} to {data.status}",
        payload={"from_status": str(current), "to_status": str(data.status), "comment": data.comment},
        user_id=current_user.id,
    )

    await db.commit()
    await db.refresh(action)
    return action


@router.delete("/{capa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capa_action(
    capa_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
):
    action = await get_or_404(db, CAPAAction, capa_id, tenant_id=current_user.tenant_id)

    from src.domain.services.audit_service import record_audit_event

    await record_audit_event(
        db=db,
        event_type="capa.deleted",
        entity_type="capa",
        entity_id=str(action.id),
        action="delete",
        description=f"CAPA {action.reference_number} deleted",
        payload={"capa_id": capa_id, "reference_number": action.reference_number},
        user_id=current_user.id,
    )

    await db.delete(action)
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "capa")
