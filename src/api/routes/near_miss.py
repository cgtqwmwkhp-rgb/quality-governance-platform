"""Near Miss API routes."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.api.schemas.investigation import InvestigationRunListResponse
from src.api.schemas.near_miss import NearMissCreate, NearMissListResponse, NearMissResponse, NearMissUpdate
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.near_miss import NearMiss
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter(tags=["Near Misses"])


@router.post("/", response_model=NearMissResponse, status_code=status.HTTP_201_CREATED)
async def create_near_miss(
    data: NearMissCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> NearMiss:
    """
    Report a new near miss.

    Near misses are events that could have resulted in injury, damage, or loss
    but didn't. Tracking these helps prevent future incidents.
    """
    reference_number = await ReferenceNumberService.generate(db, "near_miss", NearMiss)

    near_miss = NearMiss(
        **data.model_dump(),
        reference_number=reference_number,
        status="REPORTED",
        priority="MEDIUM",
        tenant_id=current_user.tenant_id,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
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

    await db.commit()
    await db.refresh(near_miss)
    await invalidate_tenant_cache(current_user.tenant_id, "near_miss")
    track_metric("near_miss.mutation", 1)
    return near_miss


@router.get("/", response_model=NearMissListResponse)
async def list_near_misses(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    contract: Optional[str] = Query(None),
    reporter_email: Optional[str] = Query(None, description="Filter by reporter email"),
) -> NearMissListResponse:
    """
    List near misses with pagination and filtering.

    Ordered by event_date DESC, id ASC for deterministic results.
    """
    query = (
        select(NearMiss)
        .where(NearMiss.tenant_id == current_user.tenant_id)
        .options(
            selectinload(NearMiss.assigned_to),
            selectinload(NearMiss.created_by),
            selectinload(NearMiss.updated_by),
            selectinload(NearMiss.closed_by),
        )
    )

    if reporter_email:
        query = query.where(NearMiss.reporter_email == reporter_email)
    if status_filter:
        query = query.where(NearMiss.status == status_filter)
    if priority:
        query = query.where(NearMiss.priority == priority)
    if contract:
        query = query.where(NearMiss.contract == contract)

    query = query.order_by(NearMiss.event_date.desc(), NearMiss.id.asc())
    params = PaginationParams(page=page, page_size=page_size)
    paginated = await paginate(db, query, params)

    return NearMissListResponse(
        items=[NearMissResponse.model_validate(nm) for nm in paginated.items],
        total=paginated.total,
        page=paginated.page,
        page_size=paginated.page_size,
        pages=paginated.pages,
    )


@router.get("/{near_miss_id}", response_model=NearMissResponse)
async def get_near_miss(
    near_miss_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> NearMiss:
    """Get a near miss by ID."""
    return await get_or_404(db, NearMiss, near_miss_id, tenant_id=current_user.tenant_id)


@router.patch("/{near_miss_id}", response_model=NearMissResponse)
async def update_near_miss(
    near_miss_id: int,
    data: NearMissUpdate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> NearMiss:
    """Update a near miss."""
    near_miss = await get_or_404(db, NearMiss, near_miss_id, tenant_id=current_user.tenant_id)
    old_status = near_miss.status
    update_data = apply_updates(near_miss, data, set_updated_at=False)

    if "status" in update_data:
        if update_data["status"] == "CLOSED" and near_miss.closed_at is None:
            near_miss.closed_at = datetime.now(timezone.utc)
            near_miss.closed_by_id = current_user.id

    if "assigned_to_id" in update_data and near_miss.assigned_at is None:
        near_miss.assigned_at = datetime.now(timezone.utc)

    near_miss.updated_by_id = current_user.id

    await record_audit_event(
        db=db,
        event_type="near_miss.updated",
        entity_type="near_miss",
        entity_id=str(near_miss.id),
        action="update",
        description=f"Near Miss {near_miss.reference_number} updated",
        payload={"updates": update_data, "old_status": old_status, "new_status": near_miss.status},
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.commit()
    await db.refresh(near_miss)
    await invalidate_tenant_cache(current_user.tenant_id, "near_miss")
    track_metric("near_miss.mutation", 1)
    return near_miss


@router.delete("/{near_miss_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_near_miss(
    near_miss_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
    request_id: str = Depends(get_request_id),
) -> None:
    """Delete a near miss."""
    near_miss = await get_or_404(db, NearMiss, near_miss_id, tenant_id=current_user.tenant_id)

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
    await invalidate_tenant_cache(current_user.tenant_id, "near_miss")
    track_metric("near_miss.mutation", 1)


@router.get("/{near_miss_id}/investigations", response_model=InvestigationRunListResponse)
async def list_near_miss_investigations(
    near_miss_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """List investigations for a near miss."""
    from src.api.schemas.investigation import InvestigationRunResponse
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun

    await get_or_404(db, NearMiss, near_miss_id, tenant_id=current_user.tenant_id)

    query = (
        select(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.NEAR_MISS,
            InvestigationRun.assigned_entity_id == near_miss_id,
        )
        .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
    )
    params = PaginationParams(page=page, page_size=page_size)
    paginated = await paginate(db, query, params)

    return {
        "items": [InvestigationRunResponse.model_validate(inv) for inv in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
    }
