"""Incident API routes.

Thin controller layer — all business logic lives in IncidentService.
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession, require_permission
from src.api.dependencies.request_context import get_request_id
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.incident import IncidentCreate, IncidentListResponse, IncidentResponse, IncidentUpdate
from src.api.schemas.investigation import InvestigationRunListResponse
from src.api.schemas.links import build_collection_links, build_resource_links
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.domain.models.incident import Incident
from src.domain.models.user import User
from src.domain.services.audit_service import record_audit_event
from src.domain.services.incident_service import IncidentService
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident(
    incident_data: IncidentCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("incident:create"))],
    request_id: str = Depends(get_request_id),
) -> Incident:
    """
    Report a new incident.

    Requires authentication.
    """
    _span = tracer.start_span("create_incident") if tracer else None
    if _span:
        _span.set_attribute("tenant_id", str(current_user.tenant_id or 0))

    service = IncidentService(db)
    try:
        incident = await service.create_incident(
            incident_data=incident_data,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            has_set_ref_permission=current_user.has_permission("incident:set_reference_number"),
            request_id=request_id,
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorCode.PERMISSION_DENIED,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ErrorCode.DUPLICATE_ENTITY,
        )

    track_metric("incidents.created")
    if _span:
        _span.end()
    return incident


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """
    Get an incident by ID.

    Requires authentication.
    """
    incident = await get_or_404(db, Incident, incident_id, tenant_id=current_user.tenant_id)
    response = IncidentResponse.model_validate(incident)
    response.links = build_resource_links("", "incidents", incident_id)
    return response


@router.get("/", response_model=IncidentListResponse)
async def list_incidents(
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
    params: PaginationParams = Depends(),
    reporter_email: Optional[str] = Query(None, description="Filter by reporter email"),
) -> IncidentListResponse:
    """
    List all incidents with deterministic ordering.

    Incidents are ordered by:
    1. reported_date DESC (newest first)
    2. id ASC (stable secondary sort)

    Requires authentication. Users can only filter by their own email
    unless they have admin permissions.
    """
    service = IncidentService(db)

    if reporter_email:
        user_email = getattr(current_user, "email", None)
        has_view_all = (
            current_user.has_permission("incident:view_all") if hasattr(current_user, "has_permission") else False
        )
        is_superuser = getattr(current_user, "is_superuser", False)

        if not await service.check_reporter_email_access(reporter_email, user_email, has_view_all, is_superuser):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorCode.PERMISSION_DENIED,
            )

        await record_audit_event(
            db=db,
            event_type="incident.list_filtered",
            entity_type="incident",
            entity_id="*",
            action="list",
            description="Incident list accessed with email filter",
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
        paginated = await service.list_incidents(
            tenant_id=current_user.tenant_id,
            params=params,
            reporter_email=reporter_email,
        )
        return {
            "items": paginated.items,
            "total": paginated.total,
            "page": paginated.page,
            "page_size": paginated.page_size,
            "pages": paginated.pages,
            "links": build_collection_links("incidents", paginated.page, paginated.page_size, paginated.pages),
        }
    except SQLAlchemyError as e:
        error_str = str(e).lower()
        logger.exception(
            "Error listing incidents [request_id=%s]: %s",
            request_id,
            type(e).__name__,
        )

        column_errors = [
            "reporter_email",
            "column",
            "does not exist",
            "unknown column",
            "no such column",
            "undefined column",
            "relation",
            "programmingerror",
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


@router.get("/{incident_id}/investigations", response_model=InvestigationRunListResponse)
async def list_incident_investigations(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
):
    """
    List investigations for a specific incident (paginated).

    Requires authentication.
    Returns investigations assigned to this incident with pagination.
    Deterministic ordering: created_at DESC, id ASC.
    """
    from sqlalchemy import select

    from src.domain.models.investigation import AssignedEntityType, InvestigationRun

    await get_or_404(db, Incident, incident_id, tenant_id=current_user.tenant_id)

    query = (
        select(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.REPORTING_INCIDENT,
            InvestigationRun.assigned_entity_id == incident_id,
        )
        .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
    )

    return await paginate(db, query, params)


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: int,
    incident_data: IncidentUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("incident:update"))],
    request_id: str = Depends(get_request_id),
) -> Incident:
    """
    Partially update an incident.

    Requires authentication.
    """
    service = IncidentService(db)
    try:
        incident = await service.update_incident(
            incident_id,
            incident_data,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )
    return incident


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident(
    incident_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
    request_id: str = Depends(get_request_id),
) -> None:
    """
    Delete an incident.

    Requires authentication.
    """
    service = IncidentService(db)
    try:
        await service.delete_incident(
            incident_id,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )
