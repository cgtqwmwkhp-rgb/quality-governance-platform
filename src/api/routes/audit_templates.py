"""Audit Template Builder API Routes.

Delegates to the production AuditService for all operations.
This route module provides the /api/v1/audit-templates path that the
AuditTemplateBuilder frontend component uses. All endpoints proxy through
to the same AuditService that backs /api/v1/audits/templates.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Query, status
from sqlalchemy import func, or_, select

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.audit import (
    ArchiveTemplateResponse,
    AuditQuestionCreate,
    AuditQuestionResponse,
    AuditQuestionUpdate,
    AuditSectionCreate,
    AuditSectionResponse,
    AuditSectionUpdate,
    AuditTemplateCreate,
    AuditTemplateDetailResponse,
    AuditTemplateListResponse,
    AuditTemplateResponse,
    AuditTemplateUpdate,
)
from src.domain.models.audit import AuditTemplate
from src.domain.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/categories")
async def list_categories(
    db: DbSession,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    """Return distinct categories with template counts for the current tenant."""
    query = (
        select(
            AuditTemplate.category,
            func.count(AuditTemplate.id).label("count"),
        )
        .where(
            AuditTemplate.is_active == True,  # noqa: E712
            AuditTemplate.archived_at.is_(None),
            or_(
                AuditTemplate.tenant_id == user.tenant_id,
                AuditTemplate.tenant_id.is_(None),
            ),
            AuditTemplate.category.isnot(None),
        )
        .group_by(AuditTemplate.category)
        .order_by(AuditTemplate.category)
    )
    rows = (await db.execute(query)).all()
    return [{"category": row[0], "count": row[1]} for row in rows]


@router.get("/", response_model=AuditTemplateListResponse)
async def list_templates(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    audit_type: Optional[str] = None,
    is_published: Optional[bool] = None,
):
    """List audit templates with filtering and pagination."""
    service = AuditService(db)
    result = await service.list_templates(
        tenant_id=user.tenant_id,
        page=page,
        page_size=page_size,
        search=search,
        category=category,
        audit_type=audit_type,
        is_published=is_published,
    )
    items = []
    for t in result.items:
        resp = AuditTemplateResponse.model_validate(t)
        resp.section_count = len(t.sections)
        resp.question_count = sum(len(s.questions) for s in t.sections)
        items.append(resp)
    return AuditTemplateListResponse(
        items=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        pages=result.pages,
    )


@router.post("/", response_model=AuditTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: AuditTemplateCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create a new audit template."""
    service = AuditService(db)
    template = await service.create_template(
        data=template_data.model_dump(exclude_unset=True),
        standard_ids=None,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )
    return AuditTemplateResponse.model_validate(template)


@router.get("/{template_id}", response_model=AuditTemplateDetailResponse)
async def get_template(
    template_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Get a specific audit template with sections and questions."""
    service = AuditService(db)
    template = await service.get_template_detail(
        template_id=template_id,
        tenant_id=user.tenant_id,
    )
    resp = AuditTemplateDetailResponse.model_validate(template)
    resp.question_count = len(template.questions)
    resp.section_count = len(template.sections)
    return resp


@router.patch("/{template_id}", response_model=AuditTemplateResponse)
async def update_template(
    template_id: int,
    updates: AuditTemplateUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update an existing audit template."""
    service = AuditService(db)
    template = await service.update_template(
        template_id=template_id,
        update_data=updates.model_dump(exclude_unset=True),
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
    )
    return AuditTemplateResponse.model_validate(template)


@router.delete("/{template_id}", response_model=ArchiveTemplateResponse)
async def archive_template(
    template_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Archive (soft-delete) an audit template."""
    service = AuditService(db)
    template = await service.archive_template(
        template_id=template_id,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
    )
    return ArchiveTemplateResponse.model_validate(template)


@router.post("/{template_id}/restore", response_model=AuditTemplateResponse)
async def restore_template(
    template_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Restore an archived template."""
    service = AuditService(db)
    template = await service.restore_template(
        template_id=template_id,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
    )
    return AuditTemplateResponse.model_validate(template)


@router.post(
    "/{template_id}/duplicate",
    response_model=AuditTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_template(
    template_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Duplicate an existing template."""
    service = AuditService(db)
    template = await service.clone_template(
        template_id=template_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )
    return AuditTemplateResponse.model_validate(template)


@router.post("/{template_id}/publish", response_model=AuditTemplateResponse)
async def publish_template(
    template_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Publish a template."""
    service = AuditService(db)
    template = await service.publish_template(
        template_id=template_id,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
    )
    return AuditTemplateResponse.model_validate(template)


# -- Section endpoints --


@router.post(
    "/{template_id}/sections",
    response_model=AuditSectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_section(
    template_id: int,
    section_data: AuditSectionCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Add a section to a template."""
    service = AuditService(db)
    section = await service.create_section(
        template_id=template_id,
        data=section_data.model_dump(exclude_unset=True),
        tenant_id=user.tenant_id,
    )
    return AuditSectionResponse.model_validate(section)


@router.patch("/sections/{section_id}", response_model=AuditSectionResponse)
async def update_section(
    section_id: int,
    section_data: AuditSectionUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update a section."""
    service = AuditService(db)
    section = await service.update_section(
        section_id=section_id,
        update_data=section_data.model_dump(exclude_unset=True),
        tenant_id=user.tenant_id,
    )
    return AuditSectionResponse.model_validate(section)


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Delete a section."""
    service = AuditService(db)
    await service.delete_section(
        section_id=section_id,
        tenant_id=user.tenant_id,
    )


# -- Question endpoints --


@router.post(
    "/{template_id}/questions",
    response_model=AuditQuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_question(
    template_id: int,
    question_data: AuditQuestionCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Add a question to a template."""
    service = AuditService(db)
    question = await service.create_question(
        template_id=template_id,
        data=question_data.model_dump(exclude_unset=True),
        tenant_id=user.tenant_id,
    )
    return AuditQuestionResponse.model_validate(question)


@router.patch("/questions/{question_id}", response_model=AuditQuestionResponse)
async def update_question(
    question_id: int,
    question_data: AuditQuestionUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update a question."""
    service = AuditService(db)
    question = await service.update_question(
        question_id=question_id,
        update_data=question_data.model_dump(exclude_unset=True),
        tenant_id=user.tenant_id,
    )
    return AuditQuestionResponse.model_validate(question)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Delete a question."""
    service = AuditService(db)
    await service.delete_question(
        question_id=question_id,
        tenant_id=user.tenant_id,
    )
