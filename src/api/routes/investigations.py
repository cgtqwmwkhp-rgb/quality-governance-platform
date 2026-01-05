"""Investigation Run API routes."""

import math
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.investigation import (
    InvestigationRunCreate,
    InvestigationRunListResponse,
    InvestigationRunResponse,
    InvestigationRunUpdate,
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

    # Validate template exists
    template_query = select(InvestigationTemplate).where(InvestigationTemplate.id == investigation_data.template_id)
    template_result = await db.execute(template_query)
    template = template_result.scalar_one_or_none()

    if not template:
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
