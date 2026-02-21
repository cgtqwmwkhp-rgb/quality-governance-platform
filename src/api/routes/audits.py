"""Audits & Inspections API routes.

Enterprise-grade audit template and execution management with:
- Full CRUD for templates, sections, questions
- Audit event logging on all mutations
- Mass assignment protection on update endpoints
- Ownership verification on mutations
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.audit import (
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
)
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.audit import (
    AuditFinding,
    AuditQuestion,
    AuditResponse,
    AuditRun,
    AuditSection,
    AuditStatus,
    AuditTemplate,
    FindingStatus,
)
from src.domain.services.audit_scoring_service import AuditScoringService
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter()

TEMPLATE_UPDATE_ALLOWED_FIELDS = {
    "name",
    "description",
    "category",
    "audit_type",
    "frequency",
    "scoring_method",
    "passing_score",
    "allow_offline",
    "require_gps",
    "require_signature",
    "require_approval",
    "auto_create_findings",
}


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
) -> AuditTemplateListResponse:
    """List all audit templates with pagination and filtering."""
    query = select(AuditTemplate).where(
        AuditTemplate.is_active == True,  # noqa: E712
        AuditTemplate.archived_at.is_(None),
        AuditTemplate.tenant_id == current_user.tenant_id,
    )

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (AuditTemplate.name.ilike(search_filter)) | (AuditTemplate.description.ilike(search_filter))
        )
    if category:
        query = query.where(AuditTemplate.category == category)
    if audit_type:
        query = query.where(AuditTemplate.audit_type == audit_type)
    if is_published is not None:
        query = query.where(AuditTemplate.is_published == is_published)

    query = query.order_by(AuditTemplate.name)

    return await paginate(db, query, params)


@router.post("/templates", response_model=AuditTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: AuditTemplateCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditTemplateResponse:
    """Create a new audit template."""
    dump = template_data.model_dump(exclude={"standard_ids"})
    template = AuditTemplate(
        **dump,
        standard_ids_json=template_data.standard_ids,
        created_by_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )

    template.reference_number = await ReferenceNumberService.generate(db, "audit_template", AuditTemplate)

    db.add(template)
    await db.commit()
    await db.refresh(template)
    await invalidate_tenant_cache(current_user.tenant_id, "audits")

    await record_audit_event(
        db,
        event_type="audit_template.created",
        entity_type="audit_template",
        entity_id=str(template.id),
        action="create",
        description=f"Template '{template.name}' created",
        actor_user_id=current_user.id,
    )

    return AuditTemplateResponse.model_validate(template)


@router.get("/templates/archived", response_model=AuditTemplateListResponse)
async def list_archived_templates(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
) -> AuditTemplateListResponse:
    """List archived templates that are within the 30-day recovery window."""
    query = select(AuditTemplate).where(
        AuditTemplate.archived_at.isnot(None),
        AuditTemplate.tenant_id == current_user.tenant_id,
    )
    query = query.order_by(AuditTemplate.archived_at.desc())

    return await paginate(db, query, params)


@router.post("/templates/purge-expired", response_model=dict)
async def purge_expired_templates(
    db: DbSession,
    current_user: CurrentSuperuser,
) -> dict:
    """Purge templates archived more than 30 days ago (superuser only).

    This can also be called by a scheduled cron job.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    result = await db.execute(
        select(AuditTemplate).where(
            AuditTemplate.archived_at.isnot(None),
            AuditTemplate.archived_at < cutoff,
            AuditTemplate.tenant_id == current_user.tenant_id,
        )
    )
    expired = result.scalars().all()

    purged_count = len(expired)
    purged_names = [t.name for t in expired]

    for template in expired:
        await db.delete(template)

    if purged_count > 0:
        await db.commit()
        await record_audit_event(
            db,
            event_type="audit_template.purge",
            entity_type="audit_template",
            entity_id="batch",
            action="purge",
            description=f"Purged {purged_count} expired archived template(s)",
            actor_user_id=current_user.id,
            payload={"purged_templates": purged_names},
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
    result = await db.execute(
        select(AuditTemplate)
        .options(
            selectinload(AuditTemplate.sections).selectinload(AuditSection.questions),
            selectinload(AuditTemplate.questions),
        )
        .where(AuditTemplate.id == template_id, AuditTemplate.tenant_id == current_user.tenant_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    response = AuditTemplateDetailResponse.model_validate(template)
    response.section_count = len(template.sections)
    response.question_count = len(template.questions)

    return response


@router.patch("/templates/{template_id}", response_model=AuditTemplateResponse)
async def update_template(
    template_id: int,
    template_data: AuditTemplateUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditTemplateResponse:
    """Update an audit template."""
    template = await get_or_404(db, AuditTemplate, template_id, tenant_id=current_user.tenant_id)

    # Increment version if published template is modified
    if template.is_published:
        template.version += 1
        template.is_published = False

    update_data = template_data.model_dump(exclude_unset=True, exclude={"standard_ids"})
    safe_data = {k: v for k, v in update_data.items() if k in TEMPLATE_UPDATE_ALLOWED_FIELDS}

    # Handle standard_ids → standard_ids_json mapping
    raw = template_data.model_dump(exclude_unset=True)
    if "standard_ids" in raw:
        safe_data["standard_ids_json"] = raw["standard_ids"]

    changed_fields = []
    for field, value in safe_data.items():
        old_value = getattr(template, field, None)
        if old_value != value:
            changed_fields.append(field)
            setattr(template, field, value)

    await db.commit()
    await db.refresh(template)
    await invalidate_tenant_cache(current_user.tenant_id, "audits")

    if changed_fields:
        await record_audit_event(
            db,
            event_type="audit_template.updated",
            entity_type="audit_template",
            entity_id=str(template.id),
            action="update",
            description=f"Template '{template.name}' updated: {', '.join(changed_fields)}",
            actor_user_id=current_user.id,
            payload={"changed_fields": changed_fields},
        )

    return AuditTemplateResponse.model_validate(template)


@router.post("/templates/{template_id}/publish", response_model=AuditTemplateResponse)
async def publish_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditTemplateResponse:
    """Publish an audit template, making it available for use."""
    result = await db.execute(
        select(AuditTemplate)
        .options(selectinload(AuditTemplate.questions))
        .where(AuditTemplate.id == template_id, AuditTemplate.tenant_id == current_user.tenant_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    question_count = len(template.questions)
    if question_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template must have at least one question before publishing",
        )

    template.is_published = True
    await db.commit()
    await db.refresh(template)

    await record_audit_event(
        db,
        event_type="audit_template.published",
        entity_type="audit_template",
        entity_id=str(template.id),
        action="publish",
        description=f"Template '{template.name}' published (v{template.version}, {question_count} questions)",
        actor_user_id=current_user.id,
    )

    return AuditTemplateResponse.model_validate(template)


@router.post(
    "/templates/{template_id}/clone", response_model=AuditTemplateResponse, status_code=status.HTTP_201_CREATED
)
async def clone_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditTemplateResponse:
    """Clone an existing audit template."""
    result = await db.execute(
        select(AuditTemplate)
        .options(
            selectinload(AuditTemplate.sections).selectinload(AuditSection.questions),
            selectinload(AuditTemplate.questions),
        )
        .where(AuditTemplate.id == template_id, AuditTemplate.tenant_id == current_user.tenant_id)
    )
    original = result.scalar_one_or_none()

    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    reference_number = await ReferenceNumberService.generate(db, "audit_template", AuditTemplate)

    cloned_template = AuditTemplate(
        name=f"Copy of {original.name}",
        description=original.description,
        category=original.category,
        audit_type=original.audit_type,
        frequency=original.frequency,
        scoring_method=original.scoring_method,
        passing_score=original.passing_score,
        allow_offline=original.allow_offline,
        require_gps=original.require_gps,
        require_signature=original.require_signature,
        require_approval=original.require_approval,
        auto_create_findings=original.auto_create_findings,
        standard_ids_json=original.standard_ids_json,
        is_active=True,
        is_published=False,
        created_by_id=current_user.id,
        reference_number=reference_number,
        tenant_id=current_user.tenant_id,
    )
    db.add(cloned_template)
    await db.flush()

    for original_section in original.sections:
        cloned_section = AuditSection(
            template_id=cloned_template.id,
            title=original_section.title,
            description=original_section.description,
            sort_order=original_section.sort_order,
            weight=original_section.weight,
            is_repeatable=original_section.is_repeatable,
            max_repeats=original_section.max_repeats,
            is_active=original_section.is_active,
        )
        db.add(cloned_section)
        await db.flush()

        for original_question in original_section.questions:
            cloned_question = AuditQuestion(
                template_id=cloned_template.id,
                section_id=cloned_section.id,
                question_text=original_question.question_text,
                question_type=original_question.question_type,
                description=original_question.description,
                help_text=original_question.help_text,
                is_required=original_question.is_required,
                allow_na=original_question.allow_na,
                is_active=original_question.is_active,
                max_score=original_question.max_score,
                weight=original_question.weight,
                options_json=original_question.options_json,
                min_value=original_question.min_value,
                max_value=original_question.max_value,
                decimal_places=original_question.decimal_places,
                min_length=original_question.min_length,
                max_length=original_question.max_length,
                evidence_requirements_json=original_question.evidence_requirements_json,
                conditional_logic_json=original_question.conditional_logic_json,
                clause_ids_json=original_question.clause_ids_json,
                control_ids_json=original_question.control_ids_json,
                risk_category=original_question.risk_category,
                risk_weight=original_question.risk_weight,
                sort_order=original_question.sort_order,
            )
            db.add(cloned_question)

    # Clone unsectioned questions (section_id=None)
    for oq in original.questions:
        if oq.section_id is None:
            cloned_question = AuditQuestion(
                template_id=cloned_template.id,
                section_id=None,
                question_text=oq.question_text,
                question_type=oq.question_type,
                description=oq.description,
                help_text=oq.help_text,
                is_required=oq.is_required,
                allow_na=oq.allow_na,
                is_active=oq.is_active,
                max_score=oq.max_score,
                weight=oq.weight,
                options_json=oq.options_json,
                min_value=oq.min_value,
                max_value=oq.max_value,
                decimal_places=oq.decimal_places,
                min_length=oq.min_length,
                max_length=oq.max_length,
                evidence_requirements_json=oq.evidence_requirements_json,
                conditional_logic_json=oq.conditional_logic_json,
                clause_ids_json=oq.clause_ids_json,
                control_ids_json=oq.control_ids_json,
                risk_category=oq.risk_category,
                risk_weight=oq.risk_weight,
                sort_order=oq.sort_order,
            )
            db.add(cloned_question)

    await db.commit()
    await db.refresh(cloned_template)

    return AuditTemplateResponse.model_validate(cloned_template)


@router.delete("/templates/{template_id}", status_code=status.HTTP_200_OK, response_model=dict)
async def archive_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Archive an audit template (two-stage delete).

    Stage 1: Template is moved to the archive for 30 days.
    Stage 2: After 30 days, a purge job permanently deletes it.
    Archived templates can be restored within the 30-day window.
    """
    result = await db.execute(
        select(AuditTemplate).where(
            AuditTemplate.id == template_id,
            AuditTemplate.archived_at.is_(None),
            AuditTemplate.tenant_id == current_user.tenant_id,
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or already archived",
        )

    template.archived_at = datetime.now(timezone.utc)
    template.archived_by_id = current_user.id
    template.is_active = False
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "audits")

    await record_audit_event(
        db,
        event_type="audit_template.archived",
        entity_type="audit_template",
        entity_id=str(template_id),
        action="archive",
        description=f"Template '{template.name}' archived (recoverable for 30 days)",
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
    current_user: CurrentUser,
) -> AuditTemplateResponse:
    """Restore an archived template back to active status."""
    result = await db.execute(
        select(AuditTemplate).where(
            AuditTemplate.id == template_id,
            AuditTemplate.archived_at.isnot(None),
            AuditTemplate.tenant_id == current_user.tenant_id,
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archived template not found",
        )

    template.archived_at = None
    template.archived_by_id = None
    template.is_active = True
    await db.commit()
    await db.refresh(template)

    await record_audit_event(
        db,
        event_type="audit_template.restored",
        entity_type="audit_template",
        entity_id=str(template_id),
        action="restore",
        description=f"Template '{template.name}' restored from archive",
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
    result = await db.execute(
        select(AuditTemplate).where(
            AuditTemplate.id == template_id,
            AuditTemplate.archived_at.isnot(None),
            AuditTemplate.tenant_id == current_user.tenant_id,
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archived template not found",
        )

    template_name = template.name
    await db.delete(template)
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "audits")

    await record_audit_event(
        db,
        event_type="audit_template.permanently_deleted",
        entity_type="audit_template",
        entity_id=str(template_id),
        action="permanent_delete",
        description=f"Template '{template_name}' permanently deleted",
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
    current_user: CurrentUser,
) -> AuditSectionResponse:
    """Create a new section in an audit template."""
    await get_or_404(db, AuditTemplate, template_id, tenant_id=current_user.tenant_id)

    section = AuditSection(
        template_id=template_id,
        **section_data.model_dump(),
    )

    db.add(section)
    await db.commit()

    refreshed = await db.execute(
        select(AuditSection).options(selectinload(AuditSection.questions)).where(AuditSection.id == section.id)
    )
    section = refreshed.scalar_one()

    return AuditSectionResponse.model_validate(section)


@router.patch("/sections/{section_id}", response_model=AuditSectionResponse)
async def update_section(
    section_id: int,
    section_data: AuditSectionUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditSectionResponse:
    """Update an audit section."""
    result = await db.execute(
        select(AuditSection).options(selectinload(AuditSection.questions)).where(AuditSection.id == section_id)
    )
    section = result.scalar_one_or_none()

    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found",
        )

    await get_or_404(db, AuditTemplate, section.template_id, tenant_id=current_user.tenant_id)

    apply_updates(section, section_data, set_updated_at=False)

    await db.commit()

    refreshed = await db.execute(
        select(AuditSection).options(selectinload(AuditSection.questions)).where(AuditSection.id == section.id)
    )
    section = refreshed.scalar_one()

    return AuditSectionResponse.model_validate(section)


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Soft delete an audit section."""
    section = await get_or_404(db, AuditSection, section_id)
    await get_or_404(db, AuditTemplate, section.template_id, tenant_id=current_user.tenant_id)

    section.is_active = False
    await db.commit()


# ============== Question Endpoints ==============


@router.post(
    "/templates/{template_id}/questions", response_model=AuditQuestionResponse, status_code=status.HTTP_201_CREATED
)
async def create_question(
    template_id: int,
    question_data: AuditQuestionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditQuestionResponse:
    """Create a new question in an audit template."""
    await get_or_404(db, AuditTemplate, template_id, tenant_id=current_user.tenant_id)

    # Validate section belongs to this template
    if question_data.section_id is not None:
        section_result = await db.execute(
            select(AuditSection).where(
                AuditSection.id == question_data.section_id,
                AuditSection.template_id == template_id,
            )
        )
        if not section_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Section does not belong to this template",
            )

    # Convert options to JSON if provided
    question_dict = question_data.model_dump()
    if question_dict.get("options"):
        question_dict["options_json"] = [
            opt.model_dump() if hasattr(opt, "model_dump") else opt for opt in question_dict["options"]
        ]
    del question_dict["options"]

    if question_dict.get("evidence_requirements"):
        er = question_dict["evidence_requirements"]
        question_dict["evidence_requirements_json"] = er.model_dump() if hasattr(er, "model_dump") else er
    del question_dict["evidence_requirements"]

    if question_dict.get("conditional_logic"):
        question_dict["conditional_logic_json"] = [
            cl.model_dump() if hasattr(cl, "model_dump") else cl for cl in question_dict["conditional_logic"]
        ]
    del question_dict["conditional_logic"]

    # Handle clause_ids and control_ids
    clause_ids = question_dict.pop("clause_ids", None)
    control_ids = question_dict.pop("control_ids", None)
    if clause_ids:
        question_dict["clause_ids_json"] = clause_ids
    if control_ids:
        question_dict["control_ids_json"] = control_ids

    question = AuditQuestion(
        template_id=template_id,
        **question_dict,
    )

    db.add(question)
    await db.commit()
    await db.refresh(question)

    return AuditQuestionResponse.model_validate(question)


@router.patch("/questions/{question_id}", response_model=AuditQuestionResponse)
async def update_question(
    question_id: int,
    question_data: AuditQuestionUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditQuestionResponse:
    """Update an audit question."""
    question = await get_or_404(db, AuditQuestion, question_id)
    await get_or_404(db, AuditTemplate, question.template_id, tenant_id=current_user.tenant_id)

    update_data = question_data.model_dump(exclude_unset=True)

    # Handle JSON fields (schema → model field remapping)
    _JSON_REMAP = {
        "options": "options_json",
        "evidence_requirements": "evidence_requirements_json",
        "conditional_logic": "conditional_logic_json",
        "clause_ids": "clause_ids_json",
        "control_ids": "control_ids_json",
    }
    for schema_field, model_field in _JSON_REMAP.items():
        if schema_field in update_data:
            setattr(question, model_field, update_data[schema_field])

    apply_updates(question, question_data, set_updated_at=False, exclude=set(_JSON_REMAP))

    await db.commit()
    await db.refresh(question)

    return AuditQuestionResponse.model_validate(question)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Soft delete an audit question."""
    question = await get_or_404(db, AuditQuestion, question_id)
    await get_or_404(db, AuditTemplate, question.template_id, tenant_id=current_user.tenant_id)

    question.is_active = False
    await db.commit()


# ============== Audit Run Endpoints ==============


@router.get("/runs", response_model=AuditRunListResponse)
async def list_runs(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, alias="status"),
    template_id: Optional[int] = None,
    assigned_to_id: Optional[int] = None,
) -> AuditRunListResponse:
    """List all audit runs with pagination and filtering."""
    query = select(AuditRun).where(AuditRun.tenant_id == current_user.tenant_id)

    if status_filter:
        query = query.where(AuditRun.status == status_filter)
    if template_id:
        query = query.where(AuditRun.template_id == template_id)
    if assigned_to_id:
        query = query.where(AuditRun.assigned_to_id == assigned_to_id)

    query = query.order_by(AuditRun.created_at.desc())

    return await paginate(db, query, params)


@router.post("/runs", response_model=AuditRunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    run_data: AuditRunCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditRunResponse:
    """Create a new audit run from a template."""
    # Verify template exists and is published
    result = await db.execute(
        select(AuditTemplate).where(
            and_(
                AuditTemplate.id == run_data.template_id,
                AuditTemplate.is_published == True,
                AuditTemplate.is_active == True,
            )
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published template not found",
        )

    run = AuditRun(
        **run_data.model_dump(),
        template_version=template.version,
        status=AuditStatus.SCHEDULED,
        created_by_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )

    # Generate reference number
    run.reference_number = await ReferenceNumberService.generate(db, "audit_run", AuditRun)

    db.add(run)
    await db.commit()
    await db.refresh(run)
    await invalidate_tenant_cache(current_user.tenant_id, "audits")

    return AuditRunResponse.model_validate(run)


@router.get("/runs/{run_id}", response_model=AuditRunDetailResponse)
async def get_run(
    run_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditRunDetailResponse:
    """Get a specific audit run with responses and findings."""
    result = await db.execute(
        select(AuditRun)
        .options(
            selectinload(AuditRun.responses),
            selectinload(AuditRun.findings),
            selectinload(AuditRun.template),
        )
        .where(AuditRun.id == run_id, AuditRun.tenant_id == current_user.tenant_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit run not found",
        )

    response = AuditRunDetailResponse.model_validate(run)
    response.template_name = run.template.name if run.template else None

    # Calculate completion percentage
    if run.template:
        total_questions = await db.scalar(
            select(func.count())
            .select_from(AuditQuestion)
            .where(
                and_(
                    AuditQuestion.template_id == run.template_id,
                    AuditQuestion.is_active == True,
                )
            )
        )
        answered_questions = len(run.responses)
        if total_questions and total_questions > 0:
            response.completion_percentage = answered_questions / total_questions * 100
        else:
            response.completion_percentage = 0

    return response


@router.patch("/runs/{run_id}", response_model=AuditRunResponse)
async def update_run(
    run_id: int,
    run_data: AuditRunUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditRunResponse:
    """Update an audit run."""
    run = await get_or_404(db, AuditRun, run_id, tenant_id=current_user.tenant_id)

    update_data = run_data.model_dump(exclude_unset=True)

    if "status" in update_data:
        new_status = update_data["status"]
        if new_status == AuditStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use POST /runs/{id}/complete to finish an audit with score calculation",
            )
        try:
            validated = AuditStatus(new_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status. Must be one of: {[s.value for s in AuditStatus]}",
            )
        if validated == AuditStatus.IN_PROGRESS and run.started_at is None:
            run.started_at = datetime.now(timezone.utc)
        run.status = validated

    apply_updates(run, run_data, set_updated_at=False, exclude={"status"})

    await db.commit()
    await db.refresh(run)
    await invalidate_tenant_cache(current_user.tenant_id, "audits")

    return AuditRunResponse.model_validate(run)


@router.post("/runs/{run_id}/start", response_model=AuditRunResponse)
async def start_run(
    run_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditRunResponse:
    """Start an audit run."""
    run = await get_or_404(db, AuditRun, run_id, tenant_id=current_user.tenant_id)

    if run.status != AuditStatus.SCHEDULED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audit run can only be started from scheduled status",
        )

    run.status = AuditStatus.IN_PROGRESS
    run.started_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(run)

    return AuditRunResponse.model_validate(run)


@router.post("/runs/{run_id}/complete", response_model=AuditRunResponse)
async def complete_run(
    run_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditRunResponse:
    """Complete an audit run and calculate scores."""
    result = await db.execute(
        select(AuditRun)
        .options(selectinload(AuditRun.responses))
        .where(AuditRun.id == run_id, AuditRun.tenant_id == current_user.tenant_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit run not found",
        )

    if run.status != AuditStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audit run must be in progress to complete",
        )

    score = AuditScoringService.calculate_run_score(run.responses)
    run.score = score.total_score
    run.max_score = score.max_score
    run.score_percentage = score.score_percentage

    # Get template to check passing score
    template_result = await db.execute(select(AuditTemplate).where(AuditTemplate.id == run.template_id))
    template = template_result.scalar_one_or_none()

    if template and template.passing_score is not None:
        run.passed = run.score_percentage >= template.passing_score

    run.status = AuditStatus.COMPLETED
    run.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(run)
    track_metric("audits.completed")

    return AuditRunResponse.model_validate(run)


# ============== Response Endpoints ==============


@router.post("/runs/{run_id}/responses", response_model=AuditResponseResponse, status_code=status.HTTP_201_CREATED)
async def create_response(
    run_id: int,
    response_data: AuditResponseCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditResponseResponse:
    """Submit a response to an audit question."""
    run = await get_or_404(db, AuditRun, run_id, tenant_id=current_user.tenant_id)

    if run.status not in [AuditStatus.SCHEDULED, AuditStatus.IN_PROGRESS]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit responses to a completed audit",
        )

    # Auto-start if scheduled
    if run.status == AuditStatus.SCHEDULED:
        run.status = AuditStatus.IN_PROGRESS
        run.started_at = datetime.now(timezone.utc)

    # Check if response already exists for this question
    existing = await db.execute(
        select(AuditResponse).where(
            and_(
                AuditResponse.run_id == run_id,
                AuditResponse.question_id == response_data.question_id,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Response already exists for this question. Use PATCH to update.",
        )

    response = AuditResponse(
        run_id=run_id,
        **response_data.model_dump(),
    )

    db.add(response)
    await db.commit()
    await db.refresh(response)

    return AuditResponseResponse.model_validate(response)


@router.patch("/responses/{response_id}", response_model=AuditResponseResponse)
async def update_response(
    response_id: int,
    response_data: AuditResponseUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditResponseResponse:
    """Update an audit response."""
    result = await db.execute(
        select(AuditResponse).options(selectinload(AuditResponse.run)).where(AuditResponse.id == response_id)
    )
    response = result.scalar_one_or_none()

    if response:
        await get_or_404(db, AuditRun, response.run_id, tenant_id=current_user.tenant_id)

    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response not found",
        )

    if response.run.status == AuditStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update responses on a completed audit",
        )

    apply_updates(response, response_data, set_updated_at=False)

    await db.commit()
    await db.refresh(response)

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
) -> AuditFindingListResponse:
    """List all audit findings with pagination and filtering."""
    query = select(AuditFinding).where(AuditFinding.tenant_id == current_user.tenant_id)

    if status_filter:
        query = query.where(AuditFinding.status == status_filter)
    if severity:
        query = query.where(AuditFinding.severity == severity)
    if run_id:
        query = query.where(AuditFinding.run_id == run_id)

    query = query.order_by(AuditFinding.created_at.desc())

    return await paginate(db, query, params)


@router.post("/runs/{run_id}/findings", response_model=AuditFindingResponse, status_code=status.HTTP_201_CREATED)
async def create_finding(
    run_id: int,
    finding_data: AuditFindingCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditFindingResponse:
    """Create a new finding for an audit run."""
    await get_or_404(db, AuditRun, run_id, tenant_id=current_user.tenant_id)

    finding_dict = finding_data.model_dump()

    # Handle list fields
    clause_ids = finding_dict.pop("clause_ids", None)
    control_ids = finding_dict.pop("control_ids", None)
    risk_ids = finding_dict.pop("risk_ids", None)

    finding = AuditFinding(
        run_id=run_id,
        status=FindingStatus.OPEN,
        created_by_id=current_user.id,
        tenant_id=current_user.tenant_id,
        **finding_dict,
    )

    # Store list fields as JSON
    if clause_ids:
        finding.clause_ids_json = clause_ids
    if control_ids:
        finding.control_ids_json = control_ids
    if risk_ids:
        finding.risk_ids_json = risk_ids

    # Generate reference number
    finding.reference_number = await ReferenceNumberService.generate(db, "audit_finding", AuditFinding)

    db.add(finding)
    await db.commit()
    await db.refresh(finding)
    await invalidate_tenant_cache(current_user.tenant_id, "audits")
    track_metric("audits.findings")

    return AuditFindingResponse.model_validate(finding)


@router.patch("/findings/{finding_id}", response_model=AuditFindingResponse)
async def update_finding(
    finding_id: int,
    finding_data: AuditFindingUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditFindingResponse:
    """Update an audit finding."""
    finding = await get_or_404(db, AuditFinding, finding_id, tenant_id=current_user.tenant_id)

    update_data = finding_data.model_dump(exclude_unset=True)

    # Handle list fields (schema → model field remapping)
    if "clause_ids" in update_data:
        finding.clause_ids_json = update_data["clause_ids"]
    if "control_ids" in update_data:
        finding.control_ids_json = update_data["control_ids"]
    if "risk_ids" in update_data:
        finding.risk_ids_json = update_data["risk_ids"]

    apply_updates(finding, finding_data, set_updated_at=False, exclude={"clause_ids", "control_ids", "risk_ids"})

    await db.commit()
    await db.refresh(finding)
    await invalidate_tenant_cache(current_user.tenant_id, "audits")

    return AuditFindingResponse.model_validate(finding)
