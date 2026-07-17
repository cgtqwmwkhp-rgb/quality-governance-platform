"""API routes for complaint management."""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.dependencies.request_context import get_request_id
from src.api.routes._runner_sheet import assert_can_delete_runner_sheet_entry
from src.api.schemas.complaint import ComplaintCreate, ComplaintListResponse, ComplaintResponse, ComplaintUpdate
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.running_sheet import RunningSheetEntryCreate, RunningSheetEntryResponse
from src.api.utils.errors import api_error
from src.api.utils.tenant import apply_tenant_filter, require_tenant_id
from src.domain.exceptions import AuthorizationError, BadRequestError, ConflictError, NotFoundError
from src.domain.models.complaint import Complaint, ComplaintRunningSheetEntry
from src.domain.models.user import User
from src.domain.services.audit_service import record_audit_event
from src.domain.services.notification_service import NotificationService
from src.infrastructure.monitoring.azure_monitor import track_metric
from src.services.complaint_service import ComplaintService

router = APIRouter(tags=["Complaints"])
logger = logging.getLogger(__name__)


async def _validate_case_owner(db: DbSession, owner_id: int, tenant_id: int | None) -> User:
    """Ensure owner_id refers to an active user in the tenant."""
    result = await db.execute(select(User).where(User.id == owner_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise BadRequestError(f"No active user found with id {owner_id}")
    if tenant_id is not None and user.tenant_id != tenant_id:
        raise BadRequestError(f"User {owner_id} is not in this tenant")
    return user


async def _notify_case_owner_assignment(
    db: DbSession,
    *,
    entity_type: str,
    entity_id: int,
    assigned_to_user_id: int,
    assigned_by_user_id: int,
    reference: str,
) -> None:
    """In-app assignment notify; never rewrite NotificationService — call site only."""
    try:
        service = NotificationService(db)
        await service.create_assignment(
            entity_type=entity_type,
            entity_id=str(entity_id),
            assigned_to_user_id=assigned_to_user_id,
            assigned_by_user_id=assigned_by_user_id,
            notes=f"You have been assigned as case owner for {reference}",
            priority="high",
        )
    except Exception:
        logger.exception(
            "Failed to notify case owner assignment for %s %s",
            entity_type,
            entity_id,
        )


async def _trigger_operational_standards_assess(
    db: DbSession,
    complaint: Complaint,
    current_user: User,
) -> None:
    """Fire-and-forget standards assessment; never breaks complaint save."""
    tenant_id = complaint.tenant_id or current_user.tenant_id
    if tenant_id is None:
        logger.warning(
            "Skipping operational standards assess for complaint %s; no tenant_id",
            complaint.id,
        )
        return
    try:
        from src.domain.services.governed_knowledge_service import governed_knowledge_service

        content = f"{complaint.title}\n\n{complaint.description}"
        async with db.begin_nested():
            await governed_knowledge_service.assess_operational_entity(
                db,
                entity_type="complaint",
                entity_id=str(complaint.id),
                content=content,
                tenant_id=tenant_id,
                user=current_user,
            )
    except Exception:
        logger.warning(
            "Operational standards assess failed for complaint %s; save continues",
            complaint.id,
            exc_info=True,
        )


@router.post("/", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
async def create_complaint(
    complaint_in: ComplaintCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("complaint:create"))],
    request_id: str = Depends(get_request_id),
) -> Complaint:
    """
    Create a new complaint.

    Requires authentication. Delegates to ComplaintService for audit trail,
    cache invalidation, and telemetry.
    """
    svc = ComplaintService(db)
    try:
        complaint = await svc.create_complaint(
            complaint_data=complaint_in,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
        )
        track_metric("complaints.created")
        await _trigger_operational_standards_assess(db, complaint, current_user)
        return complaint
    except ValueError as e:
        msg = str(e)
        if "DUPLICATE_EXTERNAL_REF" in msg:
            parts = msg.split(":")
            existing_id = int(parts[1]) if len(parts) > 1 else None
            raise ConflictError(
                f"Complaint with external_ref '{complaint_in.external_ref}' already exists",
                details={"existing_id": existing_id, "external_ref": complaint_in.external_ref},
            )
        raise BadRequestError(msg)


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
    query = select(Complaint).where(Complaint.id == complaint_id)
    if not current_user.is_superuser:
        query = query.where(Complaint.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    complaint = result.scalar_one_or_none()

    if not complaint:
        raise NotFoundError(f"Complaint with ID {complaint_id} not found")

    return complaint


@router.get("/", response_model=ComplaintListResponse)
async def list_complaints(
    db: DbSession,
    current_user: CurrentUser,  # SECURITY FIX: Always require authentication
    request_id: str = Depends(get_request_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    complainant_email: Optional[str] = Query(None, description="Filter by complainant email"),
    owner: Optional[str] = Query(
        None,
        description="Filter by case owner: 'unassigned' for intakes with no owner_id",
    ),
) -> ComplaintListResponse:
    """
    List all complaints with deterministic ordering.

    Ordering: received_date DESC, id ASC

    Requires authentication. Users can only filter by their own email
    unless they have admin permissions.
    """
    import logging
    import math

    logger = logging.getLogger(__name__)

    if owner is not None and owner != "unassigned":
        raise BadRequestError("Invalid owner filter. Supported value: unassigned")

    # SECURITY FIX: If filtering by email, enforce that users can only access their own data
    # unless they have admin/view-all permissions
    if complainant_email:
        user_email = getattr(current_user, "email", None)
        has_view_all = (
            current_user.has_permission("complaint:view_all") if hasattr(current_user, "has_permission") else False
        )
        is_superuser = getattr(current_user, "is_superuser", False)

        if not has_view_all and not is_superuser:
            # Non-admin users can only filter by their own email
            if user_email and complainant_email.lower() != user_email.lower():
                raise AuthorizationError("You can only view your own complaints")

        # AUDIT: Log email filter usage for security monitoring
        # Note: We log the filter type but NOT the raw email (privacy compliance)
        await record_audit_event(
            db=db,
            event_type="complaint.list_filtered",
            entity_type="complaint",
            entity_id="*",  # Wildcard - listing operation
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
        query = select(Complaint)

        if not current_user.is_superuser:
            tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
            query = apply_tenant_filter(query, Complaint, tenant_id)

        if complainant_email:
            query = query.where(Complaint.complainant_email == complainant_email)
        if status_filter:
            query = query.where(Complaint.status == status_filter)
        if owner == "unassigned":
            query = query.where(Complaint.owner_id.is_(None))

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

        return ComplaintListResponse(
            items=[ComplaintResponse.model_validate(c) for c in complaints],
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 1,
        )
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e).lower()
        logger.error(f"Error listing complaints: {e}", exc_info=True)

        column_errors = [
            "email",
            "column",
            "does not exist",
            "unknown column",
            "programmingerror",
            "relation",
        ]
        is_column_error = any(err in error_str for err in column_errors)

        if is_column_error:
            logger.warning("Database column missing - migration may be pending")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database migration pending. Please wait for migrations to complete.",
            )
        logger.exception("Error listing complaints")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to list complaints at this time.",
        )


@router.patch("/{complaint_id}", response_model=ComplaintResponse)
async def update_complaint(
    complaint_id: int,
    complaint_in: ComplaintUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("complaint:update"))],
    request_id: str = Depends(get_request_id),
) -> Complaint:
    """
    Partial update of a complaint.

    Requires authentication. StateTransitionError is caught by the
    global domain error handler and returned as a structured JSON response.
    """
    updates = complaint_in.model_dump(exclude_unset=True)
    if "owner_id" in updates and updates["owner_id"] is not None:
        await _validate_case_owner(db, updates["owner_id"], current_user.tenant_id)

    svc = ComplaintService(db)
    try:
        existing = await svc.get_complaint(
            complaint_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
        previous_owner_id = existing.owner_id

        complaint = await svc.update_complaint(
            complaint_id,
            complaint_in,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
            skip_tenant_check=current_user.is_superuser,
        )
        await _trigger_operational_standards_assess(db, complaint, current_user)

        if "owner_id" in updates and updates["owner_id"] is not None and updates["owner_id"] != previous_owner_id:
            await _notify_case_owner_assignment(
                db,
                entity_type="complaint",
                entity_id=complaint.id,
                assigned_to_user_id=updates["owner_id"],
                assigned_by_user_id=current_user.id,
                reference=complaint.reference_number,
            )
            try:
                await db.refresh(complaint)
            except Exception:
                logger.warning(
                    "Refresh after owner assign failed for complaint %s; re-fetching",
                    complaint_id,
                    exc_info=True,
                )
                complaint = await svc.get_complaint(
                    complaint_id,
                    current_user.tenant_id,
                    skip_tenant_check=current_user.is_superuser,
                )
        return complaint
    except LookupError:
        raise NotFoundError(f"Complaint {complaint_id} not found")


@router.get("/{complaint_id}/investigations", response_model=dict)
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
    from math import ceil

    from src.api.schemas.investigation import InvestigationRunResponse
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun

    query = select(Complaint).where(Complaint.id == complaint_id)
    if not current_user.is_superuser:
        query = query.where(Complaint.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    complaint = result.scalar_one_or_none()

    if not complaint:
        raise NotFoundError(f"Complaint {complaint_id} not found")

    # Get total count
    count_query = (
        select(func.count())
        .select_from(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.COMPLAINT,
            InvestigationRun.assigned_entity_id == complaint_id,
        )
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Calculate total pages
    total_pages = ceil(total / page_size) if total > 0 else 1

    # Get paginated results
    inv_query = (
        select(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.COMPLAINT,
            InvestigationRun.assigned_entity_id == complaint_id,
        )
        .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(inv_query)
    investigations = result.scalars().all()

    return {
        "items": [InvestigationRunResponse.model_validate(inv) for inv in investigations],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": total_pages,
    }


@router.get("/{complaint_id}/running-sheet", response_model=list[RunningSheetEntryResponse])
async def list_complaint_running_sheet_entries(
    complaint_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List complaint runner-sheet entries, newest first."""
    svc = ComplaintService(db)
    try:
        complaint = await svc.get_complaint(
            complaint_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise NotFoundError(f"Complaint {complaint_id} not found")

    query = select(ComplaintRunningSheetEntry).where(ComplaintRunningSheetEntry.complaint_id == complaint_id)
    if complaint.tenant_id is None:
        query = query.where(ComplaintRunningSheetEntry.tenant_id.is_(None))
    else:
        query = query.where(ComplaintRunningSheetEntry.tenant_id == complaint.tenant_id)

    result = await db.execute(
        query.order_by(ComplaintRunningSheetEntry.created_at.desc(), ComplaintRunningSheetEntry.id.asc())
    )
    return result.scalars().all()


@router.post(
    "/{complaint_id}/running-sheet",
    response_model=RunningSheetEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_complaint_running_sheet_entry(
    complaint_id: int,
    payload: RunningSheetEntryCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Add a timestamped entry to the complaint runner sheet."""
    svc = ComplaintService(db)
    try:
        complaint = await svc.get_complaint(
            complaint_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise NotFoundError(f"Complaint {complaint_id} not found")

    entry = ComplaintRunningSheetEntry(
        tenant_id=complaint.tenant_id,
        complaint_id=complaint.id,
        content=payload.content,
        entry_type=payload.entry_type.value,
        author_id=current_user.id,
        author_email=current_user.email,
    )
    db.add(entry)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="complaint.runner_sheet_entry.created",
        entity_type="complaint",
        entity_id=str(complaint.id),
        action="create",
        description=f"Runner-sheet entry added to complaint {complaint.reference_number}",
        payload={"entry_id": entry.id, "entry_type": entry.entry_type},
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{complaint_id}/running-sheet/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_complaint_running_sheet_entry(
    complaint_id: int,
    entry_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> None:
    """Delete a complaint runner-sheet entry."""
    svc = ComplaintService(db)
    try:
        complaint = await svc.get_complaint(
            complaint_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise NotFoundError(f"Complaint {complaint_id} not found")

    result = await db.execute(
        select(ComplaintRunningSheetEntry).where(
            ComplaintRunningSheetEntry.id == entry_id,
            ComplaintRunningSheetEntry.complaint_id == complaint_id,
            ComplaintRunningSheetEntry.tenant_id == complaint.tenant_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise NotFoundError("Runner-sheet entry not found")

    assert_can_delete_runner_sheet_entry(current_user, entry.author_id, "complaint")

    await record_audit_event(
        db=db,
        event_type="complaint.runner_sheet_entry.deleted",
        entity_type="complaint",
        entity_id=str(complaint.id),
        action="delete",
        description=f"Runner-sheet entry deleted from complaint {complaint.reference_number}",
        payload={"entry_id": entry.id, "entry_type": entry.entry_type},
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.delete(entry)
    await db.commit()
