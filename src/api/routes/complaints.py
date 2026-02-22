"""API routes for complaint management — thin controller layer."""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.domain.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.dependencies.request_context import get_request_id
from src.api.schemas.complaint import (
    ComplaintCreate,
    ComplaintInvestigationsResponse,
    ComplaintListResponse,
    ComplaintResponse,
    ComplaintUpdate,
)
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.investigation import InvestigationRunResponse
from src.api.utils.pagination import PaginationParams
from src.domain.models.user import User
from src.domain.services.audit_service import record_audit_event
from src.domain.services.complaint_service import ComplaintService

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Complaints"])


@router.post("/", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
async def create_complaint(
    complaint_in: ComplaintCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("complaint:create"))],
    request_id: str = Depends(get_request_id),
) -> ComplaintResponse:
    """Create a new complaint."""
    _span = tracer.start_span("create_complaint") if tracer else None
    if _span:
        _span.set_attribute("tenant_id", str(current_user.tenant_id or 0))

    service = ComplaintService(db)
    try:
        complaint = await service.create_complaint(
            complaint_data=complaint_in,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
        )
    except ValueError as e:
        msg = str(e)
        if msg.startswith("DUPLICATE_EXTERNAL_REF:"):
            parts = msg.split(":")
            raise ConflictError(
                f"Complaint with external_ref '{complaint_in.external_ref}' already exists",
                code="DUPLICATE_EXTERNAL_REF",
                details={
                    "existing_id": int(parts[1]),
                    "existing_reference_number": parts[2],
                },
            )
        raise ValidationError(str(e))
    finally:
        if _span:
            _span.end()

    return ComplaintResponse.model_validate(complaint)


@router.get("/{complaint_id}", response_model=ComplaintResponse)
async def get_complaint(
    complaint_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ComplaintResponse:
    """Get a complaint by ID."""
    service = ComplaintService(db)
    try:
        complaint = await service.get_complaint(complaint_id, current_user.tenant_id)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return ComplaintResponse.model_validate(complaint)


@router.get("/", response_model=ComplaintListResponse)
async def list_complaints(
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
    params: PaginationParams = Depends(),
    status_filter: Optional[str] = None,
    complainant_email: Optional[str] = Query(None, description="Filter by complainant email"),
) -> ComplaintListResponse:
    """List all complaints with deterministic ordering."""
    service = ComplaintService(db)

    if complainant_email:
        user_email = getattr(current_user, "email", None)
        has_view_all = (
            current_user.has_permission("complaint:view_all") if hasattr(current_user, "has_permission") else False
        )
        is_superuser = getattr(current_user, "is_superuser", False)

        if not service.check_complainant_email_access(complainant_email, user_email, has_view_all, is_superuser):
            raise AuthorizationError(ErrorCode.PERMISSION_DENIED)

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
        paginated = await service.list_complaints(
            tenant_id=current_user.tenant_id,
            params=params,
            status_filter=status_filter,
            complainant_email=complainant_email,
        )
        return ComplaintListResponse(
            items=[ComplaintResponse.model_validate(c) for c in paginated.items],
            total=paginated.total,
            page=paginated.page,
            page_size=paginated.page_size,
            pages=paginated.pages,
        )
    except SQLAlchemyError as e:
        error_str = str(e).lower()
        logger.exception(
            "Error listing complaints [request_id=%s]: %s",
            request_id,
            type(e).__name__,
        )
        column_errors = [
            "email",
            "column",
            "does not exist",
            "unknown column",
            "programmingerror",
            "relation",
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


@router.patch("/{complaint_id}", response_model=ComplaintResponse)
async def update_complaint(
    complaint_id: int,
    complaint_in: ComplaintUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("complaint:update"))],
    request_id: str = Depends(get_request_id),
) -> ComplaintResponse:
    """Partial update of a complaint."""
    service = ComplaintService(db)
    try:
        complaint = await service.update_complaint(
            complaint_id,
            complaint_in,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
        )
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return ComplaintResponse.model_validate(complaint)


@router.get("/{complaint_id}/investigations", response_model=ComplaintInvestigationsResponse)
async def list_complaint_investigations(
    complaint_id: int,
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
):
    """List investigations for a specific complaint (paginated)."""
    service = ComplaintService(db)
    try:
        paginated = await service.list_complaint_investigations(complaint_id, current_user.tenant_id, params)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return {
        "items": [InvestigationRunResponse.model_validate(inv) for inv in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
    }
