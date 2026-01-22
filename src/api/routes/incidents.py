"""Incident API routes."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func as sa_func
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession, OptionalCurrentUser
from src.api.dependencies.request_context import get_request_id
from src.api.schemas.incident import IncidentCreate, IncidentListResponse, IncidentResponse, IncidentUpdate
from src.domain.models.incident import Incident
from src.domain.services.audit_service import record_audit_event

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
        existing = await db.execute(select(Incident).where(Incident.reference_number == reference_number))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Incident with reference number {reference_number} already exists",
            )
    else:
        # Generate reference number (format: INC-YYYY-NNNN)
        year = datetime.now(timezone.utc).year

        # Get the count of incidents created this year
        count_result = await db.execute(select(sa_func.count()).select_from(Incident))
        count = count_result.scalar_one()
        reference_number = f"INC-{year}-{count + 1:04d}"

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
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    return incident


@router.get("/", response_model=IncidentListResponse)
async def list_incidents(
    db: DbSession,
    current_user: OptionalCurrentUser,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    reporter_email: Optional[str] = Query(None, description="Filter by reporter email"),
) -> IncidentListResponse:
    """
    List all incidents with deterministic ordering.

    Incidents are ordered by:
    1. reported_date DESC (newest first)
    2. id ASC (stable secondary sort)

    Authentication is optional when filtering by reporter_email.
    This allows portal users (Azure AD auth) to view their own incidents.
    """
    # If no valid auth token and no reporter_email filter, require authentication
    if current_user is None and not reporter_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required when not filtering by reporter_email",
            headers={"WWW-Authenticate": "Bearer"},
        )

    import math
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Build base query
        query = select(Incident)
        count_query = select(sa_func.count()).select_from(Incident)

        # Filter by reporter_email if provided
        if reporter_email:
            query = query.where(Incident.reporter_email == reporter_email)
            count_query = count_query.where(Incident.reporter_email == reporter_email)

        # Count total
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()

        # Get paginated results with deterministic ordering
        offset = (page - 1) * page_size
        result = await db.execute(
            query.order_by(Incident.reported_date.desc(), Incident.id.asc()).limit(page_size).offset(offset)
        )
        incidents = result.scalars().all()

        return IncidentListResponse(
            items=[IncidentResponse.model_validate(i) for i in incidents],
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 1,
        )
    except Exception as e:
        error_str = str(e).lower()
        logger.error(f"Error listing incidents: {e}", exc_info=True)

        # Check for various database column errors
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

        # Re-raise with details for debugging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing incidents: {type(e).__name__}: {str(e)[:200]}",
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

    # Verify incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    # Get total count
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
        "total_pages": total_pages,
    }


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
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    # Update fields
    update_dict = incident_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(incident, key, value)

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
    return incident


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
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    # Record audit event
    await record_audit_event(
        db=db,
        event_type="incident.deleted",
        entity_type="incident",
        entity_id=str(incident.id),
        action="delete",
        description=f"Incident {incident.reference_number} deleted",
        payload={"incident_id": incident_id, "reference_number": incident.reference_number},
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.delete(incident)
    await db.commit()
