"""API routes for Root Cause Analysis (RTA)."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.security import require_permission
from src.api.schemas.rta import RTACreate, RTAListResponse, RTAResponse, RTAUpdate
from src.domain.models.incident import Incident
from src.domain.models.rta_analysis import RootCauseAnalysis
from src.domain.services.audit_service import record_audit_event

router = APIRouter(tags=["Root Cause Analysis"])


@router.post("/", response_model=RTAResponse, status_code=status.HTTP_201_CREATED)
async def create_rta(
    rta_in: RTACreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new Root Cause Analysis (RTA). Requires rta:create permission."""
    # Check permission
    await require_permission("rta:create", current_user, db)
    # Verify incident exists
    incident = await db.get(Incident, rta_in.incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with id {rta_in.incident_id} not found",
        )

    # Generate reference number (format: RTA-YYYY-NNNN)
    year = datetime.now(timezone.utc).year

    # Count existing RTAs for this year to generate sequence
    query = select(func.count()).select_from(RootCauseAnalysis)
    result = await db.execute(query)
    count = result.scalar() or 0
    ref_number = f"RTA-{year}-{count + 1:04d}"

    rta = RootCauseAnalysis(
        **rta_in.model_dump(),
        reference_number=ref_number,
    )
    db.add(rta)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="rta.created",
        entity_type="rta",
        entity_id=str(rta.id),
        action="create",
        description=f"RTA {rta.reference_number} created for Incident {rta.incident_id}",
        user_id=current_user.id,
    )

    await db.commit()
    await db.refresh(rta)
    return rta


@router.get("/{rta_id}", response_model=RTAResponse)
async def get_rta(
    rta_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get an RTA by ID."""
    rta = await db.get(RootCauseAnalysis, rta_id)
    if not rta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RTA with id {rta_id} not found",
        )
    return rta


@router.get("/", response_model=RTAListResponse)
async def list_rtas(
    db: DbSession,
    current_user: CurrentUser,
    incident_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """List RTAs with deterministic ordering and pagination."""
    query = select(RootCauseAnalysis)

    if incident_id:
        query = query.where(RootCauseAnalysis.incident_id == incident_id)

    # Deterministic ordering: created_at DESC, id ASC
    query = query.order_by(RootCauseAnalysis.created_at.desc(), RootCauseAnalysis.id.asc())

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/{rta_id}", response_model=RTAResponse)
async def update_rta(
    rta_id: int,
    rta_in: RTAUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Partially update an RTA."""
    rta = await db.get(RootCauseAnalysis, rta_id)
    if not rta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RTA with id {rta_id} not found",
        )

    update_data = rta_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rta, field, value)

    await record_audit_event(
        db=db,
        event_type="rta.updated",
        entity_type="rta",
        entity_id=str(rta.id),
        action="update",
        description=f"RTA {rta.reference_number} updated",
        payload=update_data,
        user_id=current_user.id,
    )

    await db.commit()
    await db.refresh(rta)
    return rta
