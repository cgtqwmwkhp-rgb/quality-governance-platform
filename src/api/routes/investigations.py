"""Investigation Run API routes."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.investigation import (
    AutosaveRequest,
    ClosureValidationResponse,
    CommentCreateRequest,
    CommentListResponse,
    CommentResponse,
    CreateFromRecordRequest,
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
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None
from src.domain.models.investigation import (
    AssignedEntityType,
    InvestigationComment,
    InvestigationCustomerPack,
    InvestigationRevisionEvent,
    InvestigationRun,
    InvestigationStatus,
    InvestigationTemplate,
)

router = APIRouter()


async def validate_assigned_entity(
    entity_type: str,
    entity_id: int,
    db: AsyncSession,
    request_id: str,
    tenant_id: int | None = None,
) -> None:
    """Validate that the assigned entity exists.

    Raises HTTPException with canonical envelope if entity doesn't exist.
    """
    # Map entity type to model
    entity_models = {
        AssignedEntityType.ROAD_TRAFFIC_COLLISION.value: "src.domain.models.rta:RoadTrafficCollision",
        AssignedEntityType.REPORTING_INCIDENT.value: "src.domain.models.incident:Incident",
        AssignedEntityType.COMPLAINT.value: "src.domain.models.complaint:Complaint",
        AssignedEntityType.NEAR_MISS.value: "src.domain.models.near_miss:NearMiss",
    }

    if entity_type not in entity_models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_ENTITY_TYPE",
                "message": f"Invalid entity type: {entity_type}",
                "details": {
                    "entity_type": entity_type,
                    "valid_types": list(entity_models.keys()),
                },
                "request_id": request_id,
            },
        )

    # Import the model dynamically
    model_path = entity_models[entity_type]
    module_path, class_name = model_path.split(":")
    module = __import__(module_path, fromlist=[class_name])
    model_class = getattr(module, class_name)

    # Check if entity exists (tenant-scoped if model supports it)
    query = select(model_class).where(model_class.id == entity_id)
    if hasattr(model_class, "tenant_id") and tenant_id is not None:
        query = query.where(model_class.tenant_id == tenant_id)
    result = await db.execute(query)
    entity = result.scalar_one_or_none()

    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "ENTITY_NOT_FOUND",
                "message": f"{entity_type.replace('_', ' ').title()} with ID {entity_id} not found",
                "details": {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                },
                "request_id": request_id,
            },
        )


@router.post("/", response_model=InvestigationRunResponse, status_code=status.HTTP_201_CREATED)
async def create_investigation(
    investigation_data: InvestigationRunCreate,
    db: DbSession,
    current_user: CurrentUser,
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
    from src.domain.services.investigation_service import get_or_create_default_template

    request_id = "N/A"  # TODO: Get from request context

    template = await get_or_create_default_template(db, investigation_data.template_id, current_user.id)

    # Validate assigned entity exists
    await validate_assigned_entity(
        investigation_data.assigned_entity_type,
        investigation_data.assigned_entity_id,
        db,
        request_id,
        tenant_id=current_user.tenant_id,
    )

    # Generate reference number
    from src.domain.services.reference_number import ReferenceNumberService

    reference_number = await ReferenceNumberService.generate(db, "investigation", InvestigationRun)

    # Create investigation run
    investigation = InvestigationRun(
        template_id=investigation_data.template_id,
        assigned_entity_type=AssignedEntityType(investigation_data.assigned_entity_type),
        assigned_entity_id=investigation_data.assigned_entity_id,
        title=investigation_data.title,
        description=investigation_data.description,
        status=InvestigationStatus(investigation_data.status),
        data=investigation_data.data,
        reference_number=reference_number,
        tenant_id=current_user.tenant_id,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )

    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)
    await invalidate_tenant_cache(current_user.tenant_id, "investigations")
    track_metric("investigations.started", 1, {"tenant_id": str(current_user.tenant_id)})
    if _span:
        _span.end()

    return investigation


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
    request_id = "N/A"  # TODO: Get from request context

    # Build query
    query = (
        select(InvestigationRun)
        .options(
            selectinload(InvestigationRun.template),
            selectinload(InvestigationRun.comments),
            selectinload(InvestigationRun.actions),
        )
        .where(InvestigationRun.tenant_id == current_user.tenant_id)
    )

    # Apply filters
    if entity_type is not None:
        try:
            entity_type_enum = AssignedEntityType(entity_type)
            query = query.where(InvestigationRun.assigned_entity_type == entity_type_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_ENTITY_TYPE",
                    "message": f"Invalid entity type: {entity_type}",
                    "details": {
                        "entity_type": entity_type,
                        "valid_types": [e.value for e in AssignedEntityType],
                    },
                    "request_id": request_id,
                },
            )

    if entity_id is not None:
        query = query.where(InvestigationRun.assigned_entity_id == entity_id)

    if status_filter is not None:
        try:
            status_enum = InvestigationStatus(status_filter)
            query = query.where(InvestigationRun.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_STATUS",
                    "message": f"Invalid status: {status_filter}",
                    "details": {
                        "status": status_filter,
                        "valid_statuses": [s.value for s in InvestigationStatus],
                    },
                    "request_id": request_id,
                },
            )

    # Deterministic ordering: created_at DESC, id ASC
    query = query.order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())

    return await paginate(db, query, params)


@router.get("/{investigation_id}", response_model=InvestigationRunResponse)
async def get_investigation(
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific investigation run by ID."""
    return await get_or_404(db, InvestigationRun, investigation_id, tenant_id=current_user.tenant_id)


@router.patch("/{investigation_id}", response_model=InvestigationRunResponse)
async def update_investigation(
    investigation_id: int,
    investigation_data: InvestigationRunUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update an investigation run.

    Only provided fields will be updated (partial update).
    Can update RCA section fields via the data field.
    """
    investigation = await get_or_404(db, InvestigationRun, investigation_id, tenant_id=current_user.tenant_id)

    # setattr kept for status: requires enum conversion (str → InvestigationStatus)
    update_data = investigation_data.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] is not None:
        setattr(investigation, "status", InvestigationStatus(update_data["status"]))

    apply_updates(investigation, investigation_data, exclude={"status"})
    investigation.updated_by_id = current_user.id

    if investigation_data.status:
        from src.domain.services.investigation_service import InvestigationStatusManager

        InvestigationStatusManager.apply_status_timestamps(investigation, investigation_data.status)

    await db.commit()
    await db.refresh(investigation)
    await invalidate_tenant_cache(current_user.tenant_id, "investigations")

    return investigation


# === Stage 2 Endpoints ===


@router.post("/from-record", response_model=InvestigationRunResponse, status_code=status.HTTP_201_CREATED)
async def create_investigation_from_record(
    request_body: CreateFromRecordRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create an investigation from a source record (Near Miss, Complaint, RTA).

    Request Body (JSON):
    - source_type: near_miss, road_traffic_collision, complaint, reporting_incident
    - source_id: ID of the source record
    - title: Investigation title
    - template_id: Optional template ID (default: 1)

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

    Error Response Format:
    {
        "error_code": "ERROR_CODE",
        "message": "Human-readable message",
        "details": {...},
        "request_id": "..."
    }
    """
    from src.domain.services.investigation_service import InvestigationService, get_or_create_default_template
    from src.domain.services.reference_number import ReferenceNumberService

    request_id = "N/A"  # TODO: Get from request context

    # Extract values from request body
    source_type = request_body.source_type
    source_id = request_body.source_id
    title = request_body.title
    template_id = request_body.template_id

    # Parse source type enum
    source_type_enum = AssignedEntityType(source_type)

    # === DUPLICATE CHECK: Return 409 if investigation already exists ===
    existing_query = select(InvestigationRun).where(
        InvestigationRun.tenant_id == current_user.tenant_id,
        InvestigationRun.assigned_entity_type == source_type_enum,
        InvestigationRun.assigned_entity_id == source_id,
    )
    existing_result = await db.execute(existing_query)
    existing_investigation = existing_result.scalar_one_or_none()

    if existing_investigation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "INV_ALREADY_EXISTS",
                "message": f"An investigation already exists for this {source_type.replace('_', ' ')}",
                "details": {
                    "existing_investigation_id": existing_investigation.id,
                    "existing_reference_number": existing_investigation.reference_number,
                    "source_type": source_type,
                    "source_id": source_id,
                },
                "request_id": request_id,
            },
        )

    # Get source record
    record, error = await InvestigationService.get_source_record(db, source_type_enum, source_id)
    if error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "SOURCE_NOT_FOUND",
                "message": error,
                "details": {
                    "source_type": source_type,
                    "source_id": source_id,
                },
                "request_id": request_id,
            },
        )

    # Create source snapshot (immutable)
    source_snapshot = InvestigationService.create_source_snapshot(record, source_type_enum)

    # Map source to investigation data
    data, mapping_log, level = InvestigationService.map_source_to_investigation(record, source_type_enum)

    template = await get_or_create_default_template(db, template_id, current_user.id)

    # Generate reference number
    reference_number = await ReferenceNumberService.generate(db, "investigation", InvestigationRun)

    # Create investigation
    from src.domain.models.investigation import InvestigationLevel as InvLevel

    investigation = InvestigationRun(
        template_id=template.id,
        assigned_entity_type=source_type_enum,
        assigned_entity_id=source_id,
        title=title,
        status=InvestigationStatus.DRAFT,
        level=level,
        data=data,
        source_schema_version="1.0",
        source_snapshot=source_snapshot,
        mapping_log=mapping_log,
        version=1,
        reference_number=reference_number,
        tenant_id=current_user.tenant_id,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )

    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    # Create revision event
    await InvestigationService.create_revision_event(
        db=db,
        investigation=investigation,
        event_type="CREATED",
        actor_id=current_user.id,
        metadata={
            "source_type": source_type,
            "source_id": source_id,
            "mapping_log_count": len(mapping_log),
        },
    )

    # Link source evidence assets to investigation
    evidence_assets = await InvestigationService.get_source_evidence_assets(db, source_type_enum, source_id)
    for asset in evidence_assets:
        asset.linked_investigation_id = investigation.id

    await db.commit()
    await db.refresh(investigation)

    return investigation


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

    Query Parameters:
    - source_type: Required. One of: near_miss, road_traffic_collision, complaint, reporting_incident
    - q: Optional search query
    - page: Page number (default: 1)
    - page_size: Page size (default: 20, max: 100)

    Response includes:
    - source_id: Record ID
    - display_label: Human-readable label for dropdown
    - reference_number: Record reference
    - status: Current status
    - created_at: Creation date
    - investigation_id: If already investigated, the investigation ID (null otherwise)
    - investigation_reference: If investigated, the investigation reference
    """
    request_id = "N/A"

    # Validate source type
    try:
        source_type_enum = AssignedEntityType(source_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_SOURCE_TYPE",
                "message": f"Invalid source type: {source_type}",
                "details": {"valid_types": [e.value for e in AssignedEntityType]},
                "request_id": request_id,
            },
        )

    # Import models dynamically based on source type
    entity_models = {
        AssignedEntityType.ROAD_TRAFFIC_COLLISION.value: "src.domain.models.rta:RoadTrafficCollision",
        AssignedEntityType.REPORTING_INCIDENT.value: "src.domain.models.incident:Incident",
        AssignedEntityType.COMPLAINT.value: "src.domain.models.complaint:Complaint",
        AssignedEntityType.NEAR_MISS.value: "src.domain.models.near_miss:NearMiss",
    }

    model_path = entity_models.get(source_type)
    if not model_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "UNSUPPORTED_SOURCE_TYPE",
                "message": f"Source type {source_type} is not supported",
                "request_id": request_id,
            },
        )

    module_path, class_name = model_path.split(":")
    module = __import__(module_path, fromlist=[class_name])
    model_class = getattr(module, class_name)

    # Build base query for source records (tenant-scoped if model supports it)
    base_query = select(model_class)
    if hasattr(model_class, "tenant_id"):
        base_query = base_query.where(model_class.tenant_id == current_user.tenant_id)

    # Apply search filter if provided
    if q:
        search_term = f"%{q}%"
        # Try to apply search on common fields
        search_conditions = []
        if hasattr(model_class, "title"):
            search_conditions.append(model_class.title.ilike(search_term))
        if hasattr(model_class, "reference_number"):
            search_conditions.append(model_class.reference_number.ilike(search_term))
        if hasattr(model_class, "description"):
            search_conditions.append(model_class.description.ilike(search_term))
        if search_conditions:
            from sqlalchemy import or_

            base_query = base_query.where(or_(*search_conditions))

    # Apply deterministic ordering and paginate
    base_query = base_query.order_by(model_class.created_at.desc(), model_class.id.asc())
    paginated = await paginate(db, base_query, params)
    records = list(paginated.items)

    # Get existing investigations for these source records
    source_ids = [r.id for r in records]
    inv_query = select(InvestigationRun).where(
        InvestigationRun.assigned_entity_type == source_type_enum,
        InvestigationRun.assigned_entity_id.in_(source_ids),
    )
    inv_result = await db.execute(inv_query)
    existing_investigations = {inv.assigned_entity_id: inv for inv in inv_result.scalars().all()}

    # Build response items
    items = []
    for record in records:
        # Get reference number
        ref_num = getattr(record, "reference_number", f"REF-{record.id}")

        # Get status (safe enum value)
        record_status = getattr(record, "status", "unknown")
        if hasattr(record_status, "value"):
            record_status = record_status.value

        # Format created_at as date only (no PII)
        created_date = record.created_at.strftime("%Y-%m-%d") if record.created_at else "Unknown"

        display_label = f"{ref_num} — {record_status.upper()} — {created_date}"

        # Check if already investigated
        existing_inv = existing_investigations.get(record.id)

        items.append(
            SourceRecordItem(
                source_id=record.id,
                display_label=display_label,
                reference_number=ref_num,
                status=record_status,
                created_at=record.created_at,
                investigation_id=int(existing_inv.id) if existing_inv else None,
                investigation_reference=str(existing_inv.reference_number) if existing_inv else None,
            )
        )

    return SourceRecordsResponse(
        items=items,
        total=paginated.total,
        page=paginated.page,
        page_size=paginated.page_size,
        pages=paginated.pages,
        source_type=source_type,
    )


@router.patch("/{investigation_id}/autosave", response_model=InvestigationRunResponse)
async def autosave_investigation(
    investigation_id: int,
    payload: AutosaveRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Autosave investigation data with optimistic locking.

    Uses version field to prevent concurrent edit conflicts.
    Returns 409 Conflict if version mismatch.
    """
    from src.domain.services.investigation_service import InvestigationService

    request_id = "N/A"

    investigation = await get_or_404(db, InvestigationRun, investigation_id, tenant_id=current_user.tenant_id)

    # Optimistic locking: check version
    if investigation.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "VERSION_CONFLICT",
                "message": "Investigation was modified by another user",
                "details": {
                    "expected_version": payload.version,
                    "current_version": investigation.version,
                },
                "request_id": request_id,
            },
        )

    # Store old data for revision event
    old_data = investigation.data

    # Update data and increment version
    investigation.data = payload.data  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
    investigation.version += 1  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
    investigation.updated_by_id = current_user.id

    # Create revision event
    await InvestigationService.create_revision_event(
        db=db,
        investigation=investigation,
        event_type="DATA_UPDATED",
        actor_id=current_user.id,
        old_value=old_data,
        new_value=payload.data,
    )

    await db.commit()
    await db.refresh(investigation)

    return investigation


@router.post("/{investigation_id}/comments", status_code=status.HTTP_201_CREATED, response_model=CommentResponse)
async def add_comment(
    investigation_id: int,
    request_body: CommentCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Add an internal comment to an investigation.

    Comments are INTERNAL ONLY - never included in customer packs.
    Can be attached to specific sections/fields and support threading.

    Request body:
        - body: Comment content (required)
        - section_id: Section to attach to (optional)
        - field_id: Field to attach to (optional)
        - parent_comment_id: For threading (optional)
    """
    from src.domain.models.investigation import InvestigationComment
    from src.domain.services.investigation_service import InvestigationService

    request_id = "N/A"

    investigation = await get_or_404(db, InvestigationRun, investigation_id, tenant_id=current_user.tenant_id)

    # Validate parent comment if provided
    if request_body.parent_comment_id:
        parent_query = select(InvestigationComment).where(
            InvestigationComment.id == request_body.parent_comment_id,
            InvestigationComment.investigation_id == investigation_id,
            InvestigationComment.deleted_at.is_(None),
        )
        parent_result = await db.execute(parent_query)
        parent_comment = parent_result.scalar_one_or_none()
        if not parent_comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "PARENT_COMMENT_NOT_FOUND",
                    "message": f"Parent comment {request_body.parent_comment_id} not found",
                    "request_id": request_id,
                },
            )

    # Create comment (map 'body' from request to 'content' in model)
    comment = InvestigationComment(
        investigation_id=investigation_id,
        content=request_body.body,  # Frontend sends 'body', we store as 'content'
        section_id=request_body.section_id,
        field_id=request_body.field_id,
        parent_comment_id=request_body.parent_comment_id,
        author_id=current_user.id,
    )

    db.add(comment)

    # Create revision event
    await InvestigationService.create_revision_event(
        db=db,
        investigation=investigation,
        event_type="COMMENT_ADDED",
        actor_id=current_user.id,
        metadata={
            "section_id": request_body.section_id,
            "field_id": request_body.field_id,
            "is_reply": request_body.parent_comment_id is not None,
        },
    )

    await db.commit()
    await db.refresh(comment)

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
    current_user: CurrentUser,
    approved: bool = True,
    rejection_reason: Optional[str] = None,
):
    """Approve or reject an investigation.

    Moves investigation to COMPLETED (approved) or back to IN_PROGRESS (rejected).
    """
    from src.domain.services.investigation_service import InvestigationService

    request_id = "N/A"

    investigation = await get_or_404(db, InvestigationRun, investigation_id, tenant_id=current_user.tenant_id)

    # Check status allows approval
    if investigation.status not in (InvestigationStatus.UNDER_REVIEW, InvestigationStatus.IN_PROGRESS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_STATUS_TRANSITION",
                "message": f"Cannot approve investigation in status {investigation.status.value}",
                "request_id": request_id,
            },
        )

    old_status = investigation.status

    if approved:
        investigation.status = InvestigationStatus.COMPLETED  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
        investigation.approved_at = datetime.now(timezone.utc)  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
        investigation.approved_by_id = current_user.id  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
        investigation.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
        investigation.rejection_reason = None  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
        event_type = "APPROVED"
    else:
        if not rejection_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "REJECTION_REASON_REQUIRED",
                    "message": "Rejection reason is required",
                    "request_id": request_id,
                },
            )
        investigation.status = InvestigationStatus.IN_PROGRESS
        investigation.rejection_reason = rejection_reason
        event_type = "REJECTED"

    investigation.updated_by_id = current_user.id
    investigation.version += 1

    # Create revision event
    await InvestigationService.create_revision_event(
        db=db,
        investigation=investigation,
        event_type=event_type,
        actor_id=current_user.id,
        old_value={"status": old_status.value},
        new_value={"status": investigation.status.value},
        metadata={"rejection_reason": rejection_reason} if not approved else None,
    )

    await db.commit()
    await db.refresh(investigation)

    return investigation


@router.post("/{investigation_id}/customer-pack", response_model=dict)
async def generate_customer_pack(
    investigation_id: int,
    audience: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Generate a customer pack with audience-specific redaction.

    Audience options:
    - internal_customer: identities retained, internal comments excluded
    - external_customer: identities redacted, only external-allowed evidence

    Returns the generated pack with redaction log.
    """
    from src.domain.models.investigation import CustomerPackAudience
    from src.domain.services.investigation_service import InvestigationService

    request_id = "N/A"

    # Validate audience
    try:
        audience_enum = CustomerPackAudience(audience)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_AUDIENCE",
                "message": f"Invalid audience: {audience}",
                "details": {"valid_audiences": [e.value for e in CustomerPackAudience]},
                "request_id": request_id,
            },
        )

    investigation = await get_or_404(db, InvestigationRun, investigation_id, tenant_id=current_user.tenant_id)

    # Get linked evidence assets
    from src.domain.models.evidence_asset import EvidenceAsset

    assets_query = select(EvidenceAsset).where(
        EvidenceAsset.linked_investigation_id == investigation_id,
        EvidenceAsset.deleted_at.is_(None),
    )
    assets_result = await db.execute(assets_query)
    evidence_assets = list(assets_result.scalars().all())

    # Generate pack with redaction
    content, redaction_log, included_assets = InvestigationService.generate_customer_pack(
        investigation=investigation,
        audience=audience_enum,
        evidence_assets=evidence_assets,
        generated_by_id=current_user.id,
        generated_by_role=None,  # TODO: Get user role
    )

    # Create pack entity
    pack = InvestigationService.create_customer_pack_entity(
        investigation_id=investigation_id,
        audience=audience_enum,
        content=content,
        redaction_log=redaction_log,
        included_assets=included_assets,
        generated_by_id=current_user.id,
    )

    db.add(pack)

    # Create revision event
    await InvestigationService.create_revision_event(
        db=db,
        investigation=investigation,
        event_type="PACK_GENERATED",
        actor_id=current_user.id,
        metadata={
            "pack_uuid": pack.pack_uuid,
            "audience": audience,
            "redaction_count": len(redaction_log),
            "assets_included": sum(1 for a in included_assets if a["included"]),
            "assets_excluded": sum(1 for a in included_assets if not a["included"]),
        },
    )

    await db.commit()
    await db.refresh(pack)

    return {
        "pack_id": pack.id,
        "pack_uuid": pack.pack_uuid,
        "audience": pack.audience.value,
        "investigation_id": investigation_id,
        "investigation_reference": investigation.reference_number,
        "generated_at": pack.created_at.isoformat() if pack.created_at else None,
        "content": pack.content,
        "redaction_log": pack.redaction_log,
        "included_assets": pack.included_assets,
        "checksum": pack.checksum_sha256,
    }


# =============================================================================
# Stage 1: Timeline, Comments, Packs List, Closure Validation Endpoints
# =============================================================================


def _user_can_access_investigation(user, investigation: InvestigationRun) -> bool:
    """Check if user has access to an investigation.

    Access is granted if:
    - User is superuser
    - User has 'investigations:view_all' permission
    - User is assigned_to the investigation
    - User is the reviewer of the investigation
    - User approved the investigation

    This implements least-privilege authz: users only see investigations
    they are directly involved with, unless they have elevated permissions.
    """
    # Superuser always has access
    if user.is_superuser:
        return True

    # Check for global view permission
    if user.has_permission("investigations:view_all"):
        return True

    # Check direct assignment
    if investigation.assigned_to_user_id == user.id:
        return True

    # Check reviewer
    if investigation.reviewer_user_id == user.id:
        return True

    # Check approver
    if investigation.approved_by_id == user.id:
        return True

    return False


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
    await get_or_404(db, InvestigationRun, investigation_id, tenant_id=current_user.tenant_id)

    # Build query for timeline events
    query = select(InvestigationRevisionEvent).where(InvestigationRevisionEvent.investigation_id == investigation_id)

    # Apply event_type filter if provided
    if event_type:
        query = query.where(InvestigationRevisionEvent.event_type == event_type)

    # Deterministic ordering: created_at DESC, id DESC
    query = query.order_by(
        desc(InvestigationRevisionEvent.created_at),
        desc(InvestigationRevisionEvent.id),
    )

    result = await paginate(db, query, params)

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
    request_id = "N/A"

    # SECURITY: include_deleted requires admin/superuser permission
    if include_deleted:
        has_deleted_access = current_user.is_superuser or current_user.has_permission(
            "investigations:comments:read_deleted"
        )
        if not has_deleted_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "FORBIDDEN",
                    "message": "Permission 'investigations:comments:read_deleted' required to view deleted comments",
                    "request_id": request_id,
                },
            )

    await get_or_404(db, InvestigationRun, investigation_id, tenant_id=current_user.tenant_id)

    # Build query for comments
    query = select(InvestigationComment).where(InvestigationComment.investigation_id == investigation_id)

    # Exclude soft-deleted by default
    if not include_deleted:
        query = query.where(InvestigationComment.deleted_at.is_(None))

    # Deterministic ordering: created_at DESC, id DESC
    query = query.order_by(
        desc(InvestigationComment.created_at),
        desc(InvestigationComment.id),
    )

    result = await paginate(db, query, params)

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
    await get_or_404(db, InvestigationRun, investigation_id, tenant_id=current_user.tenant_id)

    # Build query for packs
    query = select(InvestigationCustomerPack).where(InvestigationCustomerPack.investigation_id == investigation_id)

    # Deterministic ordering: created_at DESC, id DESC
    query = query.order_by(
        desc(InvestigationCustomerPack.created_at),
        desc(InvestigationCustomerPack.id),
    )

    result = await paginate(db, query, params)

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


# Closure validation reason codes
class ClosureReasonCode:
    """Stable reason codes for closure validation failures."""

    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    MISSING_REQUIRED_SECTION = "MISSING_REQUIRED_SECTION"
    INVALID_ARRAY_EMPTY = "INVALID_ARRAY_EMPTY"
    LEVEL_NOT_SET = "LEVEL_NOT_SET"
    STATUS_NOT_COMPLETE = "STATUS_NOT_COMPLETE"


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
    checked_at = datetime.now(timezone.utc)

    investigation = await get_or_404(db, InvestigationRun, investigation_id, tenant_id=current_user.tenant_id)

    reason_codes: List[str] = []
    missing_fields: List[str] = []

    # Get template
    template_query = select(InvestigationTemplate).where(InvestigationTemplate.id == investigation.template_id)
    template_result = await db.execute(template_query)
    template = template_result.scalar_one_or_none()

    # Helper to get level as string value
    def get_level_str(level: object) -> str | None:
        if level is None:
            return None
        # Handle both enum and string values
        if hasattr(level, "value"):
            return str(level.value)
        return str(level)

    level_str = get_level_str(investigation.level)

    if not template:
        return ClosureValidationResponse(
            status="BLOCKED",
            reason_codes=[ClosureReasonCode.TEMPLATE_NOT_FOUND],
            missing_fields=[],
            checked_at_utc=checked_at,
            investigation_id=investigation_id,
            investigation_level=level_str,
        )

    # Check if level is set (required for section gating)
    if not investigation.level:
        reason_codes.append(ClosureReasonCode.LEVEL_NOT_SET)

    # Get investigation data
    data: dict = dict(investigation.data) if investigation.data else {}

    # Get required sections based on level
    # LOW: sections 1-3, MEDIUM: sections 1-4, HIGH: sections 1-6
    level_section_counts = {
        "low": 3,
        "medium": 4,
        "high": 6,
    }
    max_sections = level_section_counts.get(level_str or "high", 6)

    # Validate template structure
    structure: dict = dict(template.structure) if template.structure else {}
    sections = structure.get("sections", [])

    for i, section in enumerate(sections):
        # Skip sections beyond the level requirement
        if i >= max_sections:
            break

        section_id = section.get("id", f"section_{i}")
        section_data = data.get(section_id, {})

        # Check if section exists in data
        if section_id not in data:
            # Check if section has any required fields
            fields = section.get("fields", [])
            has_required = any(f.get("required", False) for f in fields)
            if has_required:
                reason_codes.append(ClosureReasonCode.MISSING_REQUIRED_SECTION)
                missing_fields.append(section_id)
            continue

        # Validate required fields within section
        fields = section.get("fields", [])
        for field in fields:
            field_id = field.get("id")
            is_required = field.get("required", False)
            field_type = field.get("type", "text")

            if not is_required:
                continue

            field_path = f"{section_id}.{field_id}"
            field_value = section_data.get(field_id)

            # Check if field is missing or empty
            if field_value is None:
                reason_codes.append(ClosureReasonCode.MISSING_REQUIRED_FIELD)
                missing_fields.append(field_path)
            elif field_type == "text" and isinstance(field_value, str) and not field_value.strip():
                reason_codes.append(ClosureReasonCode.MISSING_REQUIRED_FIELD)
                missing_fields.append(field_path)
            elif field_type == "array" and isinstance(field_value, list) and len(field_value) == 0:
                reason_codes.append(ClosureReasonCode.INVALID_ARRAY_EMPTY)
                missing_fields.append(field_path)

    # Deduplicate reason codes (keep unique)
    unique_reason_codes = list(dict.fromkeys(reason_codes))

    closure_status = "OK" if not unique_reason_codes else "BLOCKED"

    return ClosureValidationResponse(
        status=closure_status,
        reason_codes=unique_reason_codes,
        missing_fields=missing_fields,
        checked_at_utc=checked_at,
        investigation_id=investigation_id,
        investigation_level=level_str,
    )
