"""Investigation Run API routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.investigation import (
    AutosaveRequest,
    ClosureValidationResponse,
    CommentCreateRequest,
    CommentListResponse,
    CommentResponse,
    CreateFromRecordRequest,
    CustomerPackGeneratedResponse,
    CustomerPackSummaryResponse,
    InvestigationRunCreate,
    InvestigationRunListResponse,
    InvestigationRunResponse,
    InvestigationRunUpdate,
    PackListResponse,
    SourceRecordItem,
    SourceRecordsResponse,
    TimelineEventResponse,
    TimelineListResponse,
)
from src.api.utils.pagination import PaginationParams
from src.domain.exceptions import AuthorizationError
from src.domain.models.user import User
from src.domain.services.investigation_service import ClosureReasonCode, InvestigationService

# Re-export for backward compatibility with tests
_user_can_access_investigation = InvestigationService.user_can_access_investigation

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter()


@router.post("/", response_model=InvestigationRunResponse, status_code=status.HTTP_201_CREATED)
async def create_investigation(
    investigation_data: InvestigationRunCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:create"))],
):
    """Create a new investigation run.

    Requires authentication and validates that:
    - Template exists
    - Assigned entity type is valid
    - Assigned entity exists

    Returns 400 for invalid entity type, 404 for missing template or entity.
    """
    _span = tracer.start_span("create_investigation") if tracer else None
    if _span:
        _span.set_attribute("tenant_id", str(current_user.tenant_id or 0))
    try:
        return await InvestigationService.create_new_investigation(
            db,
            template_id=investigation_data.template_id,
            assigned_entity_type=investigation_data.assigned_entity_type,
            assigned_entity_id=investigation_data.assigned_entity_id,
            title=investigation_data.title,
            description=investigation_data.description,
            status=investigation_data.status,
            data=investigation_data.data,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
        )
    finally:
        if _span:
            _span.end()


@router.get("/", response_model=InvestigationRunListResponse)
async def list_investigations(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[int] = Query(None, description="Filter by entity ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
):
    """List investigation runs with pagination.

    Returns investigations in deterministic order (created_at DESC, id ASC).
    Can filter by entity_type, entity_id, and status.
    """
    result = await InvestigationService.list_investigations(
        db,
        tenant_id=current_user.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        status_filter=status_filter,
        page=params.page,
        page_size=params.page_size,
    )
    return result


@router.get("/source-records", response_model=SourceRecordsResponse)
async def list_source_records(
    db: DbSession,
    current_user: CurrentUser,
    source_type: str = Query(
        ..., description="Source type (near_miss, road_traffic_collision, complaint, reporting_incident)"
    ),
    q: Optional[str] = Query(None, description="Search query (searches title, reference)"),
    params: PaginationParams = Depends(),
):
    """List source records available for investigation creation.

    Returns records of the specified type with investigation status.
    Records that already have an investigation are marked with investigation_id.
    """
    result = await InvestigationService.list_source_records(
        db,
        source_type=source_type,
        tenant_id=current_user.tenant_id,
        search_query=q,
        page=params.page,
        page_size=params.page_size,
    )
    return SourceRecordsResponse(
        items=[
            SourceRecordItem(
                source_id=item.source_id,
                display_label=item.display_label,
                reference_number=item.reference_number,
                status=item.status,
                created_at=item.created_at,
                investigation_id=item.investigation_id,
                investigation_reference=item.investigation_reference,
            )
            for item in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        pages=result.pages,
        source_type=result.source_type,
    )


@router.get("/{investigation_id}", response_model=InvestigationRunResponse)
async def get_investigation(
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific investigation run by ID."""
    return await InvestigationService.get_investigation(db, investigation_id, current_user.tenant_id)


@router.patch("/{investigation_id}", response_model=InvestigationRunResponse)
async def update_investigation(
    investigation_id: int,
    investigation_data: InvestigationRunUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Update an investigation run.

    Only provided fields will be updated (partial update).
    Can update RCA section fields via the data field.
    """
    updates = investigation_data.model_dump(exclude_unset=True)
    return await InvestigationService.update_investigation(
        db,
        investigation_id=investigation_id,
        updates=updates,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )


# === Stage 2 Endpoints ===


@router.post("/from-record", response_model=InvestigationRunResponse, status_code=status.HTTP_201_CREATED)
async def create_investigation_from_record(
    request_body: CreateFromRecordRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:create"))],
):
    """Create an investigation from a source record (Near Miss, Complaint, RTA).

    Performs deterministic prefill using Mapping Contract v1:
    - Creates immutable source snapshot
    - Maps fields with explicit reason codes
    - Links existing evidence assets
    - Determines investigation level from source severity

    Returns:
    - 201: Created investigation with prefilled data
    - 400: VALIDATION_ERROR - Invalid request body
    - 404: SOURCE_NOT_FOUND - Source record doesn't exist
    - 409: INV_ALREADY_EXISTS - Investigation already exists for this source
    """
    return await InvestigationService.create_from_record(
        db,
        source_type=request_body.source_type,
        source_id=request_body.source_id,
        title=request_body.title,
        template_id=request_body.template_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )


@router.patch("/{investigation_id}/autosave", response_model=InvestigationRunResponse)
async def autosave_investigation(
    investigation_id: int,
    payload: AutosaveRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Autosave investigation data with optimistic locking.

    Uses version field to prevent concurrent edit conflicts.
    Returns 409 Conflict if version mismatch.
    """
    return await InvestigationService.autosave(
        db,
        investigation_id=investigation_id,
        data=payload.data,
        version=payload.version,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )


@router.post("/{investigation_id}/comments", status_code=status.HTTP_201_CREATED, response_model=CommentResponse)
async def add_comment(
    investigation_id: int,
    request_body: CommentCreateRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:create"))],
):
    """Add an internal comment to an investigation.

    Comments are INTERNAL ONLY - never included in customer packs.
    Can be attached to specific sections/fields and support threading.
    """
    comment = await InvestigationService.add_comment(
        db,
        investigation_id=investigation_id,
        body=request_body.body,
        section_id=request_body.section_id,
        field_id=request_body.field_id,
        parent_comment_id=request_body.parent_comment_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    return {
        "id": comment.id,
        "investigation_id": comment.investigation_id,
        "content": comment.content,
        "section_id": comment.section_id,
        "field_id": comment.field_id,
        "parent_comment_id": comment.parent_comment_id,
        "author_id": comment.author_id,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


@router.post("/{investigation_id}/approve", response_model=InvestigationRunResponse)
async def approve_investigation(
    investigation_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
    approved: bool = True,
    rejection_reason: Optional[str] = None,
):
    """Approve or reject an investigation.

    Moves investigation to COMPLETED (approved) or back to IN_PROGRESS (rejected).
    """
    return await InvestigationService.approve_or_reject(
        db,
        investigation_id=investigation_id,
        approved=approved,
        rejection_reason=rejection_reason,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )


@router.post("/{investigation_id}/customer-pack", response_model=CustomerPackGeneratedResponse)
async def generate_customer_pack(
    investigation_id: int,
    audience: str,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:create"))],
):
    """Generate a customer pack with audience-specific redaction.

    Audience options:
    - internal_customer: identities retained, internal comments excluded
    - external_customer: identities redacted, only external-allowed evidence

    Returns the generated pack with redaction log.
    """
    result = await InvestigationService.generate_pack_for_investigation(
        db,
        investigation_id=investigation_id,
        audience=audience,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    pack = result.pack
    return {
        "pack_id": pack.id,
        "pack_uuid": pack.pack_uuid,
        "audience": pack.audience.value,
        "investigation_id": investigation_id,
        "investigation_reference": result.investigation_reference,
        "generated_at": pack.created_at.isoformat() if pack.created_at else None,
        "content": pack.content,
        "redaction_log": pack.redaction_log,
        "included_assets": pack.included_assets,
        "checksum": pack.checksum_sha256,
    }


# =============================================================================
# Stage 1: Timeline, Comments, Packs List, Closure Validation Endpoints
# =============================================================================


@router.get("/{investigation_id}/timeline", response_model=TimelineListResponse)
async def get_investigation_timeline(
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
):
    """Get timeline of revision events for an investigation.

    Returns events in deterministic order: created_at DESC, then id DESC.
    Supports filtering by event_type and pagination.
    """
    result = await InvestigationService.get_timeline(
        db,
        investigation_id=investigation_id,
        tenant_id=current_user.tenant_id,
        event_type=event_type,
        page=params.page,
        page_size=params.page_size,
    )
    return TimelineListResponse(
        items=[
            TimelineEventResponse(
                id=event.id,
                created_at=event.created_at,
                event_type=event.event_type,
                field_path=event.field_path,
                old_value=event.old_value,
                new_value=event.new_value,
                actor_id=event.actor_id,
                version=event.version,
                event_metadata=event.event_metadata,
            )
            for event in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        investigation_id=investigation_id,
    )


@router.get("/{investigation_id}/comments", response_model=CommentListResponse)
async def get_investigation_comments(
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    include_deleted: bool = Query(False, description="Include soft-deleted comments (admin only)"),
):
    """Get list of comments on an investigation.

    Returns comments in deterministic order: created_at DESC, id DESC.
    Excludes soft-deleted comments by default.

    Security:
    - include_deleted=true requires superuser or 'investigations:comments:read_deleted' permission
    """
    if include_deleted:
        has_deleted_access = current_user.is_superuser or current_user.has_permission(
            "investigations:comments:read_deleted"
        )
        if not has_deleted_access:
            raise AuthorizationError(
                "Permission 'investigations:comments:read_deleted' required to view deleted comments",
            )

    result = await InvestigationService.get_comments_list(
        db,
        investigation_id=investigation_id,
        tenant_id=current_user.tenant_id,
        include_deleted=include_deleted,
        page=params.page,
        page_size=params.page_size,
    )
    return CommentListResponse(
        items=[
            CommentResponse(
                id=comment.id,
                created_at=comment.created_at,
                content=comment.content,
                author_id=comment.author_id,
                section_id=comment.section_id,
                field_id=comment.field_id,
                parent_comment_id=comment.parent_comment_id,
            )
            for comment in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        investigation_id=investigation_id,
    )


@router.get("/{investigation_id}/packs", response_model=PackListResponse)
async def get_investigation_packs(
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
):
    """Get list of customer packs generated for an investigation.

    Returns pack summaries (without full content) in deterministic order:
    created_at DESC, id DESC. Full pack content should be fetched separately.
    """
    result = await InvestigationService.get_packs_list(
        db,
        investigation_id=investigation_id,
        tenant_id=current_user.tenant_id,
        page=params.page,
        page_size=params.page_size,
    )
    return PackListResponse(
        items=[
            CustomerPackSummaryResponse(
                id=pack.id,
                created_at=pack.created_at,
                pack_uuid=pack.pack_uuid,
                audience=pack.audience.value,
                checksum_sha256=pack.checksum_sha256,
                generated_by_id=pack.generated_by_id,
                expires_at=pack.expires_at,
            )
            for pack in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        investigation_id=investigation_id,
    )


@router.get("/{investigation_id}/closure-validation", response_model=ClosureValidationResponse)
async def validate_investigation_closure(
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Validate whether an investigation can be closed.

    Performs deterministic, template-driven validation:
    - Checks investigation level (LOW/MEDIUM/HIGH)
    - Validates required sections based on template structure
    - Validates required fields within each section
    - Returns specific reason codes for any blockers

    Returns:
        status: "OK" if closeable, "BLOCKED" if not
        reason_codes: List of blocking reasons (stable strings)
        missing_fields: List of field paths that are missing
    """
    result = await InvestigationService.validate_closure(
        db,
        investigation_id=investigation_id,
        tenant_id=current_user.tenant_id,
    )
    return ClosureValidationResponse(
        status=result.status,
        reason_codes=result.reason_codes,
        missing_fields=result.missing_fields,
        checked_at_utc=result.checked_at_utc,
        investigation_id=result.investigation_id,
        investigation_level=result.investigation_level,
    )
