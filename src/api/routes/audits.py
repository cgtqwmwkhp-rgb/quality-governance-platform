"""Audits & Inspections API routes.

Enterprise-grade audit template and execution management with:
- Full CRUD for templates, sections, questions
- Audit event logging on all mutations
- Mass assignment protection on update endpoints
- Ownership verification on mutations

All business logic and data access is delegated to
:class:`~src.domain.services.audit_service.AuditService`.
"""

from datetime import timedelta
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query, status

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession, require_permission
from src.domain.models.user import User
from src.api.schemas.audit import (
    ArchiveTemplateResponse,
    AuditFindingCreate,
    AuditFindingListResponse,
    AuditFindingResponse,
    AuditFindingUpdate,
    AuditQuestionCreate,
    AuditQuestionResponse,
    AuditQuestionUpdate,
    AuditResponseCreate,
    AuditResponseResponse,
    AuditResponseUpdate,
    AuditRunCreate,
    AuditRunDetailResponse,
    AuditRunListResponse,
    AuditRunResponse,
    AuditRunUpdate,
    AuditSectionCreate,
    AuditSectionResponse,
    AuditSectionUpdate,
    AuditTemplateCreate,
    AuditTemplateDetailResponse,
    AuditTemplateListResponse,
    AuditTemplateResponse,
    AuditTemplateUpdate,
    PurgeExpiredTemplatesResponse,
)
from src.api.schemas.links import build_collection_links, build_resource_links
from src.api.utils.pagination import PaginationParams
from src.domain.services.audit_service import AuditService

router = APIRouter()


# ============== Template Endpoints ==============


@router.get("/templates", response_model=AuditTemplateListResponse)
async def list_templates(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    search: Optional[str] = None,
    category: Optional[str] = None,
    audit_type: Optional[str] = None,
    is_published: Optional[bool] = None,
) -> Any:
    """List all audit templates with pagination and filtering."""
    service = AuditService(db)
    result = await service.list_templates(
        current_user.tenant_id,
        page=params.page,
        page_size=params.page_size,
        search=search,
        category=category,
        audit_type=audit_type,
        is_published=is_published,
    )
    return {
        "items": result.items,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "pages": result.pages,
        "links": build_collection_links("audits/templates", result.page, result.page_size, result.pages),
    }


@router.post("/templates", response_model=AuditTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: AuditTemplateCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> AuditTemplateResponse:
    """Create a new audit template."""
    service = AuditService(db)
    template = await service.create_template(
        template_data.model_dump(exclude={"standard_ids"}),
        standard_ids=template_data.standard_ids,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    return AuditTemplateResponse.model_validate(template)


@router.get("/templates/archived", response_model=AuditTemplateListResponse)
async def list_archived_templates(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
) -> Any:
    """List archived templates that are within the 30-day recovery window."""
    service = AuditService(db)
    result = await service.list_archived_templates(
        current_user.tenant_id,
        page=params.page,
        page_size=params.page_size,
    )
    return {
        "items": result.items,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "pages": result.pages,
        "links": build_collection_links(
            "audits/templates/archived",
            result.page,
            result.page_size,
            result.pages,
        ),
    }


@router.post("/templates/purge-expired", response_model=PurgeExpiredTemplatesResponse)
async def purge_expired_templates(
    db: DbSession,
    current_user: CurrentSuperuser,
) -> dict:
    """Purge templates archived more than 30 days ago (superuser only).

    This can also be called by a scheduled cron job.
    """
    service = AuditService(db)
    purged_count, purged_names = await service.purge_expired_templates(
        current_user.tenant_id,
        current_user.id,
    )
    return {
        "purged_count": purged_count,
        "purged_templates": purged_names,
    }


@router.get("/templates/{template_id}", response_model=AuditTemplateDetailResponse)
async def get_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditTemplateDetailResponse:
    """Get a specific audit template with sections and questions."""
    service = AuditService(db)
    template = await service.get_template_detail(template_id, current_user.tenant_id)

    response = AuditTemplateDetailResponse.model_validate(template)
    response.section_count = len(template.sections)
    response.question_count = len(template.questions)
    response.links = build_resource_links("", "audits/templates", template_id)
    return response


@router.patch("/templates/{template_id}", response_model=AuditTemplateResponse)
async def update_template(
    template_id: int,
    template_data: AuditTemplateUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> AuditTemplateResponse:
    """Update an audit template."""
    service = AuditService(db)
    template = await service.update_template(
        template_id,
        template_data.model_dump(exclude_unset=True),
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
    )
    return AuditTemplateResponse.model_validate(template)


@router.post("/templates/{template_id}/publish", response_model=AuditTemplateResponse)
async def publish_template(
    template_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> AuditTemplateResponse:
    """Publish an audit template, making it available for use."""
    service = AuditService(db)
    template = await service.publish_template(
        template_id,
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
    )
    return AuditTemplateResponse.model_validate(template)


@router.post(
    "/templates/{template_id}/clone", response_model=AuditTemplateResponse, status_code=status.HTTP_201_CREATED
)
async def clone_template(
    template_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> AuditTemplateResponse:
    """Clone an existing audit template."""
    service = AuditService(db)
    cloned = await service.clone_template(
        template_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    return AuditTemplateResponse.model_validate(cloned)


@router.delete("/templates/{template_id}", status_code=status.HTTP_200_OK, response_model=ArchiveTemplateResponse)
async def archive_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> dict:
    """Archive an audit template (two-stage delete).

    Stage 1: Template is moved to the archive for 30 days.
    Stage 2: After 30 days, a purge job permanently deletes it.
    Archived templates can be restored within the 30-day window.
    """
    service = AuditService(db)
    template = await service.archive_template(
        template_id,
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
    )
    return {
        "message": f"Template '{template.name}' moved to archive. It can be restored within 30 days.",
        "archived_at": template.archived_at.isoformat(),
        "expires_at": (template.archived_at + timedelta(days=30)).isoformat(),
    }


@router.post("/templates/{template_id}/restore", response_model=AuditTemplateResponse)
async def restore_template(
    template_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> AuditTemplateResponse:
    """Restore an archived template back to active status."""
    service = AuditService(db)
    template = await service.restore_template(
        template_id,
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
    )
    return AuditTemplateResponse.model_validate(template)


@router.delete("/templates/{template_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
async def permanently_delete_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Permanently delete an archived template (superuser only).

    Only works on templates that are already archived.
    """
    service = AuditService(db)
    await service.permanently_delete_template(
        template_id,
        tenant_id=current_user.tenant_id,
        actor_user_id=current_user.id,
    )


# ============== Section Endpoints ==============


@router.post(
    "/templates/{template_id}/sections", response_model=AuditSectionResponse, status_code=status.HTTP_201_CREATED
)
async def create_section(
    template_id: int,
    section_data: AuditSectionCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> AuditSectionResponse:
    """Create a new section in an audit template."""
    service = AuditService(db)
    section = await service.create_section(
        template_id,
        section_data.model_dump(),
        tenant_id=current_user.tenant_id,
    )
    return AuditSectionResponse.model_validate(section)


@router.patch("/sections/{section_id}", response_model=AuditSectionResponse)
async def update_section(
    section_id: int,
    section_data: AuditSectionUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> AuditSectionResponse:
    """Update an audit section."""
    service = AuditService(db)
    section = await service.update_section(
        section_id,
        section_data.model_dump(exclude_unset=True),
        tenant_id=current_user.tenant_id,
    )
    return AuditSectionResponse.model_validate(section)


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Soft delete an audit section."""
    service = AuditService(db)
    await service.delete_section(section_id, tenant_id=current_user.tenant_id)


# ============== Question Endpoints ==============


@router.post(
    "/templates/{template_id}/questions", response_model=AuditQuestionResponse, status_code=status.HTTP_201_CREATED
)
async def create_question(
    template_id: int,
    question_data: AuditQuestionCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> AuditQuestionResponse:
    """Create a new question in an audit template."""
    service = AuditService(db)
    question = await service.create_question(
        template_id,
        question_data.model_dump(),
        tenant_id=current_user.tenant_id,
    )
    return AuditQuestionResponse.model_validate(question)


@router.patch("/questions/{question_id}", response_model=AuditQuestionResponse)
async def update_question(
    question_id: int,
    question_data: AuditQuestionUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> AuditQuestionResponse:
    """Update an audit question."""
    service = AuditService(db)
    question = await service.update_question(
        question_id,
        question_data.model_dump(exclude_unset=True),
        tenant_id=current_user.tenant_id,
    )
    return AuditQuestionResponse.model_validate(question)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Soft delete an audit question."""
    service = AuditService(db)
    await service.delete_question(question_id, tenant_id=current_user.tenant_id)


# ============== Audit Run Endpoints ==============


@router.get("/runs", response_model=AuditRunListResponse)
async def list_runs(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, alias="status"),
    template_id: Optional[int] = None,
    assigned_to_id: Optional[int] = None,
) -> Any:
    """List all audit runs with pagination and filtering."""
    service = AuditService(db)
    result = await service.list_runs(
        current_user.tenant_id,
        page=params.page,
        page_size=params.page_size,
        status_filter=status_filter,
        template_id=template_id,
        assigned_to_id=assigned_to_id,
    )
    return {
        "items": result.items,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "pages": result.pages,
        "links": build_collection_links("audits/runs", result.page, result.page_size, result.pages),
    }


@router.post("/runs", response_model=AuditRunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    run_data: AuditRunCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> AuditRunResponse:
    """Create a new audit run from a template."""
    service = AuditService(db)
    run = await service.create_run(
        run_data.model_dump(),
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    return AuditRunResponse.model_validate(run)


@router.get("/runs/{run_id}", response_model=AuditRunDetailResponse)
async def get_run(
    run_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditRunDetailResponse:
    """Get a specific audit run with responses and findings."""
    service = AuditService(db)
    detail = await service.get_run_detail(run_id, current_user.tenant_id)

    response = AuditRunDetailResponse.model_validate(detail.run)
    response.template_name = detail.template_name
    response.completion_percentage = detail.completion_percentage
    response.links = build_resource_links("", "audits/runs", run_id)
    return response


@router.patch("/runs/{run_id}", response_model=AuditRunResponse)
async def update_run(
    run_id: int,
    run_data: AuditRunUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> AuditRunResponse:
    """Update an audit run."""
    service = AuditService(db)
    run = await service.update_run(
        run_id,
        run_data.model_dump(exclude_unset=True),
        tenant_id=current_user.tenant_id,
    )
    return AuditRunResponse.model_validate(run)


@router.post("/runs/{run_id}/start", response_model=AuditRunResponse)
async def start_run(
    run_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> AuditRunResponse:
    """Start an audit run."""
    service = AuditService(db)
    run = await service.start_run(run_id, tenant_id=current_user.tenant_id)
    return AuditRunResponse.model_validate(run)


@router.post("/runs/{run_id}/complete", response_model=AuditRunResponse)
async def complete_run(
    run_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> AuditRunResponse:
    """Complete an audit run and calculate scores."""
    service = AuditService(db)
    run = await service.complete_run(run_id, tenant_id=current_user.tenant_id)
    return AuditRunResponse.model_validate(run)


# ============== Response Endpoints ==============


@router.post("/runs/{run_id}/responses", response_model=AuditResponseResponse, status_code=status.HTTP_201_CREATED)
async def create_response(
    run_id: int,
    response_data: AuditResponseCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> AuditResponseResponse:
    """Submit a response to an audit question."""
    service = AuditService(db)
    response = await service.create_audit_response(
        run_id,
        response_data.model_dump(),
        tenant_id=current_user.tenant_id,
    )
    return AuditResponseResponse.model_validate(response)


@router.patch("/responses/{response_id}", response_model=AuditResponseResponse)
async def update_response(
    response_id: int,
    response_data: AuditResponseUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> AuditResponseResponse:
    """Update an audit response."""
    service = AuditService(db)
    response = await service.update_audit_response(
        response_id,
        response_data.model_dump(exclude_unset=True),
        tenant_id=current_user.tenant_id,
    )
    return AuditResponseResponse.model_validate(response)


# ============== Finding Endpoints ==============


@router.get("/findings", response_model=AuditFindingListResponse)
async def list_findings(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = None,
    run_id: Optional[int] = None,
) -> Any:
    """List all audit findings with pagination and filtering."""
    service = AuditService(db)
    result = await service.list_findings(
        current_user.tenant_id,
        page=params.page,
        page_size=params.page_size,
        status_filter=status_filter,
        severity=severity,
        run_id=run_id,
    )
    return {
        "items": result.items,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "pages": result.pages,
        "links": build_collection_links("audits/findings", result.page, result.page_size, result.pages),
    }


@router.post("/runs/{run_id}/findings", response_model=AuditFindingResponse, status_code=status.HTTP_201_CREATED)
async def create_finding(
    run_id: int,
    finding_data: AuditFindingCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> AuditFindingResponse:
    """Create a new finding for an audit run."""
    service = AuditService(db)
    finding = await service.create_finding(
        run_id,
        finding_data.model_dump(),
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    return AuditFindingResponse.model_validate(finding)


@router.patch("/findings/{finding_id}", response_model=AuditFindingResponse)
async def update_finding(
    finding_id: int,
    finding_data: AuditFindingUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> AuditFindingResponse:
    """Update an audit finding."""
    service = AuditService(db)
    finding = await service.update_finding(
        finding_id,
        finding_data.model_dump(exclude_unset=True),
        tenant_id=current_user.tenant_id,
    )
    return AuditFindingResponse.model_validate(finding)
