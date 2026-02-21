"""Form configuration API routes for admin form builder."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.api.schemas.form_config import (
    ContractCreate,
    ContractListResponse,
    ContractResponse,
    ContractUpdate,
    FormFieldCreate,
    FormFieldResponse,
    FormFieldUpdate,
    FormStepCreate,
    FormStepResponse,
    FormStepUpdate,
    FormTemplateCreate,
    FormTemplateListResponse,
    FormTemplateResponse,
    FormTemplateUpdate,
    LookupOptionCreate,
    LookupOptionListResponse,
    LookupOptionResponse,
    LookupOptionUpdate,
    SystemSettingCreate,
    SystemSettingListResponse,
    SystemSettingResponse,
    SystemSettingUpdate,
)
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.form_config import Contract, FormField, FormStep, FormTemplate, LookupOption, SystemSetting
from src.domain.services.audit_service import record_audit_event
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter()


# ==================== Form Template Routes ====================


@router.get("/templates", response_model=FormTemplateListResponse)
async def list_form_templates(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    form_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
) -> FormTemplateListResponse:
    """List all form templates with pagination."""
    query = select(FormTemplate).where(FormTemplate.tenant_id == current_user.tenant_id)

    if form_type:
        query = query.where(FormTemplate.form_type == form_type)
    if is_active is not None:
        query = query.where(FormTemplate.is_active == is_active)

    query = query.order_by(FormTemplate.name)

    return await paginate(db, query, params)


@router.post(
    "/templates",
    response_model=FormTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_form_template(
    data: FormTemplateCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> FormTemplate:
    """Create a new form template."""
    # Check for duplicate slug
    existing = await db.execute(select(FormTemplate).where(FormTemplate.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Form template with slug '{data.slug}' already exists",
        )

    template = FormTemplate(
        name=data.name,
        slug=data.slug,
        description=data.description,
        form_type=data.form_type,
        icon=data.icon,
        color=data.color,
        allow_drafts=data.allow_drafts,
        allow_attachments=data.allow_attachments,
        require_signature=data.require_signature,
        auto_assign_reference=data.auto_assign_reference,
        reference_prefix=data.reference_prefix,
        notify_on_submit=data.notify_on_submit,
        notification_emails=data.notification_emails,
        workflow_id=data.workflow_id,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )

    db.add(template)
    await db.flush()

    # Create steps if provided
    if data.steps:
        for step_order, step_data in enumerate(data.steps):
            step = FormStep(
                template_id=template.id,
                name=step_data.name,
                description=step_data.description,
                order=step_order,
                icon=step_data.icon,
                show_condition=step_data.show_condition,
            )
            db.add(step)
            await db.flush()

            # Create fields if provided
            if step_data.fields:
                for field_order, field_data in enumerate(step_data.fields):
                    field = FormField(
                        step_id=step.id,
                        name=field_data.name,
                        label=field_data.label,
                        field_type=field_data.field_type,
                        order=field_order,
                        placeholder=field_data.placeholder,
                        help_text=field_data.help_text,
                        is_required=field_data.is_required,
                        min_length=field_data.min_length,
                        max_length=field_data.max_length,
                        min_value=field_data.min_value,
                        max_value=field_data.max_value,
                        pattern=field_data.pattern,
                        default_value=field_data.default_value,
                        options=field_data.options,
                        show_condition=field_data.show_condition,
                        width=field_data.width,
                    )
                    db.add(field)

    await db.commit()
    await db.refresh(template)
    await invalidate_tenant_cache(current_user.tenant_id, "form_config")
    track_metric("form_config.mutation", 1)

    await record_audit_event(
        db=db,
        entity_type="form_template",
        entity_id=template.id,
        action="created",
        user_id=current_user.id,
        details={"name": template.name, "form_type": template.form_type},
        request_id=request_id,
    )

    return template


@router.get("/templates/{template_id}", response_model=FormTemplateResponse)
async def get_form_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FormTemplate:
    """Get a form template by ID."""
    return await get_or_404(db, FormTemplate, template_id)


@router.get("/templates/by-slug/{slug}", response_model=FormTemplateResponse)
async def get_form_template_by_slug(
    slug: str,
    db: DbSession,
) -> FormTemplate:
    """Get a form template by slug (public endpoint for portal)."""
    result = await db.execute(
        select(FormTemplate)
        .where(FormTemplate.slug == slug)
        .where(FormTemplate.is_active == True)
        .where(FormTemplate.is_published == True)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Form template '{slug}' not found or not published",
        )

    return template


@router.patch("/templates/{template_id}", response_model=FormTemplateResponse)
async def update_form_template(
    template_id: int,
    data: FormTemplateUpdate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> FormTemplate:
    """Update a form template."""
    template = await get_or_404(db, FormTemplate, template_id)

    update_data = apply_updates(template, data)
    template.updated_by_id = current_user.id
    template.version += 1

    await db.commit()
    await db.refresh(template)
    await invalidate_tenant_cache(current_user.tenant_id, "form_config")
    track_metric("form_config.mutation", 1)

    await record_audit_event(
        db=db,
        entity_type="form_template",
        entity_id=template.id,
        action="updated",
        user_id=current_user.id,
        details=update_data,
        request_id=request_id,
    )

    return template


@router.post("/templates/{template_id}/publish", response_model=FormTemplateResponse)
async def publish_form_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> FormTemplate:
    """Publish a form template to make it available in the portal."""
    template = await get_or_404(db, FormTemplate, template_id)

    template.is_published = True
    template.published_at = datetime.now(timezone.utc)
    template.updated_by_id = current_user.id

    await db.commit()
    await db.refresh(template)

    await record_audit_event(
        db=db,
        entity_type="form_template",
        entity_id=template.id,
        action="published",
        user_id=current_user.id,
        details={"published_at": template.published_at.isoformat()},
        request_id=request_id,
    )

    return template


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_form_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> None:
    """Delete a form template."""
    template = await get_or_404(db, FormTemplate, template_id)

    await record_audit_event(
        db=db,
        entity_type="form_template",
        entity_id=template.id,
        action="deleted",
        user_id=current_user.id,
        details={"name": template.name},
        request_id=request_id,
    )

    await db.delete(template)
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "form_config")
    track_metric("form_config.mutation", 1)


# ==================== Form Step Routes ====================


@router.post(
    "/templates/{template_id}/steps",
    response_model=FormStepResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_form_step(
    template_id: int,
    data: FormStepCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> FormStep:
    """Create a new step in a form template."""
    await get_or_404(db, FormTemplate, template_id)

    step = FormStep(
        template_id=template_id,
        name=data.name,
        description=data.description,
        order=data.order,
        icon=data.icon,
        show_condition=data.show_condition,
    )

    db.add(step)
    await db.flush()

    # Create fields if provided
    if data.fields:
        for field_order, field_data in enumerate(data.fields):
            field = FormField(
                step_id=step.id,
                name=field_data.name,
                label=field_data.label,
                field_type=field_data.field_type,
                order=field_order,
                placeholder=field_data.placeholder,
                help_text=field_data.help_text,
                is_required=field_data.is_required,
                options=field_data.options,
                width=field_data.width,
            )
            db.add(field)

    await db.commit()
    await db.refresh(step)

    return step


@router.patch("/steps/{step_id}", response_model=FormStepResponse)
async def update_form_step(
    step_id: int,
    data: FormStepUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> FormStep:
    """Update a form step."""
    step = await get_or_404(db, FormStep, step_id)

    apply_updates(step, data, set_updated_at=False)

    await db.commit()
    await db.refresh(step)

    return step


@router.delete("/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_form_step(
    step_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a form step."""
    step = await get_or_404(db, FormStep, step_id)

    await db.delete(step)
    await db.commit()


# ==================== Form Field Routes ====================


@router.post(
    "/steps/{step_id}/fields",
    response_model=FormFieldResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_form_field(
    step_id: int,
    data: FormFieldCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> FormField:
    """Create a new field in a form step."""
    await get_or_404(db, FormStep, step_id)

    field = FormField(
        step_id=step_id,
        name=data.name,
        label=data.label,
        field_type=data.field_type,
        order=data.order,
        placeholder=data.placeholder,
        help_text=data.help_text,
        is_required=data.is_required,
        min_length=data.min_length,
        max_length=data.max_length,
        min_value=data.min_value,
        max_value=data.max_value,
        pattern=data.pattern,
        default_value=data.default_value,
        options=data.options,
        show_condition=data.show_condition,
        width=data.width,
    )

    db.add(field)
    await db.commit()
    await db.refresh(field)

    return field


@router.patch("/fields/{field_id}", response_model=FormFieldResponse)
async def update_form_field(
    field_id: int,
    data: FormFieldUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> FormField:
    """Update a form field."""
    field = await get_or_404(db, FormField, field_id)

    apply_updates(field, data, set_updated_at=False)

    await db.commit()
    await db.refresh(field)

    return field


@router.delete("/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_form_field(
    field_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a form field."""
    field = await get_or_404(db, FormField, field_id)

    await db.delete(field)
    await db.commit()


# ==================== Contract Routes ====================


@router.get("/contracts", response_model=ContractListResponse)
async def list_contracts(
    db: DbSession,
    current_user: CurrentUser,
    is_active: Optional[bool] = Query(None),
) -> ContractListResponse:
    """List all contracts."""
    query = select(Contract).where(Contract.tenant_id == current_user.tenant_id)

    if is_active is not None:
        query = query.where(Contract.is_active == is_active)

    query = query.order_by(Contract.display_order, Contract.name)
    result = await db.execute(query)
    contracts = result.scalars().all()

    return ContractListResponse(
        items=[ContractResponse.model_validate(c) for c in contracts],
        total=len(contracts),
    )


@router.post("/contracts", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(
    data: ContractCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> Contract:
    """Create a new contract."""
    # Check for duplicate code
    existing = await db.execute(select(Contract).where(Contract.code == data.code))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Contract with code '{data.code}' already exists",
        )

    contract = Contract(
        name=data.name,
        code=data.code,
        description=data.description,
        client_name=data.client_name,
        client_contact=data.client_contact,
        client_email=data.client_email,
        is_active=data.is_active,
        start_date=data.start_date,
        end_date=data.end_date,
        display_order=data.display_order,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )

    db.add(contract)
    await db.commit()
    await db.refresh(contract)
    await invalidate_tenant_cache(current_user.tenant_id, "form_config")
    track_metric("form_config.mutation", 1)

    await record_audit_event(
        db=db,
        entity_type="contract",
        entity_id=contract.id,
        action="created",
        user_id=current_user.id,
        details={"name": contract.name, "code": contract.code},
        request_id=request_id,
    )

    return contract


@router.get("/contracts/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Contract:
    """Get a contract by ID."""
    return await get_or_404(db, Contract, contract_id)


@router.patch("/contracts/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: int,
    data: ContractUpdate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> Contract:
    """Update a contract."""
    contract = await get_or_404(db, Contract, contract_id)

    update_data = apply_updates(contract, data)
    contract.updated_by_id = current_user.id

    await db.commit()
    await db.refresh(contract)
    await invalidate_tenant_cache(current_user.tenant_id, "form_config")
    track_metric("form_config.mutation", 1)

    await record_audit_event(
        db=db,
        entity_type="contract",
        entity_id=contract.id,
        action="updated",
        user_id=current_user.id,
        details=update_data,
        request_id=request_id,
    )

    return contract


@router.delete("/contracts/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(
    contract_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> None:
    """Delete a contract."""
    contract = await get_or_404(db, Contract, contract_id)

    await record_audit_event(
        db=db,
        entity_type="contract",
        entity_id=contract.id,
        action="deleted",
        user_id=current_user.id,
        details={"name": contract.name},
        request_id=request_id,
    )

    await db.delete(contract)
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "form_config")
    track_metric("form_config.mutation", 1)


# ==================== System Setting Routes ====================


@router.get("/settings", response_model=SystemSettingListResponse)
async def list_system_settings(
    db: DbSession,
    current_user: CurrentUser,
    category: Optional[str] = Query(None),
) -> SystemSettingListResponse:
    """List all system settings."""
    query = select(SystemSetting).where(SystemSetting.tenant_id == current_user.tenant_id)

    if category:
        query = query.where(SystemSetting.category == category)

    query = query.order_by(SystemSetting.category, SystemSetting.key)
    result = await db.execute(query)
    settings = result.scalars().all()

    return SystemSettingListResponse(
        items=[SystemSettingResponse.model_validate(s) for s in settings],
        total=len(settings),
    )


@router.post(
    "/settings",
    response_model=SystemSettingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_system_setting(
    data: SystemSettingCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> SystemSetting:
    """Create a new system setting."""
    # Check for duplicate key
    existing = await db.execute(select(SystemSetting).where(SystemSetting.key == data.key))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Setting with key '{data.key}' already exists",
        )

    setting = SystemSetting(
        key=data.key,
        value=data.value,
        category=data.category,
        description=data.description,
        value_type=data.value_type,
        is_public=data.is_public,
        is_editable=data.is_editable,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )

    db.add(setting)
    await db.commit()
    await db.refresh(setting)
    await invalidate_tenant_cache(current_user.tenant_id, "form_config")
    track_metric("form_config.mutation", 1)

    return setting


@router.patch("/settings/{key}", response_model=SystemSettingResponse)
async def update_system_setting(
    key: str,
    data: SystemSettingUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> SystemSetting:
    """Update a system setting by key."""
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )

    if not setting.is_editable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Setting '{key}' is not editable",
        )

    apply_updates(setting, data)
    setting.updated_by_id = current_user.id

    await db.commit()
    await db.refresh(setting)
    await invalidate_tenant_cache(current_user.tenant_id, "form_config")
    track_metric("form_config.mutation", 1)

    return setting


# ==================== Lookup Option Routes ====================


@router.get("/lookup/{category}", response_model=LookupOptionListResponse)
async def list_lookup_options(
    category: str,
    db: DbSession,
    current_user: CurrentUser,
    is_active: Optional[bool] = Query(True),
) -> LookupOptionListResponse:
    """List lookup options by category."""
    query = select(LookupOption).where(
        LookupOption.category == category,
        LookupOption.tenant_id == current_user.tenant_id,
    )

    if is_active is not None:
        query = query.where(LookupOption.is_active == is_active)

    query = query.order_by(LookupOption.display_order, LookupOption.label)
    result = await db.execute(query)
    options = result.scalars().all()

    return LookupOptionListResponse(
        items=[LookupOptionResponse.model_validate(o) for o in options],
        total=len(options),
    )


@router.post(
    "/lookup/{category}",
    response_model=LookupOptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_lookup_option(
    category: str,
    data: LookupOptionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> LookupOption:
    """Create a new lookup option."""
    # Ensure category matches
    if data.category != category:
        data.category = category

    option = LookupOption(
        category=data.category,
        code=data.code,
        label=data.label,
        description=data.description,
        is_active=data.is_active,
        display_order=data.display_order,
        parent_id=data.parent_id,
    )

    db.add(option)
    await db.commit()
    await db.refresh(option)
    await invalidate_tenant_cache(current_user.tenant_id, "form_config")
    track_metric("form_config.mutation", 1)

    return option


@router.patch("/lookup/{category}/{option_id}", response_model=LookupOptionResponse)
async def update_lookup_option(
    category: str,
    option_id: int,
    data: LookupOptionUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> LookupOption:
    """Update a lookup option."""
    result = await db.execute(
        select(LookupOption).where(LookupOption.id == option_id).where(LookupOption.category == category)
    )
    option = result.scalar_one_or_none()

    if not option:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lookup option {option_id} not found in category '{category}'",
        )

    apply_updates(option, data, set_updated_at=False)

    await db.commit()
    await db.refresh(option)
    await invalidate_tenant_cache(current_user.tenant_id, "form_config")
    track_metric("form_config.mutation", 1)

    return option


@router.delete("/lookup/{category}/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lookup_option(
    category: str,
    option_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a lookup option."""
    result = await db.execute(
        select(LookupOption).where(LookupOption.id == option_id).where(LookupOption.category == category)
    )
    option = result.scalar_one_or_none()

    if not option:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lookup option {option_id} not found in category '{category}'",
        )

    await db.delete(option)
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "form_config")
    track_metric("form_config.mutation", 1)
