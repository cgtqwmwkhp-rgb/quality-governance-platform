"""Incident API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func as sa_func
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.api.routes._runner_sheet import assert_can_delete_runner_sheet_entry
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.incident import IncidentCreate, IncidentListResponse, IncidentResponse, IncidentUpdate
from src.api.schemas.running_sheet import RunningSheetEntryCreate, RunningSheetEntryResponse
from src.api.utils.errors import api_error
from src.api.utils.pagination import PaginationParams
from src.domain.models.incident import Incident, IncidentRunningSheetEntry
from src.domain.services.audit_service import record_audit_event
from src.domain.services.incident_service import IncidentService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident(
    incident_data: IncidentCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> Incident:
    """
    Report a new incident.

    Requires authentication. Delegates to IncidentService for audit trail,
    cache invalidation, and telemetry.
    """
    svc = IncidentService(db)
    try:
        has_set_ref = current_user.has_permission("incident:set_reference_number")
        incident = await svc.create_incident(
            incident_data=incident_data,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            has_set_ref_permission=has_set_ref,
            request_id=request_id,
        )
        return incident
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=api_error(ErrorCode.PERMISSION_DENIED, str(e)),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=api_error(ErrorCode.DUPLICATE_ENTITY, str(e)),
        )


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Incident:
    """
    Get an incident by ID.

    Requires authentication.
    """
    svc = IncidentService(db)
    try:
        return await svc.get_incident(
            incident_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, f"Incident {incident_id} not found"),
        )


@router.get("/", response_model=IncidentListResponse)
async def list_incidents(
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    reporter_email: Optional[str] = Query(None, description="Filter by reporter email"),
) -> IncidentListResponse:
    """
    List all incidents with deterministic ordering.

    Incidents are ordered by reported_date DESC, id ASC.
    Requires authentication. Users can only filter by their own email
    unless they have admin permissions.
    """
    svc = IncidentService(db)

    if reporter_email:
        user_email = getattr(current_user, "email", None)
        has_view_all = (
            current_user.has_permission("incident:view_all") if hasattr(current_user, "has_permission") else False
        )
        is_superuser = getattr(current_user, "is_superuser", False)

        if not await svc.check_reporter_email_access(reporter_email, user_email, has_view_all, is_superuser):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=api_error(
                    ErrorCode.PERMISSION_DENIED,
                    "You can only view your own incidents",
                ),
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
        result = await svc.list_incidents(
            tenant_id=current_user.tenant_id,
            params=PaginationParams(page=page, page_size=page_size),
            reporter_email=reporter_email,
            skip_tenant_check=current_user.is_superuser,
        )
        return IncidentListResponse(
            items=[IncidentResponse.model_validate(i) for i in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            pages=result.pages,
        )
    except Exception as e:
        error_str = str(e).lower()
        logger.error("Error listing incidents: %s", e, exc_info=True)

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
            logger.warning("Database column missing - migration may be pending")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=api_error(
                    ErrorCode.DATABASE_ERROR,
                    "Database migration pending. Please wait for migrations to complete.",
                ),
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=api_error(
                ErrorCode.INTERNAL_ERROR,
                "Unable to list incidents at this time.",
            ),
        )


@router.get("/{incident_id}/investigations", response_model=dict)
async def list_incident_investigations(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page (1-100)"),
):
    """
    List investigations for a specific incident (paginated).

    Requires authentication.
    Returns investigations assigned to this incident with pagination.
    Deterministic ordering: created_at DESC, id ASC.
    """
    from math import ceil

    from src.api.schemas.investigation import InvestigationRunResponse
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun

    svc = IncidentService(db)
    try:
        await svc.get_incident(
            incident_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, f"Incident {incident_id} not found"),
        )

    count_query = (
        select(sa_func.count())
        .select_from(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.REPORTING_INCIDENT,
            InvestigationRun.assigned_entity_id == incident_id,
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
            InvestigationRun.assigned_entity_type == AssignedEntityType.REPORTING_INCIDENT,
            InvestigationRun.assigned_entity_id == incident_id,
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


@router.get("/{incident_id}/running-sheet", response_model=list[RunningSheetEntryResponse])
async def list_incident_running_sheet_entries(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List incident runner-sheet entries, newest first."""
    svc = IncidentService(db)
    try:
        await svc.get_incident(
            incident_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, f"Incident {incident_id} not found"),
        )

    result = await db.execute(
        select(IncidentRunningSheetEntry)
        .where(IncidentRunningSheetEntry.incident_id == incident_id)
        .order_by(IncidentRunningSheetEntry.created_at.desc(), IncidentRunningSheetEntry.id.asc())
    )
    return result.scalars().all()


@router.post(
    "/{incident_id}/running-sheet",
    response_model=RunningSheetEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_incident_running_sheet_entry(
    incident_id: int,
    payload: RunningSheetEntryCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Add a timestamped entry to the incident runner sheet."""
    svc = IncidentService(db)
    try:
        incident = await svc.get_incident(
            incident_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, f"Incident {incident_id} not found"),
        )

    entry = IncidentRunningSheetEntry(
        tenant_id=incident.tenant_id,
        incident_id=incident.id,
        content=payload.content,
        entry_type=payload.entry_type.value,
        author_id=current_user.id,
        author_email=current_user.email,
    )
    db.add(entry)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="incident.runner_sheet_entry.created",
        entity_type="incident",
        entity_id=str(incident.id),
        action="create",
        description=f"Runner-sheet entry added to incident {incident.reference_number}",
        payload={"entry_id": entry.id, "entry_type": entry.entry_type},
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{incident_id}/running-sheet/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident_running_sheet_entry(
    incident_id: int,
    entry_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> None:
    """Delete an incident runner-sheet entry."""
    svc = IncidentService(db)
    try:
        incident = await svc.get_incident(
            incident_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, f"Incident {incident_id} not found"),
        )

    result = await db.execute(
        select(IncidentRunningSheetEntry).where(
            IncidentRunningSheetEntry.id == entry_id,
            IncidentRunningSheetEntry.incident_id == incident_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Runner-sheet entry not found"),
        )

    assert_can_delete_runner_sheet_entry(current_user, entry.author_id, "incident")

    await record_audit_event(
        db=db,
        event_type="incident.runner_sheet_entry.deleted",
        entity_type="incident",
        entity_id=str(incident.id),
        action="delete",
        description=f"Runner-sheet entry deleted from incident {incident.reference_number}",
        payload={"entry_id": entry.id, "entry_type": entry.entry_type},
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.delete(entry)
    await db.commit()


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: int,
    incident_data: IncidentUpdate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> Incident:
    """
    Partially update an incident.

    Requires authentication. StateTransitionError is caught by the
    global domain error handler and returned as a structured JSON response.
    """
    svc = IncidentService(db)
    try:
        return await svc.update_incident(
            incident_id,
            incident_data,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, f"Incident {incident_id} not found"),
        )


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> None:
    """
    Delete an incident.

    Requires authentication.
    """
    svc = IncidentService(db)
    try:
        await svc.delete_incident(
            incident_id,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, f"Incident {incident_id} not found"),
        )
