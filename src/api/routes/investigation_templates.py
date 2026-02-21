"""Investigation Template API routes."""

import math
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.investigation import (
    InvestigationTemplateCreate,
    InvestigationTemplateListResponse,
    InvestigationTemplateResponse,
    InvestigationTemplateUpdate,
)
from src.domain.models.investigation import InvestigationTemplate

router = APIRouter()


@router.post("/", response_model=InvestigationTemplateResponse, status_code=201)
async def create_template(
    template_data: InvestigationTemplateCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new investigation template.

    Requires authentication and appropriate permissions.
    """
    # Create template
    template = InvestigationTemplate(
        name=template_data.name,
        description=template_data.description,
        version=template_data.version,
        is_active=template_data.is_active,
        structure=template_data.structure,
        applicable_entity_types=template_data.applicable_entity_types,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )

    db.add(template)
    await db.commit()
    await db.refresh(template)

    return template


@router.get("/", response_model=InvestigationTemplateListResponse)
async def list_templates(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
):
    """List investigation templates with pagination.

    Returns templates in deterministic order (by ID).
    """
    # Build query
    query = select(InvestigationTemplate)

    # Apply filters
    if is_active is not None:
        query = query.where(InvestigationTemplate.is_active == is_active)

    # Deterministic ordering
    query = query.order_by(InvestigationTemplate.id)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    templates = result.scalars().all()

    total_pages = math.ceil(total / page_size) if total and total > 0 else 1

    return InvestigationTemplateListResponse(
        items=[InvestigationTemplateResponse.model_validate(t) for t in templates],
        total=total or 0,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{template_id}", response_model=InvestigationTemplateResponse)
async def get_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific investigation template by ID."""
    request_id = "N/A"  # TODO: Get from request context

    query = select(InvestigationTemplate).where(InvestigationTemplate.id == template_id)
    result = await db.execute(query)
    template = result.scalar_one_or_none()

    if not template:
        pass
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "TEMPLATE_NOT_FOUND",
                "message": f"Investigation template with ID {template_id} not found",
                "details": {"template_id": template_id},
                "request_id": request_id,
            },
        )

    return template


@router.patch("/{template_id}", response_model=InvestigationTemplateResponse)
async def update_template(
    template_id: int,
    template_data: InvestigationTemplateUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update an investigation template.

    Only provided fields will be updated (partial update).
    """
    request_id = "N/A"  # TODO: Get from request context

    # Get existing template
    query = select(InvestigationTemplate).where(InvestigationTemplate.id == template_id)
    result = await db.execute(query)
    template = result.scalar_one_or_none()

    if not template:
        pass
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "TEMPLATE_NOT_FOUND",
                "message": f"Investigation template with ID {template_id} not found",
                "details": {"template_id": template_id},
                "request_id": request_id,
            },
        )

    # Update fields
    update_data = template_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    template.updated_by_id = current_user.id

    await db.commit()
    await db.refresh(template)

    return template


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
):
    """Delete an investigation template.

    Only safe if no investigation runs reference this template.
    """
    request_id = "N/A"  # TODO: Get from request context

    # Get existing template
    query = select(InvestigationTemplate).where(InvestigationTemplate.id == template_id)
    result = await db.execute(query)
    template = result.scalar_one_or_none()

    if not template:
        pass
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "TEMPLATE_NOT_FOUND",
                "message": f"Investigation template with ID {template_id} not found",
                "details": {"template_id": template_id},
                "request_id": request_id,
            },
        )

    # Check if template has investigation runs
    from src.domain.models.investigation import InvestigationRun

    count_query = select(func.count()).where(InvestigationRun.template_id == template_id)
    run_count = await db.scalar(count_query)

    if run_count and run_count > 0:
        pass
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "TEMPLATE_IN_USE",
                "message": f"Cannot delete template with {run_count} investigation run(s)",
                "details": {"template_id": template_id, "run_count": run_count},
                "request_id": request_id,
            },
        )

    await db.delete(template)
    await db.commit()

    return None
