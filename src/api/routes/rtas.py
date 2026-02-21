"""Road Traffic Collision API routes."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.rta import RoadTrafficCollision, RTAAction
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter(tags=["Road Traffic Collisions"])


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
    await invalidate_tenant_cache(current_user.tenant_id, "rtas")
    track_metric("rta.mutation", 1)
    return rta


@router.get("/", response_model=RTAListResponse)
async def list_rtas(
    db: DbSession,
    current_user: CurrentUser,  # SECURITY FIX: Always require authentication
    request_id: str = Depends(get_request_id),
    params: PaginationParams = Depends(),
    severity: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    reporter_email: Optional[str] = Query(None, description="Filter by reporter email"),
):
    """List RTAs with deterministic ordering and pagination.

    Requires authentication. Users can only filter by their own email
    unless they have admin permissions.
    """
    import logging

    logger = logging.getLogger(__name__)

    # SECURITY FIX: If filtering by email, enforce that users can only access their own data
    # unless they have admin/view-all permissions
    if reporter_email:
        user_email = getattr(current_user, "email", None)
        has_view_all = current_user.has_permission("rta:view_all") if hasattr(current_user, "has_permission") else False
        is_superuser = getattr(current_user, "is_superuser", False)

        if not has_view_all and not is_superuser:
            if user_email and reporter_email.lower() != user_email.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own RTAs",
                )

        await record_audit_event(
            db=db,
            event_type="rta.list_filtered",
            entity_type="rta",
            entity_id="*",
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
        query = (
            select(RoadTrafficCollision)
            .options(selectinload(RoadTrafficCollision.actions))
            .where(RoadTrafficCollision.tenant_id == current_user.tenant_id)
        )

        if severity:
            query = query.where(RoadTrafficCollision.severity == severity)
        if status_filter:
            query = query.where(RoadTrafficCollision.status == status_filter)
        if reporter_email:
            query = query.where(RoadTrafficCollision.reporter_email == reporter_email)

        query = query.order_by(RoadTrafficCollision.created_at.desc(), RoadTrafficCollision.id.asc())

        paginated = await paginate(db, query, params)
        return {
            "items": paginated.items,
            "total": paginated.total,
            "page": paginated.page,
            "page_size": paginated.page_size,
            "pages": paginated.pages,
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
    return await get_or_404(db, RoadTrafficCollision, rta_id, tenant_id=current_user.tenant_id)


@router.patch("/{rta_id}", response_model=RTAResponse)
async def update_rta(
    rta_id: int,
    rta_in: RTAUpdate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Partially update an RTA."""
    rta = await get_or_404(db, RoadTrafficCollision, rta_id, tenant_id=current_user.tenant_id)
    update_data = apply_updates(rta, rta_in)
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
    await invalidate_tenant_cache(current_user.tenant_id, "rtas")
    track_metric("rta.mutation", 1)
    return rta


@router.delete("/{rta_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rta(
    rta_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Delete an RTA."""
    rta = await get_or_404(db, RoadTrafficCollision, rta_id, tenant_id=current_user.tenant_id)

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
    await invalidate_tenant_cache(current_user.tenant_id, "rtas")
    track_metric("rta.mutation", 1)


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
    rta = await get_or_404(db, RoadTrafficCollision, rta_id, tenant_id=current_user.tenant_id)

    ref_number = await ReferenceNumberService.generate(db, "rta_action", RTAAction)

    action = RTAAction(
        **action_in.model_dump(),
        rta_id=rta_id,
        reference_number=ref_number,
        tenant_id=current_user.tenant_id,
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
    params: PaginationParams = Depends(),
):
    """List actions for an RTA with deterministic ordering and pagination."""
    await get_or_404(db, RoadTrafficCollision, rta_id, tenant_id=current_user.tenant_id)

    query = (
        select(RTAAction).where(RTAAction.rta_id == rta_id).order_by(RTAAction.created_at.desc(), RTAAction.id.asc())
    )

    paginated = await paginate(db, query, params)
    return {
        "items": paginated.items,
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
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
    await get_or_404(db, RoadTrafficCollision, rta_id, tenant_id=current_user.tenant_id)
    action = await get_or_404(db, RTAAction, action_id, tenant_id=current_user.tenant_id)
    if action.rta_id != rta_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action with id {action_id} not found for RTA {rta_id}",
        )

    update_data = apply_updates(action, action_in)
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
    await get_or_404(db, RoadTrafficCollision, rta_id, tenant_id=current_user.tenant_id)
    action = await get_or_404(db, RTAAction, action_id, tenant_id=current_user.tenant_id)
    if action.rta_id != rta_id:
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
    params: PaginationParams = Depends(),
):
    """
    List investigations for a specific RTA (paginated).

    Requires authentication.
    Returns investigations assigned to this RTA with pagination.
    Deterministic ordering: created_at DESC, id ASC.
    """
    from src.api.schemas.investigation import InvestigationRunResponse
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun

    await get_or_404(db, RoadTrafficCollision, rta_id, tenant_id=current_user.tenant_id)

    query = (
        select(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.ROAD_TRAFFIC_COLLISION,
            InvestigationRun.assigned_entity_id == rta_id,
        )
        .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
    )

    paginated = await paginate(db, query, params)
    return {
        "items": [InvestigationRunResponse.model_validate(inv) for inv in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
    }
