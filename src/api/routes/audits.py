"""Audits & Inspections API routes."""

import html
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
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
from src.infrastructure.monitoring.azure_monitor import StructuredLogger
from src.services.reference_number import ReferenceNumberService

router = APIRouter()
observability_logger = StructuredLogger("audit.observability")


def _decode_html(value: Optional[str]) -> Optional[str]:
    """Decode HTML entities from text fields (e.g. '&amp;' -> '&')."""
    if value is None:
        return None
    return html.unescape(value)


def _decode_option_list(options: Optional[list[Any]]) -> Optional[list[Any]]:
    """Decode HTML entities in question options, preserving shape."""
    if options is None:
        return None

    decoded_options: list[Any] = []
    for option in options:
        if isinstance(option, dict):
            decoded_option = dict(option)
            for key in ("label", "value"):
                if key in decoded_option and isinstance(decoded_option[key], str):
                    decoded_option[key] = html.unescape(decoded_option[key])
            decoded_options.append(decoded_option)
        elif hasattr(option, "label") and hasattr(option, "value"):
            if isinstance(option.label, str):
                option.label = html.unescape(option.label)
            if isinstance(option.value, str):
                option.value = html.unescape(option.value)
            decoded_options.append(option)
        else:
            decoded_options.append(option)
    return decoded_options


def _decode_template_response_entities(response: AuditTemplateResponse) -> AuditTemplateResponse:
    response.name = _decode_html(response.name) or response.name
    response.description = _decode_html(response.description)
    response.category = _decode_html(response.category)
    return response


def _decode_template_detail_response_entities(response: AuditTemplateDetailResponse) -> AuditTemplateDetailResponse:
    response = _decode_template_response_entities(response)
    for section in response.sections:
        section.title = _decode_html(section.title) or section.title
        section.description = _decode_html(section.description)
        for question in section.questions:
            question.question_text = _decode_html(question.question_text) or question.question_text
            question.description = _decode_html(question.description)
            question.help_text = _decode_html(question.help_text)
            question.options = _decode_option_list(question.options)
    return response


def _record_audit_endpoint_event(
    endpoint: str,
    status_code: int,
    duration_ms: float,
    error_class: Optional[str] = None,
) -> None:
    """Emit bounded audit endpoint telemetry for dashboards and alerting."""
    observability_logger.info(
        "audit_endpoint_event",
        endpoint=endpoint,
        status_code=status_code,
        duration_ms=round(duration_ms, 2),
        error_class=error_class or "none",
    )


# ============== Template Endpoints ==============


@router.get("/templates", response_model=AuditTemplateListResponse)
async def list_templates(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    audit_type: Optional[str] = None,
    is_published: Optional[bool] = None,
) -> AuditTemplateListResponse:
    """List all audit templates with pagination and filtering."""
    started = time.perf_counter()
    query = select(AuditTemplate).where(AuditTemplate.is_active == True)

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

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(AuditTemplate.name)

    result = await db.execute(query)
    templates = result.scalars().all()

    response = AuditTemplateListResponse(
        items=[_decode_template_response_entities(AuditTemplateResponse.model_validate(t)) for t in templates],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )
    _record_audit_endpoint_event("GET /api/v1/audits/templates", 200, (time.perf_counter() - started) * 1000)
    return response


@router.post("/templates", response_model=AuditTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: AuditTemplateCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditTemplateResponse:
    """Create a new audit template."""
    template_data_dict = template_data.model_dump(exclude={"standard_ids"})
    for field in ("name", "description", "category"):
        if field in template_data_dict and isinstance(template_data_dict[field], str):
            template_data_dict[field] = html.unescape(template_data_dict[field])

    template = AuditTemplate(
        **template_data_dict,
        created_by_id=current_user.id,
    )

    # Generate reference number
    template.reference_number = await ReferenceNumberService.generate(db, "audit_template", AuditTemplate)

    db.add(template)
    await db.commit()
    await db.refresh(template)

    return _decode_template_response_entities(AuditTemplateResponse.model_validate(template))


@router.get("/templates/{template_id}", response_model=AuditTemplateDetailResponse)
async def get_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditTemplateDetailResponse:
    """Get a specific audit template with sections and questions."""
    result = await db.execute(
        select(AuditTemplate)
        .options(selectinload(AuditTemplate.sections).selectinload(AuditSection.questions))
        .where(AuditTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    response = AuditTemplateDetailResponse.model_validate(template)
    response.section_count = len(template.sections)
    response.question_count = sum(len(s.questions) for s in template.sections)

    return _decode_template_detail_response_entities(response)


@router.patch("/templates/{template_id}", response_model=AuditTemplateResponse)
async def update_template(
    template_id: int,
    template_data: AuditTemplateUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditTemplateResponse:
    """Update an audit template."""
    result = await db.execute(select(AuditTemplate).where(AuditTemplate.id == template_id))
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Increment version if published template is modified
    if template.is_published:
        template.version += 1
        template.is_published = False

    update_data = template_data.model_dump(exclude_unset=True, exclude={"standard_ids"})
    for field in ("name", "description", "category"):
        if field in update_data and isinstance(update_data[field], str):
            update_data[field] = html.unescape(update_data[field])
    for field, value in update_data.items():
        setattr(template, field, value)

    await db.commit()
    await db.refresh(template)

    return _decode_template_response_entities(AuditTemplateResponse.model_validate(template))


@router.post("/templates/{template_id}/publish", response_model=AuditTemplateResponse)
async def publish_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditTemplateResponse:
    """Publish an audit template, making it available for use."""
    result = await db.execute(
        select(AuditTemplate)
        .options(selectinload(AuditTemplate.sections).selectinload(AuditSection.questions))
        .where(AuditTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Validate template has at least one question
    question_count = sum(len(s.questions) for s in template.sections)
    if question_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template must have at least one question before publishing",
        )

    template.is_published = True
    await db.commit()
    await db.refresh(template)

    return _decode_template_response_entities(AuditTemplateResponse.model_validate(template))


@router.post(
    "/templates/{template_id}/clone", response_model=AuditTemplateResponse, status_code=status.HTTP_201_CREATED
)
async def clone_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditTemplateResponse:
    """Clone an existing audit template."""
    # Fetch the original template with all relationships
    result = await db.execute(
        select(AuditTemplate)
        .options(selectinload(AuditTemplate.sections).selectinload(AuditSection.questions))
        .where(AuditTemplate.id == template_id)
    )
    original = result.scalar_one_or_none()

    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Generate reference number for the cloned template
    from src.services.reference_number import ReferenceNumberService

    reference_number = await ReferenceNumberService.generate(db, "TPL", AuditTemplate)

    # Create a new template with copied attributes
    cloned_template = AuditTemplate(
        name=f"Copy of {original.name}",
        description=original.description,
        category=original.category,
        audit_type=original.audit_type,
        scoring_method=original.scoring_method,
        passing_score=original.passing_score,
        is_active=original.is_active,
        is_published=False,  # Clones start as unpublished
        created_by_id=current_user.id,
        reference_number=reference_number,
    )
    db.add(cloned_template)
    await db.flush()  # Get the ID for the cloned template

    # Clone sections and questions
    for original_section in original.sections:
        cloned_section = AuditSection(
            template_id=cloned_template.id,
            title=original_section.title,
            description=original_section.description,
            sort_order=original_section.sort_order,
        )
        db.add(cloned_section)
        await db.flush()  # Get the ID for the cloned section

        for original_question in original_section.questions:
            cloned_question = AuditQuestion(
                template_id=cloned_template.id,
                section_id=cloned_section.id,
                question_text=original_question.question_text,
                question_type=original_question.question_type,
                is_required=original_question.is_required,
                weight=original_question.weight,
                options_json=original_question.options_json,
            )
            db.add(cloned_question)

    await db.commit()
    await db.refresh(cloned_template)

    return _decode_template_response_entities(AuditTemplateResponse.model_validate(cloned_template))


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Soft delete an audit template (superuser only)."""
    result = await db.execute(select(AuditTemplate).where(AuditTemplate.id == template_id))
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    template.is_active = False
    await db.commit()


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
    # Verify template exists
    result = await db.execute(select(AuditTemplate).where(AuditTemplate.id == template_id))
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    section = AuditSection(
        template_id=template_id,
        **section_data.model_dump(),
    )

    db.add(section)
    await db.commit()
    await db.refresh(section)

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

    update_data = section_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(section, field, value)

    await db.commit()
    await db.refresh(section)

    return AuditSectionResponse.model_validate(section)


@router.delete("/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Soft delete an audit section."""
    result = await db.execute(select(AuditSection).where(AuditSection.id == section_id))
    section = result.scalar_one_or_none()

    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found",
        )

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
    # Verify template exists
    result = await db.execute(select(AuditTemplate).where(AuditTemplate.id == template_id))
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Convert options to JSON if provided
    question_dict = question_data.model_dump()
    for field in ("question_text", "description", "help_text"):
        if field in question_dict and isinstance(question_dict[field], str):
            question_dict[field] = html.unescape(question_dict[field])

    if question_dict.get("options"):
        options_list = [
            opt.model_dump() if hasattr(opt, "model_dump") else opt for opt in question_dict["options"]
        ]
        question_dict["options_json"] = _decode_option_list(options_list)
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

    response = AuditQuestionResponse.model_validate(question)
    response.question_text = _decode_html(response.question_text) or response.question_text
    response.description = _decode_html(response.description)
    response.help_text = _decode_html(response.help_text)
    response.options = _decode_option_list(response.options)
    return response


@router.patch("/questions/{question_id}", response_model=AuditQuestionResponse)
async def update_question(
    question_id: int,
    question_data: AuditQuestionUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditQuestionResponse:
    """Update an audit question."""
    result = await db.execute(select(AuditQuestion).where(AuditQuestion.id == question_id))
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    update_data = question_data.model_dump(exclude_unset=True)

    # Handle JSON fields
    for field in ("question_text", "description", "help_text"):
        if field in update_data and isinstance(update_data[field], str):
            update_data[field] = html.unescape(update_data[field])

    if "options" in update_data:
        update_data["options_json"] = _decode_option_list(update_data.pop("options"))
    if "evidence_requirements" in update_data:
        update_data["evidence_requirements_json"] = update_data.pop("evidence_requirements")
    if "conditional_logic" in update_data:
        update_data["conditional_logic_json"] = update_data.pop("conditional_logic")
    if "clause_ids" in update_data:
        update_data["clause_ids_json"] = update_data.pop("clause_ids")
    if "control_ids" in update_data:
        update_data["control_ids_json"] = update_data.pop("control_ids")

    for field, value in update_data.items():
        setattr(question, field, value)

    await db.commit()
    await db.refresh(question)

    response = AuditQuestionResponse.model_validate(question)
    response.question_text = _decode_html(response.question_text) or response.question_text
    response.description = _decode_html(response.description)
    response.help_text = _decode_html(response.help_text)
    response.options = _decode_option_list(response.options)
    return response


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Soft delete an audit question."""
    result = await db.execute(select(AuditQuestion).where(AuditQuestion.id == question_id))
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    question.is_active = False
    await db.commit()


# ============== Audit Run Endpoints ==============


@router.get("/runs", response_model=AuditRunListResponse)
async def list_runs(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    template_id: Optional[int] = None,
    assigned_to_id: Optional[int] = None,
) -> AuditRunListResponse:
    """List all audit runs with pagination and filtering."""
    query = select(AuditRun)

    if status_filter:
        query = query.where(AuditRun.status == status_filter)
    if template_id:
        query = query.where(AuditRun.template_id == template_id)
    if assigned_to_id:
        query = query.where(AuditRun.assigned_to_id == assigned_to_id)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(AuditRun.created_at.desc())

    result = await db.execute(query)
    runs = result.scalars().all()

    return AuditRunListResponse(
        items=[AuditRunResponse.model_validate(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.post("/runs", response_model=AuditRunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    run_data: AuditRunCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditRunResponse:
    """Create a new audit run from a template."""
    started = time.perf_counter()
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
        _record_audit_endpoint_event(
            "POST /api/v1/audits/runs",
            404,
            (time.perf_counter() - started) * 1000,
            "template_not_published",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published template not found",
        )

    run = AuditRun(
        **run_data.model_dump(),
        template_version=template.version,
        status=AuditStatus.SCHEDULED,
        created_by_id=current_user.id,
    )

    # Generate reference number
    run.reference_number = await ReferenceNumberService.generate(db, "audit_run", AuditRun)

    db.add(run)
    await db.commit()
    await db.refresh(run)

    response = AuditRunResponse.model_validate(run)
    _record_audit_endpoint_event("POST /api/v1/audits/runs", 201, (time.perf_counter() - started) * 1000)
    return response


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
        .where(AuditRun.id == run_id)
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
    result = await db.execute(select(AuditRun).where(AuditRun.id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit run not found",
        )

    update_data = run_data.model_dump(exclude_unset=True)

    # Handle status transitions
    if "status" in update_data:
        new_status = update_data["status"]
        if new_status == AuditStatus.IN_PROGRESS.value and run.started_at is None:
            run.started_at = datetime.now(timezone.utc)
        elif new_status == AuditStatus.COMPLETED.value:
            run.completed_at = datetime.now(timezone.utc)

    for field, value in update_data.items():
        setattr(run, field, value)

    await db.commit()
    await db.refresh(run)

    return AuditRunResponse.model_validate(run)


@router.post("/runs/{run_id}/start", response_model=AuditRunResponse)
async def start_run(
    run_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditRunResponse:
    """Start an audit run."""
    result = await db.execute(select(AuditRun).where(AuditRun.id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit run not found",
        )

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
    started = time.perf_counter()
    result = await db.execute(select(AuditRun).options(selectinload(AuditRun.responses)).where(AuditRun.id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        _record_audit_endpoint_event(
            "POST /api/v1/audits/runs/{id}/complete",
            404,
            (time.perf_counter() - started) * 1000,
            "run_not_found",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit run not found",
        )

    if run.status != AuditStatus.IN_PROGRESS:
        _record_audit_endpoint_event(
            "POST /api/v1/audits/runs/{id}/complete",
            400,
            (time.perf_counter() - started) * 1000,
            "invalid_status_transition",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audit run must be in progress to complete",
        )

    # Calculate scores
    total_score = sum(r.score or 0 for r in run.responses)
    max_score = sum(r.max_score or 0 for r in run.responses)

    run.score = total_score
    run.max_score = max_score
    run.score_percentage = (total_score / max_score * 100) if max_score > 0 else 0

    # Get template to check passing score
    template_result = await db.execute(select(AuditTemplate).where(AuditTemplate.id == run.template_id))
    template = template_result.scalar_one_or_none()

    if template and template.passing_score is not None:
        run.passed = run.score_percentage >= template.passing_score

    run.status = AuditStatus.COMPLETED
    run.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(run)

    response = AuditRunResponse.model_validate(run)
    _record_audit_endpoint_event("POST /api/v1/audits/runs/{id}/complete", 200, (time.perf_counter() - started) * 1000)
    return response


# ============== Response Endpoints ==============


@router.post("/runs/{run_id}/responses", response_model=AuditResponseResponse, status_code=status.HTTP_201_CREATED)
async def create_response(
    run_id: int,
    response_data: AuditResponseCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditResponseResponse:
    """Submit a response to an audit question."""
    started = time.perf_counter()
    # Verify run exists and is in progress
    result = await db.execute(select(AuditRun).where(AuditRun.id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        _record_audit_endpoint_event(
            "POST /api/v1/audits/runs/{id}/responses",
            404,
            (time.perf_counter() - started) * 1000,
            "run_not_found",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit run not found",
        )

    if run.status not in [AuditStatus.SCHEDULED, AuditStatus.IN_PROGRESS]:
        _record_audit_endpoint_event(
            "POST /api/v1/audits/runs/{id}/responses",
            400,
            (time.perf_counter() - started) * 1000,
            "run_not_writable",
        )
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
        _record_audit_endpoint_event(
            "POST /api/v1/audits/runs/{id}/responses",
            400,
            (time.perf_counter() - started) * 1000,
            "duplicate_response",
        )
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

    response_payload = AuditResponseResponse.model_validate(response)
    _record_audit_endpoint_event("POST /api/v1/audits/runs/{id}/responses", 201, (time.perf_counter() - started) * 1000)
    return response_payload


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

    update_data = response_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(response, field, value)

    await db.commit()
    await db.refresh(response)

    return AuditResponseResponse.model_validate(response)


# ============== Finding Endpoints ==============


@router.get("/findings", response_model=AuditFindingListResponse)
async def list_findings(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = None,
    run_id: Optional[int] = None,
) -> AuditFindingListResponse:
    """List all audit findings with pagination and filtering."""
    query = select(AuditFinding)

    if status_filter:
        query = query.where(AuditFinding.status == status_filter)
    if severity:
        query = query.where(AuditFinding.severity == severity)
    if run_id:
        query = query.where(AuditFinding.run_id == run_id)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(AuditFinding.created_at.desc())

    result = await db.execute(query)
    findings = result.scalars().all()

    return AuditFindingListResponse(
        items=[AuditFindingResponse.model_validate(f) for f in findings],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.post("/runs/{run_id}/findings", response_model=AuditFindingResponse, status_code=status.HTTP_201_CREATED)
async def create_finding(
    run_id: int,
    finding_data: AuditFindingCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditFindingResponse:
    """Create a new finding for an audit run."""
    started = time.perf_counter()
    # Verify run exists
    result = await db.execute(select(AuditRun).where(AuditRun.id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        _record_audit_endpoint_event(
            "POST /api/v1/audits/runs/{id}/findings",
            404,
            (time.perf_counter() - started) * 1000,
            "run_not_found",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit run not found",
        )

    finding_dict = finding_data.model_dump()

    # Handle list fields
    clause_ids = finding_dict.pop("clause_ids", None)
    control_ids = finding_dict.pop("control_ids", None)
    risk_ids = finding_dict.pop("risk_ids", None)

    finding = AuditFinding(
        run_id=run_id,
        status=FindingStatus.OPEN,
        created_by_id=current_user.id,
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

    response = AuditFindingResponse.model_validate(finding)
    _record_audit_endpoint_event("POST /api/v1/audits/runs/{id}/findings", 201, (time.perf_counter() - started) * 1000)
    return response


@router.patch("/findings/{finding_id}", response_model=AuditFindingResponse)
async def update_finding(
    finding_id: int,
    finding_data: AuditFindingUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> AuditFindingResponse:
    """Update an audit finding."""
    result = await db.execute(select(AuditFinding).where(AuditFinding.id == finding_id))
    finding = result.scalar_one_or_none()

    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found",
        )

    update_data = finding_data.model_dump(exclude_unset=True)

    # Handle list fields
    if "clause_ids" in update_data:
        finding.clause_ids_json = update_data.pop("clause_ids")
    if "control_ids" in update_data:
        finding.control_ids_json = update_data.pop("control_ids")
    if "risk_ids" in update_data:
        finding.risk_ids_json = update_data.pop("risk_ids")

    for field, value in update_data.items():
        setattr(finding, field, value)

    await db.commit()
    await db.refresh(finding)

    return AuditFindingResponse.model_validate(finding)
