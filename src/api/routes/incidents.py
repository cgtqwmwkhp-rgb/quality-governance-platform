"""Incident API routes."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.api.schemas.incident import (
    IncidentCreate,
    IncidentListResponse,
    IncidentResponse,
    IncidentUpdate,
)
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.incident import Incident
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter()


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

    Requires authentication.
    """
    # Generate or use provided reference number
    if incident_data.reference_number:
        # Guard: Only authorized users can set explicit reference numbers
        if not current_user.has_permission("incident:set_reference_number"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission 'incident:set_reference_number' required to set explicit reference number",
            )

        reference_number = incident_data.reference_number
        # Check for duplicate reference number
        existing = await db.execute(
            select(Incident).where(Incident.reference_number == reference_number)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Incident with reference number {reference_number} already exists",
            )
    else:
        reference_number = await ReferenceNumberService.generate(
            db, "incident", Incident
        )

    # Create new incident
    incident = Incident(
        title=incident_data.title,
        description=incident_data.description,
        incident_type=incident_data.incident_type,
        severity=incident_data.severity,
        status=incident_data.status,
        incident_date=incident_data.incident_date,
        reported_date=datetime.now(timezone.utc),
        location=incident_data.location,
        department=incident_data.department,
        reference_number=reference_number,
        reporter_id=current_user.id,
        reporter_email=incident_data.reporter_email,
        reporter_name=incident_data.reporter_name,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )

    db.add(incident)
    await db.flush()  # Get ID before recording event

    await record_audit_event(
        db=db,
        event_type="incident.created",
        entity_type="incident",
        entity_id=str(incident.id),
        action="create",
        description=f"Incident {incident.reference_number} created",
        payload=incident_data.model_dump(mode="json"),
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.commit()
    await db.refresh(incident)
    await invalidate_tenant_cache(current_user.tenant_id, "incidents")
    track_metric("incidents.created")
    return incident


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
    return await get_or_404(db, Incident, incident_id, tenant_id=current_user.tenant_id)


@router.get("/", response_model=IncidentListResponse)
async def list_incidents(
    db: DbSession,
    current_user: CurrentUser,  # SECURITY FIX: Always require authentication
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
    # SECURITY FIX: If filtering by email, enforce that users can only access their own data
    # unless they have admin/view-all permissions
    if reporter_email:
        user_email = getattr(current_user, "email", None)
        has_view_all = (
            current_user.has_permission("incident:view_all")
            if hasattr(current_user, "has_permission")
            else False
        )
        is_superuser = getattr(current_user, "is_superuser", False)

        if not has_view_all and not is_superuser:
            if user_email and reporter_email.lower() != user_email.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own incidents",
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
                "is_own_email": user_email
                and reporter_email.lower() == user_email.lower(),
                "has_view_all_permission": has_view_all,
                "is_superuser": is_superuser,
            },
            user_id=current_user.id,
            request_id=request_id,
        )

    import logging

    logger = logging.getLogger(__name__)

    try:
        query = (
            select(Incident)
            .options(selectinload(Incident.actions))
            .where(Incident.tenant_id == current_user.tenant_id)
        )

        if reporter_email:
            query = query.where(Incident.reporter_email == reporter_email)

        query = query.order_by(Incident.reported_date.desc(), Incident.id.asc())

        return await paginate(db, query, params)
    except Exception as e:
        error_str = str(e).lower()
        logger.error(f"Error listing incidents: {e}", exc_info=True)

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

        is_column_error = any(err in error_str for err in column_errors)

        if is_column_error:
            logger.warning("Database column missing - migration may be pending")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database migration pending. Please wait for migrations to complete.",
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing incidents: {type(e).__name__}: {str(e)[:200]}",
        )


@router.get("/{incident_id}/investigations", response_model=dict)
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
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun

    await get_or_404(db, Incident, incident_id, tenant_id=current_user.tenant_id)

    query = (
        select(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type
            == AssignedEntityType.REPORTING_INCIDENT,
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
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> Incident:
    """
    Partially update an incident.

    Requires authentication.
    """
    incident = await get_or_404(
        db, Incident, incident_id, tenant_id=current_user.tenant_id
    )

    update_dict = apply_updates(incident, incident_data, set_updated_at=False)

    incident.updated_by_id = current_user.id
    incident.updated_at = datetime.now(timezone.utc)

    await record_audit_event(
        db=db,
        event_type="incident.updated",
        entity_type="incident",
        entity_id=str(incident.id),
        action="update",
        description=f"Incident {incident.reference_number} updated",
        payload=update_dict,
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.commit()
    await db.refresh(incident)
    await invalidate_tenant_cache(current_user.tenant_id, "incidents")
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
    incident = await get_or_404(
        db, Incident, incident_id, tenant_id=current_user.tenant_id
    )

    # Record audit event
    await record_audit_event(
        db=db,
        event_type="incident.deleted",
        entity_type="incident",
        entity_id=str(incident.id),
        action="delete",
        description=f"Incident {incident.reference_number} deleted",
        payload={
            "incident_id": incident_id,
            "reference_number": incident.reference_number,
        },
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.delete(incident)
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "incidents")
