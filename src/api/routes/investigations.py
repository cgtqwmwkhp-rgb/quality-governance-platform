"""Investigation Run API routes."""

import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.investigation import (
    CreateFromRecordRequest,
    InvestigationRunCreate,
    InvestigationRunListResponse,
    InvestigationRunResponse,
    InvestigationRunUpdate,
    SourceRecordItem,
    SourceRecordsResponse,
)
from src.domain.models.investigation import (
    AssignedEntityType,
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
            status_code=400,
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

    # Check if entity exists
    query = select(model_class).where(model_class.id == entity_id)
    result = await db.execute(query)
    entity = result.scalar_one_or_none()

    if not entity:
        raise HTTPException(
            status_code=404,
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


@router.post("/", response_model=InvestigationRunResponse, status_code=201)
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
    request_id = "N/A"  # TODO: Get from request context

    # Validate template exists, create default if missing
    template_query = select(InvestigationTemplate).where(InvestigationTemplate.id == investigation_data.template_id)
    template_result = await db.execute(template_query)
    template = template_result.scalar_one_or_none()

    if not template:
        # Auto-create a default template if template_id is 1 and doesn't exist
        if investigation_data.template_id == 1:
            default_template = InvestigationTemplate(
                id=1,
                name="Default Investigation Template",
                description="Standard investigation template for incidents, RTAs, and complaints",
                version="1.0",
                is_active=True,
                structure={
                    "sections": [
                        {
                            "id": "rca",
                            "title": "Root Cause Analysis",
                            "fields": [
                                {"id": "problem_statement", "type": "text", "required": True},
                                {"id": "root_cause", "type": "text", "required": True},
                                {"id": "contributing_factors", "type": "array", "required": False},
                                {"id": "corrective_actions", "type": "array", "required": True},
                            ],
                        }
                    ]
                },
                applicable_entity_types=[
                    "road_traffic_collision",
                    "reporting_incident",
                    "complaint",
                    "near_miss",
                ],
                created_by_id=current_user.id,
                updated_by_id=current_user.id,
            )
            db.add(default_template)
            await db.commit()
            await db.refresh(default_template)
            template = default_template
        else:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "TEMPLATE_NOT_FOUND",
                    "message": f"Investigation template with ID {investigation_data.template_id} not found",
                    "details": {"template_id": investigation_data.template_id},
                    "request_id": request_id,
                },
            )

    # Validate assigned entity exists
    await validate_assigned_entity(
        investigation_data.assigned_entity_type,
        investigation_data.assigned_entity_id,
        db,
        request_id,
    )

    # Generate reference number
    from src.services.reference_number import ReferenceNumberService

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
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )

    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    return investigation


@router.get("/", response_model=InvestigationRunListResponse)
async def list_investigations(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[int] = Query(None, description="Filter by entity ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """List investigation runs with pagination.

    Returns investigations in deterministic order (created_at DESC, id ASC).
    Can filter by entity_type, entity_id, and status.
    """
    request_id = "N/A"  # TODO: Get from request context

    # Build query
    query = select(InvestigationRun)

    # Apply filters
    if entity_type is not None:
        try:
            entity_type_enum = AssignedEntityType(entity_type)
            query = query.where(InvestigationRun.assigned_entity_type == entity_type_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
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

    if status is not None:
        try:
            status_enum = InvestigationStatus(status)
            query = query.where(InvestigationRun.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "INVALID_STATUS",
                    "message": f"Invalid status: {status}",
                    "details": {
                        "status": status,
                        "valid_statuses": [s.value for s in InvestigationStatus],
                    },
                    "request_id": request_id,
                },
            )

    # Deterministic ordering: created_at DESC, id ASC
    query = query.order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    investigations = result.scalars().all()

    total_pages = math.ceil(total / page_size) if total and total > 0 else 1

    return InvestigationRunListResponse(
        items=[InvestigationRunResponse.model_validate(inv) for inv in investigations],
        total=total or 0,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{investigation_id}", response_model=InvestigationRunResponse)
async def get_investigation(
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific investigation run by ID."""
    request_id = "N/A"  # TODO: Get from request context

    query = select(InvestigationRun).where(InvestigationRun.id == investigation_id)
    result = await db.execute(query)
    investigation = result.scalar_one_or_none()

    if not investigation:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "INVESTIGATION_NOT_FOUND",
                "message": f"Investigation with ID {investigation_id} not found",
                "details": {"investigation_id": investigation_id},
                "request_id": request_id,
            },
        )

    return investigation


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
    request_id = "N/A"  # TODO: Get from request context

    # Get existing investigation
    query = select(InvestigationRun).where(InvestigationRun.id == investigation_id)
    result = await db.execute(query)
    investigation = result.scalar_one_or_none()

    if not investigation:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "INVESTIGATION_NOT_FOUND",
                "message": f"Investigation with ID {investigation_id} not found",
                "details": {"investigation_id": investigation_id},
                "request_id": request_id,
            },
        )

    # Update fields
    update_data = investigation_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and value is not None:
            setattr(investigation, field, InvestigationStatus(value))
        else:
            setattr(investigation, field, value)

    investigation.updated_by_id = current_user.id

    # Update status timestamps
    if investigation_data.status:
        if investigation_data.status == "in_progress" and not investigation.started_at:
            setattr(investigation, "started_at", datetime.utcnow())
        elif investigation_data.status == "completed" and not investigation.completed_at:
            setattr(investigation, "completed_at", datetime.utcnow())
        elif investigation_data.status == "closed" and not investigation.closed_at:
            setattr(investigation, "closed_at", datetime.utcnow())

    await db.commit()
    await db.refresh(investigation)

    return investigation


# === Stage 2 Endpoints ===


@router.post("/from-record", response_model=InvestigationRunResponse, status_code=201)
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
    from src.services.investigation_service import InvestigationService
    from src.services.reference_number import ReferenceNumberService

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
        InvestigationRun.assigned_entity_type == source_type_enum,
        InvestigationRun.assigned_entity_id == source_id,
    )
    existing_result = await db.execute(existing_query)
    existing_investigation = existing_result.scalar_one_or_none()

    if existing_investigation:
        raise HTTPException(
            status_code=409,
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
            status_code=404,
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

    # Validate template exists or create default
    template_query = select(InvestigationTemplate).where(InvestigationTemplate.id == template_id)
    template_result = await db.execute(template_query)
    template = template_result.scalar_one_or_none()

    if not template and template_id == 1:
        # Auto-create default template
        template = InvestigationTemplate(
            id=1,
            name="Investigation Report Template v2.1",
            description="Standard investigation template based on Plantexpand Template v2.0",
            version="2.1",
            is_active=True,
            structure={"sections": []},
            applicable_entity_types=[e.value for e in AssignedEntityType],
            created_by_id=current_user.id,
            updated_by_id=current_user.id,
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)

    if not template:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "TEMPLATE_NOT_FOUND",
                "message": f"Template {template_id} not found",
                "request_id": request_id,
            },
        )

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
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
):
    """List source records available for investigation creation.

    Returns records of the specified type with investigation status.
    Records that already have an investigation are marked with investigation_id.

    Query Parameters:
    - source_type: Required. One of: near_miss, road_traffic_collision, complaint, reporting_incident
    - q: Optional search query
    - page: Page number (default: 1)
    - size: Page size (default: 20, max: 100)

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
            status_code=400,
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
            status_code=400,
            detail={
                "error_code": "UNSUPPORTED_SOURCE_TYPE",
                "message": f"Source type {source_type} is not supported",
                "request_id": request_id,
            },
        )

    module_path, class_name = model_path.split(":")
    module = __import__(module_path, fromlist=[class_name])
    model_class = getattr(module, class_name)

    # Build base query for source records
    base_query = select(model_class)

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

    # Count total records
    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply deterministic ordering and pagination
    base_query = base_query.order_by(model_class.created_at.desc(), model_class.id.asc())
    offset = (page - 1) * size
    base_query = base_query.offset(offset).limit(size)

    # Execute query
    result = await db.execute(base_query)
    records = list(result.scalars().all())

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
        status = getattr(record, "status", "unknown")
        if hasattr(status, "value"):
            status = status.value

        # Format created_at as date only (no PII)
        created_date = record.created_at.strftime("%Y-%m-%d") if record.created_at else "Unknown"

        # === SAFE DISPLAY LABEL (NO PII) ===
        # Format: "{reference_number} — {status} — {date}"
        # This avoids exposing free-text fields that may contain PII
        display_label = f"{ref_num} — {status.upper()} — {created_date}"

        # Check if already investigated
        existing_inv = existing_investigations.get(record.id)

        items.append(
            SourceRecordItem(
                source_id=record.id,
                display_label=display_label,
                reference_number=ref_num,
                status=status,
                created_at=record.created_at,
                investigation_id=existing_inv.id if existing_inv else None,
                investigation_reference=existing_inv.reference_number if existing_inv else None,
            )
        )

    total_pages = math.ceil(total / size) if total > 0 else 1

    return SourceRecordsResponse(
        items=items,
        total=total,
        page=page,
        page_size=size,
        total_pages=total_pages,
        source_type=source_type,
    )


@router.patch("/{investigation_id}/autosave", response_model=InvestigationRunResponse)
async def autosave_investigation(
    investigation_id: int,
    data: dict,
    version: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Autosave investigation data with optimistic locking.

    Uses version field to prevent concurrent edit conflicts.
    Returns 409 Conflict if version mismatch.
    """
    from src.services.investigation_service import InvestigationService

    request_id = "N/A"

    # Get investigation with version check
    query = select(InvestigationRun).where(InvestigationRun.id == investigation_id)
    result = await db.execute(query)
    investigation = result.scalar_one_or_none()

    if not investigation:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "INVESTIGATION_NOT_FOUND",
                "message": f"Investigation {investigation_id} not found",
                "request_id": request_id,
            },
        )

    # Optimistic locking: check version
    if investigation.version != version:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "VERSION_CONFLICT",
                "message": "Investigation was modified by another user",
                "details": {
                    "expected_version": version,
                    "current_version": investigation.version,
                },
                "request_id": request_id,
            },
        )

    # Store old data for revision event
    old_data = investigation.data

    # Update data and increment version
    investigation.data = data  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
    investigation.version += 1  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
    investigation.updated_by_id = current_user.id

    # Create revision event
    await InvestigationService.create_revision_event(
        db=db,
        investigation=investigation,
        event_type="DATA_UPDATED",
        actor_id=current_user.id,
        old_value=old_data,
        new_value=data,
    )

    await db.commit()
    await db.refresh(investigation)

    return investigation


@router.post("/{investigation_id}/comments", status_code=201)
async def add_comment(
    investigation_id: int,
    content: str,
    db: DbSession,
    current_user: CurrentUser,
    section_id: Optional[str] = None,
    field_id: Optional[str] = None,
    parent_comment_id: Optional[int] = None,
):
    """Add an internal comment to an investigation.

    Comments are INTERNAL ONLY - never included in customer packs.
    Can be attached to specific sections/fields and support threading.
    """
    from src.domain.models.investigation import InvestigationComment
    from src.services.investigation_service import InvestigationService

    request_id = "N/A"

    # Validate investigation exists
    query = select(InvestigationRun).where(InvestigationRun.id == investigation_id)
    result = await db.execute(query)
    investigation = result.scalar_one_or_none()

    if not investigation:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "INVESTIGATION_NOT_FOUND",
                "message": f"Investigation {investigation_id} not found",
                "request_id": request_id,
            },
        )

    # Validate parent comment if provided
    if parent_comment_id:
        parent_query = select(InvestigationComment).where(
            InvestigationComment.id == parent_comment_id,
            InvestigationComment.investigation_id == investigation_id,
            InvestigationComment.deleted_at.is_(None),
        )
        parent_result = await db.execute(parent_query)
        parent_comment = parent_result.scalar_one_or_none()
        if not parent_comment:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "PARENT_COMMENT_NOT_FOUND",
                    "message": f"Parent comment {parent_comment_id} not found",
                    "request_id": request_id,
                },
            )

    # Create comment
    comment = InvestigationComment(
        investigation_id=investigation_id,
        content=content,
        section_id=section_id,
        field_id=field_id,
        parent_comment_id=parent_comment_id,
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
            "section_id": section_id,
            "field_id": field_id,
            "is_reply": parent_comment_id is not None,
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
    from src.services.investigation_service import InvestigationService

    request_id = "N/A"

    # Get investigation
    query = select(InvestigationRun).where(InvestigationRun.id == investigation_id)
    result = await db.execute(query)
    investigation = result.scalar_one_or_none()

    if not investigation:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "INVESTIGATION_NOT_FOUND",
                "message": f"Investigation {investigation_id} not found",
                "request_id": request_id,
            },
        )

    # Check status allows approval
    if investigation.status not in (InvestigationStatus.UNDER_REVIEW, InvestigationStatus.IN_PROGRESS):
        raise HTTPException(
            status_code=400,
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
                status_code=400,
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


@router.post("/{investigation_id}/customer-pack")
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
    from src.services.investigation_service import InvestigationService

    request_id = "N/A"

    # Validate audience
    try:
        audience_enum = CustomerPackAudience(audience)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "INVALID_AUDIENCE",
                "message": f"Invalid audience: {audience}",
                "details": {"valid_audiences": [e.value for e in CustomerPackAudience]},
                "request_id": request_id,
            },
        )

    # Get investigation
    query = select(InvestigationRun).where(InvestigationRun.id == investigation_id)
    result = await db.execute(query)
    investigation = result.scalar_one_or_none()

    if not investigation:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "INVESTIGATION_NOT_FOUND",
                "message": f"Investigation {investigation_id} not found",
                "request_id": request_id,
            },
        )

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
