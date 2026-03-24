"""Near Miss API routes."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func as sa_func
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.api.routes._runner_sheet import assert_can_delete_runner_sheet_entry
from src.api.schemas.near_miss import NearMissCreate, NearMissListResponse, NearMissResponse, NearMissUpdate
from src.api.schemas.running_sheet import RunningSheetEntryCreate, RunningSheetEntryResponse
from src.domain.models.near_miss import NearMiss, NearMissRunningSheetEntry
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService

router = APIRouter(tags=["Near Misses"])


async def _get_near_miss_or_404(db, near_miss_id: int, current_user: CurrentUser) -> NearMiss:
    query = select(NearMiss).where(NearMiss.id == near_miss_id)
    if not current_user.is_superuser:
        query = query.where(NearMiss.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    near_miss = result.scalar_one_or_none()

    if not near_miss:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Near Miss with ID {near_miss_id} not found",
        )
    return near_miss


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

    await db.commit()
    await db.refresh(near_miss)
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
    import math

    query = select(NearMiss)

    if not current_user.is_superuser:
        query = query.where(NearMiss.tenant_id == current_user.tenant_id)

    # Apply filters
    if reporter_email:
        query = query.where(NearMiss.reporter_email == reporter_email)
    if status_filter:
        query = query.where(NearMiss.status == status_filter)
    if priority:
        query = query.where(NearMiss.priority == priority)
    if contract:
        query = query.where(NearMiss.contract == contract)

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
    current_user: CurrentUser,
) -> NearMiss:
    """Get a near miss by ID."""
    return await _get_near_miss_or_404(db, near_miss_id, current_user)


@router.patch("/{near_miss_id}", response_model=NearMissResponse)
async def update_near_miss(
    near_miss_id: int,
    data: NearMissUpdate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> NearMiss:
    """Update a near miss."""
    near_miss = await _get_near_miss_or_404(db, near_miss_id, current_user)

    update_data = data.model_dump(exclude_unset=True)
    old_status = near_miss.status

    for field, value in update_data.items():
        setattr(near_miss, field, value)

    # Handle status changes
    if "status" in update_data:
        if update_data["status"] == "CLOSED" and near_miss.closed_at is None:
            near_miss.closed_at = datetime.now(timezone.utc)
            near_miss.closed_by_id = current_user.id

    # Handle assignment
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
        payload={
            "updates": update_data,
            "old_status": old_status,
            "new_status": near_miss.status,
        },
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.commit()
    await db.refresh(near_miss)
    return near_miss


@router.delete("/{near_miss_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_near_miss(
    near_miss_id: int,
    db: DbSession,
    current_user: CurrentUser,
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
    current_user: CurrentUser,
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
    current_user: CurrentUser,
):
    """List near-miss runner-sheet entries, newest first."""
    await _get_near_miss_or_404(db, near_miss_id, current_user)

    result = await db.execute(
        select(NearMissRunningSheetEntry)
        .where(NearMissRunningSheetEntry.near_miss_id == near_miss_id)
        .order_by(NearMissRunningSheetEntry.created_at.desc(), NearMissRunningSheetEntry.id.asc())
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
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Runner-sheet entry not found",
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
