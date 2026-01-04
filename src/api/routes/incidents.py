"""Incident API routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func as sa_func
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.incident import IncidentCreate, IncidentListResponse, IncidentResponse, IncidentUpdate
from src.api.schemas.rta import RTAListResponse, RTAResponse
from src.domain.models.incident import Incident
from src.domain.models.rta_analysis import RootCauseAnalysis
from src.domain.services.audit_service import record_audit_event

router = APIRouter()


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident(
    incident_data: IncidentCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Incident:
    """
    Report a new incident.

    Requires authentication.
    """
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
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )

    db.add(incident)
    await db.flush()  # Get ID before recording event

    await record_audit_event(
        db=db,
        event_type="incident.created",
        resource_type="incident",
        resource_id=str(incident.id),
        action="create",
        description=f"Incident {incident.reference_number} created",
        user_id=current_user.id,
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


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> IncidentListResponse:
    """
    List all incidents with deterministic ordering.

    Incidents are ordered by:
    1. reported_date DESC (newest first)
    2. id ASC (stable secondary sort)

    Requires authentication.
    """
    # Count total
    count_result = await db.execute(select(sa_func.count()).select_from(Incident))
    total = count_result.scalar_one()

    # Get paginated results with deterministic ordering
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Incident).order_by(Incident.reported_date.desc(), Incident.id.asc()).limit(page_size).offset(offset)
    )
    incidents = result.scalars().all()

    return IncidentListResponse(
        items=[IncidentResponse.model_validate(i) for i in incidents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{incident_id}/rtas", response_model=RTAListResponse)
async def list_incident_rtas(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> RTAListResponse:
    """
    List RTAs for a specific incident.

    Requires authentication.
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    result = await db.execute(
        select(RootCauseAnalysis)
        .where(RootCauseAnalysis.incident_id == incident_id)
        .order_by(RootCauseAnalysis.created_at.desc(), RootCauseAnalysis.id.asc())
    )
    rtas = result.scalars().all()
    return RTAListResponse(
        items=[RTAResponse.model_validate(rta) for rta in rtas],
        total=len(rtas),
        page=1,
        page_size=len(rtas),
    )


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: int,
    incident_data: IncidentUpdate,
    db: DbSession,
    current_user: CurrentUser,
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
        resource_type="incident",
        resource_id=str(incident.id),
        action="update",
        description=f"Incident {incident.reference_number} updated",
        payload=update_dict,
        user_id=current_user.id,
    )

    await db.commit()
    await db.refresh(incident)
    return incident
