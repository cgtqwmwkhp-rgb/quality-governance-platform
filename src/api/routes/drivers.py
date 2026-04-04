"""Driver Profile API routes — driver accountability.

Manages driver profiles, vehicle assignments, and defect/assignment
acknowledgement workflows linking QGP users to PAMS driver data.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.driver_profile import (
    AcknowledgementAction,
    AcknowledgementCreate,
    DriverAcknowledgementResponse,
    DriverListResponse,
    DriverProfileCreate,
    DriverProfileResponse,
    DriverProfileUpdate,
)
from src.domain.exceptions import BadRequestError, ConflictError, NotFoundError
from src.domain.models.driver_profile import AcknowledgementStatus, DriverAcknowledgement, DriverProfile

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=DriverListResponse)
async def list_drivers(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    active_only: bool = Query(True),
    search: Optional[str] = None,
):
    """List driver profiles with pagination."""
    query = select(DriverProfile)
    count_query = select(func.count(DriverProfile.id))

    if user.tenant_id:
        query = query.where(DriverProfile.tenant_id == user.tenant_id)
        count_query = count_query.where(DriverProfile.tenant_id == user.tenant_id)

    if active_only:
        query = query.where(DriverProfile.is_active_driver == True)  # noqa: E712
        count_query = count_query.where(DriverProfile.is_active_driver == True)  # noqa: E712

    if search:
        pattern = f"%{search}%"
        query = query.where(DriverProfile.pams_driver_name.ilike(pattern))
        count_query = count_query.where(DriverProfile.pams_driver_name.ilike(pattern))

    total = (await db.execute(count_query)).scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(DriverProfile.pams_driver_name).offset(offset).limit(page_size)
    result = await db.execute(query)
    drivers = result.scalars().all()

    return DriverListResponse(
        items=[DriverProfileResponse.model_validate(d) for d in drivers],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.post("/", response_model=DriverProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_driver_profile(
    body: DriverProfileCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create a new driver profile linking a user to PAMS driver data."""
    existing = await db.execute(select(DriverProfile).where(DriverProfile.user_id == body.user_id))
    if existing.scalar_one_or_none():
        raise ConflictError("Driver profile already exists for this user")

    profile = DriverProfile(
        user_id=body.user_id,
        pams_driver_name=body.pams_driver_name,
        licence_number=body.licence_number,
        licence_expiry=body.licence_expiry,
        allocated_vehicle_reg=body.allocated_vehicle_reg,
        is_active_driver=body.is_active_driver,
        tenant_id=user.tenant_id,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return DriverProfileResponse.model_validate(profile)


@router.get("/{driver_id}", response_model=DriverProfileResponse)
async def get_driver(driver_id: int, db: DbSession, user: CurrentUser):
    """Get a single driver profile."""
    query = select(DriverProfile).where(DriverProfile.id == driver_id)
    if user.tenant_id:
        query = query.where(DriverProfile.tenant_id == user.tenant_id)
    result = await db.execute(query)
    profile = result.scalar_one_or_none()
    if not profile:
        raise NotFoundError("Driver profile not found")
    return DriverProfileResponse.model_validate(profile)


@router.patch("/{driver_id}", response_model=DriverProfileResponse)
async def update_driver(
    driver_id: int,
    body: DriverProfileUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update a driver profile (vehicle assignment, licence, active status)."""
    query = select(DriverProfile).where(DriverProfile.id == driver_id)
    if user.tenant_id:
        query = query.where(DriverProfile.tenant_id == user.tenant_id)
    result = await db.execute(query)
    profile = result.scalar_one_or_none()
    if not profile:
        raise NotFoundError("Driver profile not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return DriverProfileResponse.model_validate(profile)


# --- Acknowledgement Workflow ---


@router.post("/{driver_id}/acknowledgements", response_model=DriverAcknowledgementResponse, status_code=201)
async def create_acknowledgement_request(
    driver_id: int,
    body: AcknowledgementCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create an acknowledgement request for a driver (defect or assignment)."""
    query = select(DriverProfile).where(DriverProfile.id == driver_id)
    if user.tenant_id:
        query = query.where(DriverProfile.tenant_id == user.tenant_id)
    profile = (await db.execute(query)).scalar_one_or_none()
    if not profile:
        raise NotFoundError("Driver profile not found")

    ack = DriverAcknowledgement(
        driver_profile_id=driver_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        status=AcknowledgementStatus.PENDING,
        notes=body.notes,
        tenant_id=user.tenant_id,
    )
    db.add(ack)
    await db.commit()
    await db.refresh(ack)
    return DriverAcknowledgementResponse.model_validate(ack)


@router.get("/{driver_id}/acknowledgements")
async def list_acknowledgements(
    driver_id: int,
    db: DbSession,
    user: CurrentUser,
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """List acknowledgement requests for a driver."""
    query = select(DriverAcknowledgement).where(DriverAcknowledgement.driver_profile_id == driver_id)
    if user.tenant_id:
        query = query.where(DriverAcknowledgement.tenant_id == user.tenant_id)
    if status_filter:
        try:
            ack_status = AcknowledgementStatus(status_filter.lower())
        except ValueError:
            raise BadRequestError(f"Invalid status: {status_filter}")
        query = query.where(DriverAcknowledgement.status == ack_status)

    query = query.order_by(DriverAcknowledgement.created_at.desc())
    result = await db.execute(query)
    acks = result.scalars().all()
    return {"items": [DriverAcknowledgementResponse.model_validate(a) for a in acks]}


@router.post("/acknowledgements/{ack_id}/respond", response_model=DriverAcknowledgementResponse)
async def respond_to_acknowledgement(
    ack_id: int,
    body: AcknowledgementAction,
    db: DbSession,
    user: CurrentUser,
):
    """Driver responds to an acknowledgement request (acknowledge or refuse)."""
    query = select(DriverAcknowledgement).where(DriverAcknowledgement.id == ack_id)
    if user.tenant_id:
        query = query.where(DriverAcknowledgement.tenant_id == user.tenant_id)
    result = await db.execute(query)
    ack = result.scalar_one_or_none()
    if not ack:
        raise NotFoundError("Acknowledgement not found")

    if ack.status != AcknowledgementStatus.PENDING:
        raise ConflictError("Acknowledgement already responded to")

    if body.action == "acknowledge":
        ack.status = AcknowledgementStatus.ACKNOWLEDGED
        ack.acknowledged_at = datetime.now(timezone.utc)
    elif body.action == "refuse":
        ack.status = AcknowledgementStatus.REFUSED
    else:
        raise BadRequestError("action must be 'acknowledge' or 'refuse'")

    if body.notes:
        ack.notes = body.notes

    await db.commit()
    await db.refresh(ack)
    return DriverAcknowledgementResponse.model_validate(ack)
