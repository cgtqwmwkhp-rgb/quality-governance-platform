"""Road Traffic Collision API routes — thin controller layer."""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession, require_permission
from src.api.dependencies.request_context import get_request_id
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.investigation import InvestigationRunListResponse, InvestigationRunResponse
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
from src.api.utils.pagination import PaginationParams
from src.domain.models.user import User
from src.domain.services.audit_service import record_audit_event
from src.domain.services.rta_service import RTAService

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Road Traffic Collisions"])


@router.post("/", response_model=RTAResponse, status_code=status.HTTP_201_CREATED)
async def create_rta(
    rta_in: RTACreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("rta:create"))],
    request_id: str = Depends(get_request_id),
):
    """Create a new Road Traffic Collision (RTA)."""
    _span = tracer.start_span("create_rta") if tracer else None
    service = RTAService(db)
    rta = await service.create_rta(
        rta_data=rta_in,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        request_id=request_id,
    )
    if _span:
        _span.end()
    return rta


@router.get("/", response_model=RTAListResponse)
async def list_rtas(
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
    params: PaginationParams = Depends(),
    severity: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    reporter_email: Optional[str] = Query(None, description="Filter by reporter email"),
):
    """List RTAs with deterministic ordering and pagination."""
    service = RTAService(db)

    if reporter_email:
        user_email = getattr(current_user, "email", None)
        has_view_all = current_user.has_permission("rta:view_all") if hasattr(current_user, "has_permission") else False
        is_superuser = getattr(current_user, "is_superuser", False)

        if not service.check_reporter_email_access(reporter_email, user_email, has_view_all, is_superuser):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorCode.PERMISSION_DENIED,
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
        paginated = await service.list_rtas(
            tenant_id=current_user.tenant_id,
            params=params,
            severity=severity,
            status_filter=status_filter,
            reporter_email=reporter_email,
        )
        return {
            "items": paginated.items,
            "total": paginated.total,
            "page": paginated.page,
            "page_size": paginated.page_size,
            "pages": paginated.pages,
        }
    except SQLAlchemyError as e:
        error_str = str(e).lower()
        logger.exception(
            "Error listing RTAs [request_id=%s]: %s",
            request_id,
            type(e).__name__,
        )
        column_errors = [
            "reporter_email",
            "column",
            "does not exist",
            "unknown column",
            "programmingerror",
            "relation",
        ]
        if any(err in error_str for err in column_errors):
            logger.warning(
                "Database column missing - migration may be pending [request_id=%s]",
                request_id,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=ErrorCode.INTERNAL_ERROR,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorCode.INTERNAL_ERROR,
        )


@router.get("/{rta_id}", response_model=RTAResponse)
async def get_rta(
    rta_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get an RTA by ID."""
    service = RTAService(db)
    try:
        return await service.get_rta(rta_id, current_user.tenant_id)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )


@router.patch("/{rta_id}", response_model=RTAResponse)
async def update_rta(
    rta_id: int,
    rta_in: RTAUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("rta:update"))],
    request_id: str = Depends(get_request_id),
):
    """Partially update an RTA."""
    service = RTAService(db)
    try:
        return await service.update_rta(
            rta_id,
            rta_in,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )


@router.delete("/{rta_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rta(
    rta_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
    request_id: str = Depends(get_request_id),
):
    """Delete an RTA."""
    service = RTAService(db)
    try:
        await service.delete_rta(
            rta_id,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )


# RTA Actions endpoints


@router.post("/{rta_id}/actions", response_model=RTAActionResponse, status_code=status.HTTP_201_CREATED)
async def create_rta_action(
    rta_id: int,
    action_in: RTAActionCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("rta:create"))],
    request_id: str = Depends(get_request_id),
):
    """Create a new action for an RTA."""
    service = RTAService(db)
    try:
        return await service.create_rta_action(
            rta_id,
            action_in,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )


@router.get("/{rta_id}/actions", response_model=RTAActionListResponse)
async def list_rta_actions(
    rta_id: int,
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
):
    """List actions for an RTA with deterministic ordering and pagination."""
    service = RTAService(db)
    try:
        paginated = await service.list_rta_actions(rta_id, current_user.tenant_id, params)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )
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
    current_user: Annotated[User, Depends(require_permission("rta:update"))],
    request_id: str = Depends(get_request_id),
):
    """Update an RTA action."""
    service = RTAService(db)
    try:
        return await service.update_rta_action(
            rta_id,
            action_id,
            action_in,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )


@router.delete("/{rta_id}/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rta_action(
    rta_id: int,
    action_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
    request_id: str = Depends(get_request_id),
):
    """Delete an RTA action."""
    service = RTAService(db)
    try:
        await service.delete_rta_action(
            rta_id,
            action_id,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )


@router.get("/{rta_id}/investigations", response_model=InvestigationRunListResponse)
async def list_rta_investigations(
    rta_id: int,
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
):
    """List investigations for a specific RTA (paginated)."""
    service = RTAService(db)
    try:
        paginated = await service.list_rta_investigations(rta_id, current_user.tenant_id, params)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )
    return {
        "items": [InvestigationRunResponse.model_validate(inv) for inv in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
    }
