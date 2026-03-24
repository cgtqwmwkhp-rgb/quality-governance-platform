"""Road Traffic Collision API routes."""

import logging
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.api.routes._runner_sheet import assert_can_delete_runner_sheet_entry
from src.api.schemas.running_sheet import RunningSheetEntryCreate, RunningSheetEntryResponse
from src.api.schemas.rta import (
    RTAActionCreate,
    RTAActionListResponse,
    RTAActionResponse,
    RTAActionUpdate,
    RTACreate,
    RTAListResponse,
    RTAResponse,
    RTAUpdate,
)
from src.domain.models.rta import RoadTrafficCollision, RTAAction, RunningSheetEntry
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Road Traffic Collisions"])


async def _get_rta_or_404(db, rta_id: int, current_user) -> RoadTrafficCollision:
    """Load an RTA with tenant isolation enforced."""
    query = select(RoadTrafficCollision).where(RoadTrafficCollision.id == rta_id)
    if not getattr(current_user, "is_superuser", False):
        query = query.where(RoadTrafficCollision.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    rta = result.scalar_one_or_none()
    if not rta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RTA with id {rta_id} not found",
        )
    return rta


@router.post("/", response_model=RTAResponse, status_code=status.HTTP_201_CREATED)
async def create_rta(
    rta_in: RTACreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Create a new Road Traffic Collision (RTA)."""
    ref_number = await ReferenceNumberService.generate(db, "rta", RoadTrafficCollision)

    rta = RoadTrafficCollision(
        **rta_in.model_dump(),
        reference_number=ref_number,
        tenant_id=current_user.tenant_id,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.add(rta)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="rta.created",
        entity_type="rta",
        entity_id=str(rta.id),
        action="create",
        description=f"RTA {rta.reference_number} created",
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.commit()
    await db.refresh(rta)
    return rta


@router.get("/", response_model=RTAListResponse)
async def list_rtas(
    db: DbSession,
    current_user: CurrentUser,  # SECURITY FIX: Always require authentication
    request_id: str = Depends(get_request_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    severity: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    reporter_email: Optional[str] = Query(None, description="Filter by reporter email"),
):
    """List RTAs with deterministic ordering and pagination.

    Requires authentication. Users can only filter by their own email
    unless they have admin permissions.
    """
    # SECURITY FIX: If filtering by email, enforce that users can only access their own data
    # unless they have admin/view-all permissions
    if reporter_email:
        user_email = getattr(current_user, "email", None)
        has_view_all = current_user.has_permission("rta:view_all") if hasattr(current_user, "has_permission") else False
        is_superuser = getattr(current_user, "is_superuser", False)

        if not has_view_all and not is_superuser:
            # Non-admin users can only filter by their own email
            if user_email and reporter_email.lower() != user_email.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own RTAs",
                )

        # AUDIT: Log email filter usage for security monitoring
        # Note: We log the filter type but NOT the raw email (privacy compliance)
        await record_audit_event(
            db=db,
            event_type="rta.list_filtered",
            entity_type="rta",
            entity_id="*",  # Wildcard - listing operation
            action="list",
            description="RTA list accessed with email filter",
            payload={
                "filter_type": "reporter_email",
                "is_own_email": user_email and reporter_email.lower() == user_email.lower(),
                "has_view_all_permission": has_view_all,
                "is_superuser": is_superuser,
            },
            user_id=current_user.id,
            request_id=request_id,
        )

    try:
        query = select(RoadTrafficCollision)

        if not getattr(current_user, "is_superuser", False):
            query = query.where(RoadTrafficCollision.tenant_id == current_user.tenant_id)

        if severity:
            query = query.where(RoadTrafficCollision.severity == severity)
        if status_filter:
            query = query.where(RoadTrafficCollision.status == status_filter)
        if reporter_email:
            query = query.where(RoadTrafficCollision.reporter_email == reporter_email)

        # Deterministic ordering: created_at DESC, id ASC
        query = query.order_by(RoadTrafficCollision.created_at.desc(), RoadTrafficCollision.id.asc())

        # Total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Calculate total pages
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        # Pagination
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": total_pages,
        }
    except Exception as e:
        error_str = str(e).lower()
        logger.error(f"Error listing RTAs: {e}", exc_info=True)

        column_errors = [
            "reporter_email",
            "column",
            "does not exist",
            "unknown column",
            "programmingerror",
            "relation",
        ]
        is_column_error = any(err in error_str for err in column_errors)

        if is_column_error:
            logger.warning("Database column missing - migration may be pending")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database migration pending. Please wait for migrations to complete.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing RTAs: {type(e).__name__}: {str(e)[:200]}",
        )


@router.get("/{rta_id}", response_model=RTAResponse)
async def get_rta(
    rta_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get an RTA by ID."""
    rta = await _get_rta_or_404(db, rta_id, current_user)
    return rta


@router.patch("/{rta_id}", response_model=RTAResponse)
async def update_rta(
    rta_id: int,
    rta_in: RTAUpdate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Partially update an RTA."""
    rta = await _get_rta_or_404(db, rta_id, current_user)

    update_data = rta_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rta, field, value)

    rta.updated_by_id = current_user.id

    await record_audit_event(
        db=db,
        event_type="rta.updated",
        entity_type="rta",
        entity_id=str(rta.id),
        action="update",
        description=f"RTA {rta.reference_number} updated",
        payload=update_data,
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.commit()
    await db.refresh(rta)
    return rta


@router.delete("/{rta_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rta(
    rta_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Delete an RTA."""
    rta = await _get_rta_or_404(db, rta_id, current_user)

    await record_audit_event(
        db=db,
        event_type="rta.deleted",
        entity_type="rta",
        entity_id=str(rta.id),
        action="delete",
        description=f"RTA {rta.reference_number} deleted",
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.delete(rta)
    await db.commit()


# RTA Actions endpoints


@router.post(
    "/{rta_id}/actions",
    response_model=RTAActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rta_action(
    rta_id: int,
    action_in: RTAActionCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Create a new action for an RTA."""
    rta = await _get_rta_or_404(db, rta_id, current_user)

    ref_number = await ReferenceNumberService.generate(db, "rta_action", RTAAction)

    action = RTAAction(
        **action_in.model_dump(),
        rta_id=rta_id,
        reference_number=ref_number,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.add(action)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="rta_action.created",
        entity_type="rta_action",
        entity_id=str(action.id),
        action="create",
        description=f"RTA Action {action.reference_number} created for RTA {rta.reference_number}",
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.commit()
    await db.refresh(action)
    return action


@router.get("/{rta_id}/actions", response_model=RTAActionListResponse)
async def list_rta_actions(
    rta_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """List actions for an RTA with deterministic ordering and pagination."""
    await _get_rta_or_404(db, rta_id, current_user)

    query = select(RTAAction).where(RTAAction.rta_id == rta_id)

    # Deterministic ordering: created_at DESC, id ASC
    query = query.order_by(RTAAction.created_at.desc(), RTAAction.id.asc())

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    # Pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": total_pages,
    }


@router.patch("/{rta_id}/actions/{action_id}", response_model=RTAActionResponse)
async def update_rta_action(
    rta_id: int,
    action_id: int,
    action_in: RTAActionUpdate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Update an RTA action."""
    await _get_rta_or_404(db, rta_id, current_user)

    # Get action
    action = await db.get(RTAAction, action_id)
    if not action or action.rta_id != rta_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action with id {action_id} not found for RTA {rta_id}",
        )

    update_data = action_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(action, field, value)

    action.updated_by_id = current_user.id

    await record_audit_event(
        db=db,
        event_type="rta_action.updated",
        entity_type="rta_action",
        entity_id=str(action.id),
        action="update",
        description=f"RTA Action {action.reference_number} updated",
        payload=update_data,
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.commit()
    await db.refresh(action)
    return action


@router.delete("/{rta_id}/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rta_action(
    rta_id: int,
    action_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Delete an RTA action."""
    await _get_rta_or_404(db, rta_id, current_user)

    # Get action
    action = await db.get(RTAAction, action_id)
    if not action or action.rta_id != rta_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action with id {action_id} not found for RTA {rta_id}",
        )

    await record_audit_event(
        db=db,
        event_type="rta_action.deleted",
        entity_type="rta_action",
        entity_id=str(action.id),
        action="delete",
        description=f"RTA Action {action.reference_number} deleted",
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.delete(action)
    await db.commit()


@router.get("/{rta_id}/investigations", response_model=dict)
async def list_rta_investigations(
    rta_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page (1-100)"),
):
    """
    List investigations for a specific RTA (paginated).

    Requires authentication.
    Returns investigations assigned to this RTA with pagination.
    Deterministic ordering: created_at DESC, id ASC.
    """
    from src.api.schemas.investigation import InvestigationRunResponse
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun

    await _get_rta_or_404(db, rta_id, current_user)

    # Get total count
    count_query = (
        select(func.count())
        .select_from(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.ROAD_TRAFFIC_COLLISION,
            InvestigationRun.assigned_entity_id == rta_id,
        )
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Calculate total pages
    total_pages = ceil(total / page_size) if total > 0 else 1

    # Get paginated results
    query = (
        select(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.ROAD_TRAFFIC_COLLISION,
            InvestigationRun.assigned_entity_id == rta_id,
        )
        .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    investigations = result.scalars().all()

    return {
        "items": [InvestigationRunResponse.model_validate(inv) for inv in investigations],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": total_pages,
    }


# ---------------------------------------------------------------------------
# Running Sheet Endpoints
# ---------------------------------------------------------------------------


@router.get("/{rta_id}/running-sheet", response_model=list[RunningSheetEntryResponse])
async def list_running_sheet_entries(
    rta_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List all running sheet entries for an RTA, newest first."""
    await _get_rta_or_404(db, rta_id, current_user)

    result = await db.execute(
        select(RunningSheetEntry)
        .where(RunningSheetEntry.rta_id == rta_id)
        .order_by(RunningSheetEntry.created_at.desc(), RunningSheetEntry.id.asc())
    )
    return result.scalars().all()


@router.post(
    "/{rta_id}/running-sheet",
    response_model=RunningSheetEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_running_sheet_entry(
    rta_id: int,
    payload: RunningSheetEntryCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Add a timestamped entry to the RTA running sheet."""
    rta = await _get_rta_or_404(db, rta_id, current_user)

    entry = RunningSheetEntry(
        tenant_id=rta.tenant_id,
        rta_id=rta_id,
        content=payload.content,
        entry_type=payload.entry_type.value,
        author_id=current_user.id,
        author_email=current_user.email,
    )
    db.add(entry)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="rta.runner_sheet_entry.created",
        entity_type="rta",
        entity_id=str(rta.id),
        action="create",
        description=f"Runner-sheet entry added to RTA {rta.reference_number}",
        payload={"entry_id": entry.id, "entry_type": entry.entry_type},
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{rta_id}/running-sheet/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_running_sheet_entry(
    rta_id: int,
    entry_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Delete a running sheet entry."""
    rta = await _get_rta_or_404(db, rta_id, current_user)

    result = await db.execute(
        select(RunningSheetEntry).where(
            RunningSheetEntry.id == entry_id,
            RunningSheetEntry.rta_id == rta_id,
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Running sheet entry not found")

    assert_can_delete_runner_sheet_entry(current_user, entry.author_id, "rta")

    await record_audit_event(
        db=db,
        event_type="rta.runner_sheet_entry.deleted",
        entity_type="rta",
        entity_id=str(rta.id),
        action="delete",
        description=f"Runner-sheet entry deleted from RTA {rta.reference_number}",
        payload={"entry_id": entry.id, "entry_type": entry.entry_type},
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.delete(entry)
    await db.commit()
