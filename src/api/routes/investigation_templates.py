"""Investigation Template API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.investigation import (
    InvestigationTemplateCreate,
    InvestigationTemplateListResponse,
    InvestigationTemplateResponse,
    InvestigationTemplateUpdate,
)
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.investigation import InvestigationTemplate
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter()


@router.post("/", response_model=InvestigationTemplateResponse, status_code=status.HTTP_201_CREATED)
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
    params: PaginationParams = Depends(),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
):
    """List investigation templates with pagination.

    Returns templates in deterministic order (by ID).
    """
    query = select(InvestigationTemplate)

    if is_active is not None:
        query = query.where(InvestigationTemplate.is_active == is_active)

    query = query.order_by(InvestigationTemplate.id)

    paginated = await paginate(db, query, params)
    track_metric("investigation_templates.accessed")

    return InvestigationTemplateListResponse(
        items=[InvestigationTemplateResponse.model_validate(t) for t in paginated.items],
        total=paginated.total,
        page=paginated.page,
        page_size=paginated.page_size,
        pages=paginated.pages,
    )


@router.get("/{template_id}", response_model=InvestigationTemplateResponse)
async def get_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific investigation template by ID."""
    template = await get_or_404(db, InvestigationTemplate, template_id)
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
    template = await get_or_404(db, InvestigationTemplate, template_id)

    apply_updates(template, template_data)

    template.updated_by_id = current_user.id

    await db.commit()
    await db.refresh(template)

    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
):
    """Delete an investigation template.

    Only safe if no investigation runs reference this template.
    """
    template = await get_or_404(db, InvestigationTemplate, template_id)

    # Check if template has investigation runs
    from src.domain.models.investigation import InvestigationRun

    count_query = select(func.count()).where(InvestigationRun.template_id == template_id)
    run_count = await db.scalar(count_query)

    if run_count and run_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "TEMPLATE_IN_USE",
                "message": f"Cannot delete template with {run_count} investigation run(s)",
                "details": {"template_id": template_id, "run_count": run_count},
            },
        )

    await db.delete(template)
    await db.commit()

    return None
