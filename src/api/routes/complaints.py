"""API routes for complaint management."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.security import require_permission
from src.api.schemas.complaint import ComplaintCreate, ComplaintListResponse, ComplaintResponse, ComplaintUpdate
from src.domain.models.complaint import Complaint
from src.domain.services.audit_service import record_audit_event

router = APIRouter(tags=["Complaints"])


@router.post("/", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
async def create_complaint(
    complaint_in: ComplaintCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Complaint:
    """
    Create a new complaint.

    Requires authentication and complaint:create permission.
    """
    # Check permission
    await require_permission("complaint:create", current_user, db)
    # Generate reference number: COMP-YYYY-NNNN
    year = datetime.now().year
    count_query = select(func.count()).select_from(Complaint)
    result = await db.execute(count_query)
    count = result.scalar() or 0
    ref_num = f"COMP-{year}-{count + 1:04d}"

    complaint = Complaint(
        **complaint_in.model_dump(),
        reference_number=ref_num,
    )

    db.add(complaint)
    await db.commit()
    await db.refresh(complaint)

    # Record audit event
    await record_audit_event(
        db=db,
        event_type="complaint.created",
        entity_type="complaint",
        entity_id=str(complaint.id),
        action="create",
        payload=complaint_in.model_dump(mode="json"),
        user_id=current_user.id,
    )

    return complaint


@router.get("/{complaint_id}", response_model=ComplaintResponse)
async def get_complaint(
    complaint_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Complaint:
    """
    Get a complaint by ID.

    Requires authentication.
    """
    result = await db.execute(select(Complaint).where(Complaint.id == complaint_id))
    complaint = result.scalar_one_or_none()

    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint with ID {complaint_id} not found",
        )

    return complaint


@router.get("/", response_model=ComplaintListResponse)
async def list_complaints(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = None,
) -> ComplaintListResponse:
    """
    List all complaints with deterministic ordering.

    Ordering: received_date DESC, id ASC
    Requires authentication.
    """
    query = select(Complaint)

    if status_filter:
        query = query.where(Complaint.status == status_filter)

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Deterministic ordering: received_date DESC, id ASC
    query = query.order_by(Complaint.received_date.desc(), Complaint.id.asc())

    # Pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    complaints = result.scalars().all()

    import math

    return ComplaintListResponse(
        items=[ComplaintResponse.model_validate(c) for c in complaints],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.patch("/{complaint_id}", response_model=ComplaintResponse)
async def update_complaint(
    complaint_id: int,
    complaint_in: ComplaintUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Complaint:
    """
    Partial update of a complaint.

    Requires authentication.
    """
    result = await db.execute(select(Complaint).where(Complaint.id == complaint_id))
    complaint = result.scalar_one_or_none()

    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint with ID {complaint_id} not found",
        )

    update_data = complaint_in.model_dump(exclude_unset=True)
    old_status = complaint.status

    for field, value in update_data.items():
        setattr(complaint, field, value)

    await db.commit()
    await db.refresh(complaint)

    # Record audit event
    await record_audit_event(
        db=db,
        event_type="complaint.updated",
        entity_type="complaint",
        entity_id=str(complaint.id),
        action="update",
        payload={
            "updates": update_data,
            "old_status": old_status,
            "new_status": complaint.status,
        },
        user_id=current_user.id,
    )

    return complaint
