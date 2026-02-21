"""API routes for complaint management."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.api.schemas.complaint import (
    ComplaintCreate,
    ComplaintInvestigationsResponse,
    ComplaintListResponse,
    ComplaintResponse,
    ComplaintUpdate,
)
from src.api.schemas.error_codes import ErrorCode
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.complaint import Complaint
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter(tags=["Complaints"])


@router.post("/", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
async def create_complaint(
    complaint_in: ComplaintCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> Complaint:
    """
    Create a new complaint.

    Requires authentication.

    Idempotency:
    - If external_ref is provided and already exists, returns 409 Conflict
    - This enables ETL/external systems to safely retry imports
    """
    _span = tracer.start_span("create_complaint") if tracer else None
    if _span:
        _span.set_attribute("tenant_id", str(current_user.tenant_id or 0))
    external_ref = complaint_in.external_ref
    if external_ref:
        existing_query = select(Complaint).where(Complaint.external_ref == external_ref)
        existing_result = await db.execute(existing_query)
        existing = existing_result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "DUPLICATE_EXTERNAL_REF",
                    "message": f"Complaint with external_ref '{external_ref}' already exists",
                    "existing_id": existing.id,
                    "existing_reference_number": existing.reference_number,
                },
            )

    ref_num = await ReferenceNumberService.generate(db, "complaint", Complaint)

    complaint = Complaint(
        **complaint_in.model_dump(),
        reference_number=ref_num,
        tenant_id=current_user.tenant_id,
    )

    db.add(complaint)
    await db.commit()
    await db.refresh(complaint)
    await invalidate_tenant_cache(current_user.tenant_id, "complaints")
    track_metric("complaints.created")
    if _span:
        _span.end()

    await record_audit_event(
        db=db,
        event_type="complaint.created",
        entity_type="complaint",
        entity_id=str(complaint.id),
        action="create",
        payload=complaint_in.model_dump(mode="json"),
        user_id=current_user.id,
        request_id=request_id,
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
    return await get_or_404(db, Complaint, complaint_id, tenant_id=current_user.tenant_id)


@router.get("/", response_model=ComplaintListResponse)
async def list_complaints(
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = None,
    complainant_email: Optional[str] = Query(None, description="Filter by complainant email"),
) -> ComplaintListResponse:
    """
    List all complaints with deterministic ordering.

    Ordering: received_date DESC, id ASC

    Requires authentication. Users can only filter by their own email
    unless they have admin permissions.
    """
    import logging

    logger = logging.getLogger(__name__)

    if complainant_email:
        user_email = getattr(current_user, "email", None)
        has_view_all = (
            current_user.has_permission("complaint:view_all") if hasattr(current_user, "has_permission") else False
        )
        is_superuser = getattr(current_user, "is_superuser", False)

        if not has_view_all and not is_superuser:
            if user_email and complainant_email.lower() != user_email.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=ErrorCode.PERMISSION_DENIED,
                )

        await record_audit_event(
            db=db,
            event_type="complaint.list_filtered",
            entity_type="complaint",
            entity_id="*",
            action="list",
            description="Complaint list accessed with email filter",
            payload={
                "filter_type": "complainant_email",
                "is_own_email": user_email and complainant_email.lower() == user_email.lower(),
                "has_view_all_permission": has_view_all,
                "is_superuser": is_superuser,
            },
            user_id=current_user.id,
            request_id=request_id,
        )

    try:
        query = select(Complaint).options(selectinload(Complaint.actions)).where(Complaint.tenant_id == current_user.tenant_id)

        if complainant_email:
            query = query.where(Complaint.complainant_email == complainant_email)
        if status_filter:
            query = query.where(Complaint.status == status_filter)

        query = query.order_by(Complaint.received_date.desc(), Complaint.id.asc())
        params = PaginationParams(page=page, page_size=page_size)
        paginated = await paginate(db, query, params)

        return ComplaintListResponse(
            items=[ComplaintResponse.model_validate(c) for c in paginated.items],
            total=paginated.total,
            page=paginated.page,
            page_size=paginated.page_size,
            pages=paginated.pages,
        )
    except SQLAlchemyError as e:
        error_str = str(e).lower()
        logger.exception(f"Error listing complaints: {e}")

        column_errors = ["email", "column", "does not exist", "unknown column", "programmingerror", "relation"]
        is_column_error = any(err in error_str for err in column_errors)

        if is_column_error:
            logger.warning("Database column missing - migration may be pending")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=ErrorCode.INTERNAL_ERROR,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorCode.INTERNAL_ERROR,
        )


@router.patch("/{complaint_id}", response_model=ComplaintResponse)
async def update_complaint(
    complaint_id: int,
    complaint_in: ComplaintUpdate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> Complaint:
    """
    Partial update of a complaint.

    Requires authentication.
    """
    complaint = await get_or_404(db, Complaint, complaint_id, tenant_id=current_user.tenant_id)
    old_status = complaint.status
    update_data = apply_updates(complaint, complaint_in, set_updated_at=False)

    await db.commit()
    await db.refresh(complaint)
    await invalidate_tenant_cache(current_user.tenant_id, "complaints")

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
        request_id=request_id,
    )

    return complaint


@router.get("/{complaint_id}/investigations", response_model=ComplaintInvestigationsResponse)
async def list_complaint_investigations(
    complaint_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page (1-100)"),
):
    """
    List investigations for a specific complaint (paginated).

    Requires authentication.
    Returns investigations assigned to this complaint with pagination.
    Deterministic ordering: created_at DESC, id ASC.
    """
    from src.api.schemas.investigation import InvestigationRunResponse
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun

    await get_or_404(db, Complaint, complaint_id, tenant_id=current_user.tenant_id)

    query = (
        select(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.COMPLAINT,
            InvestigationRun.assigned_entity_id == complaint_id,
        )
        .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
    )
    params = PaginationParams(page=page, page_size=page_size)
    paginated = await paginate(db, query, params)

    return {
        "items": [InvestigationRunResponse.model_validate(inv) for inv in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
    }
