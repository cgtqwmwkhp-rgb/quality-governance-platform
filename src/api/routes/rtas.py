"""Road Traffic Collision API routes."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
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
from src.domain.models.rta import RTAAction, RoadTrafficCollision
from src.domain.services.audit_service import record_audit_event

router = APIRouter(tags=["Road Traffic Collisions"])


@router.post("/", response_model=RTAResponse, status_code=status.HTTP_201_CREATED)
async def create_rta(
    rta_in: RTACreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Create a new Road Traffic Collision (RTA)."""
    # Generate reference number (format: RTA-YYYY-NNNN)
    year = datetime.now(timezone.utc).year

    # Count existing RTAs for this year to generate sequence
    query = select(func.count()).select_from(RoadTrafficCollision)
    result = await db.execute(query)
    count = result.scalar() or 0
    ref_number = f"RTA-{year}-{count + 1:04d}"

    rta = RoadTrafficCollision(
        **rta_in.model_dump(),
        reference_number=ref_number,
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
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """List RTAs with deterministic ordering and pagination."""
    query = select(RoadTrafficCollision)

    # Apply filters
    if severity:
        query = query.where(RoadTrafficCollision.severity == severity)
    if status:
        query = query.where(RoadTrafficCollision.status == status)

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
        "total_pages": total_pages,
    }


@router.get("/{rta_id}", response_model=RTAResponse)
async def get_rta(
    rta_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get an RTA by ID."""
    rta = await db.get(RoadTrafficCollision, rta_id)
    if not rta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RTA with id {rta_id} not found",
        )
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
    rta = await db.get(RoadTrafficCollision, rta_id)
    if not rta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RTA with id {rta_id} not found",
        )

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
    rta = await db.get(RoadTrafficCollision, rta_id)
    if not rta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RTA with id {rta_id} not found",
        )

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

@router.post("/{rta_id}/actions", response_model=RTAActionResponse, status_code=status.HTTP_201_CREATED)
async def create_rta_action(
    rta_id: int,
    action_in: RTAActionCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Create a new action for an RTA."""
    # Verify RTA exists
    rta = await db.get(RoadTrafficCollision, rta_id)
    if not rta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RTA with id {rta_id} not found",
        )

    # Generate reference number (format: RTAACT-YYYY-NNNN)
    year = datetime.now(timezone.utc).year
    query = select(func.count()).select_from(RTAAction)
    result = await db.execute(query)
    count = result.scalar() or 0
    ref_number = f"RTAACT-{year}-{count + 1:04d}"

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
    # Verify RTA exists
    rta = await db.get(RoadTrafficCollision, rta_id)
    if not rta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RTA with id {rta_id} not found",
        )

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
        "total_pages": total_pages,
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
    # Verify RTA exists
    rta = await db.get(RoadTrafficCollision, rta_id)
    if not rta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RTA with id {rta_id} not found",
        )

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
    # Verify RTA exists
    rta = await db.get(RoadTrafficCollision, rta_id)
    if not rta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RTA with id {rta_id} not found",
        )

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


@router.get("/{rta_id}/investigations")
async def list_rta_investigations(
    rta_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    List investigations for a specific RTA.

    Requires authentication.
    Returns investigations assigned to this RTA.
    """
    from src.api.schemas.investigation import InvestigationRunResponse
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun

    # Verify RTA exists
    rta = await db.get(RoadTrafficCollision, rta_id)
    if not rta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RTA with ID {rta_id} not found",
        )

    result = await db.execute(
        select(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.ROAD_TRAFFIC_COLLISION,
            InvestigationRun.assigned_entity_id == rta_id,
        )
        .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
    )
    investigations = result.scalars().all()
    return [InvestigationRunResponse.model_validate(inv) for inv in investigations]
