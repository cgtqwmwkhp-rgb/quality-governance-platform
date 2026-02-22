"""Form configuration API routes for admin form builder."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
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
from src.api.utils.pagination import PaginationParams
from src.domain.models.form_config import Contract, FormField, FormStep, FormTemplate, LookupOption, SystemSetting
from src.domain.services.form_config_service import FormConfigService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter()


# ==================== Form Template Routes ====================


@router.get("/templates", response_model=FormTemplateListResponse)
async def list_form_templates(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    form_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
) -> Any:
    """List all form templates with pagination."""
    svc = FormConfigService(db)
    return await svc.list_templates(
        tenant_id=current_user.tenant_id,
        form_type=form_type,
        is_active=is_active,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("/templates", response_model=FormTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_form_template(
    data: FormTemplateCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> FormTemplate:
    """Create a new form template."""
    _span = tracer.start_span("create_form_template") if tracer else None

    svc = FormConfigService(db)
    template = await svc.create_template(
        data=data,
        user_id=current_user.id,
        request_id=request_id,
    )
    await invalidate_tenant_cache(current_user.tenant_id, "form_config")

    if _span:
        _span.end()
    return template


@router.get("/templates/{template_id}", response_model=FormTemplateResponse)
async def get_form_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> FormTemplate:
    """Get a form template by ID."""
    svc = FormConfigService(db)
    return await svc.get_template(template_id, tenant_id=current_user.tenant_id)


@router.get("/templates/by-slug/{slug}", response_model=FormTemplateResponse)
async def get_form_template_by_slug(
    slug: str,
    db: DbSession,
) -> FormTemplate:
    """Get a form template by slug (public endpoint for portal)."""
    svc = FormConfigService(db)
    return await svc.get_template_by_slug(slug)


@router.patch("/templates/{template_id}", response_model=FormTemplateResponse)
async def update_form_template(
    template_id: int,
    data: FormTemplateUpdate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> FormTemplate:
    """Update a form template."""
    svc = FormConfigService(db)
    return await svc.update_template(
        template_id,
        data=data,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        request_id=request_id,
    )


@router.post("/templates/{template_id}/publish", response_model=FormTemplateResponse)
async def publish_form_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> FormTemplate:
    """Publish a form template to make it available in the portal."""
    svc = FormConfigService(db)
    return await svc.publish_template(
        template_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        request_id=request_id,
    )


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_form_template(
    template_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
    request_id: str = Depends(get_request_id),
) -> None:
    """Delete a form template."""
    svc = FormConfigService(db)
    await svc.delete_template(
        template_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        request_id=request_id,
    )


# ==================== Form Step Routes ====================


@router.post("/templates/{template_id}/steps", response_model=FormStepResponse, status_code=status.HTTP_201_CREATED)
async def create_form_step(
    template_id: int,
    data: FormStepCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> FormStep:
    """Create a new step in a form template."""
    svc = FormConfigService(db)
    return await svc.create_step(
        template_id,
        data=data,
        tenant_id=current_user.tenant_id,
    )


@router.patch("/steps/{step_id}", response_model=FormStepResponse)
async def update_form_step(
    step_id: int,
    data: FormStepUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> FormStep:
    """Update a form step."""
    svc = FormConfigService(db)
    return await svc.update_step(
        step_id,
        data=data,
        tenant_id=current_user.tenant_id,
    )


@router.delete("/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_form_step(
    step_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Delete a form step."""
    svc = FormConfigService(db)
    await svc.delete_step(step_id, tenant_id=current_user.tenant_id)


# ==================== Form Field Routes ====================


@router.post("/steps/{step_id}/fields", response_model=FormFieldResponse, status_code=status.HTTP_201_CREATED)
async def create_form_field(
    step_id: int,
    data: FormFieldCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> FormField:
    """Create a new field in a form step."""
    svc = FormConfigService(db)
    return await svc.create_field(
        step_id,
        data=data,
        tenant_id=current_user.tenant_id,
    )


@router.patch("/fields/{field_id}", response_model=FormFieldResponse)
async def update_form_field(
    field_id: int,
    data: FormFieldUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> FormField:
    """Update a form field."""
    svc = FormConfigService(db)
    return await svc.update_field(
        field_id,
        data=data,
        tenant_id=current_user.tenant_id,
    )


@router.delete("/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_form_field(
    field_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Delete a form field."""
    svc = FormConfigService(db)
    await svc.delete_field(field_id, tenant_id=current_user.tenant_id)


# ==================== Contract Routes ====================


@router.get("/contracts", response_model=ContractListResponse)
async def list_contracts(
    db: DbSession,
    current_user: CurrentUser,
    is_active: Optional[bool] = Query(None),
) -> Any:
    """List all contracts."""
    svc = FormConfigService(db)
    contracts = await svc.list_contracts(
        tenant_id=current_user.tenant_id,
        is_active=is_active,
    )
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
    svc = FormConfigService(db)
    return await svc.create_contract(
        data=data,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        request_id=request_id,
    )


@router.get("/contracts/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Contract:
    """Get a contract by ID."""
    svc = FormConfigService(db)
    return await svc.get_contract(contract_id, tenant_id=current_user.tenant_id)


@router.patch("/contracts/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: int,
    data: ContractUpdate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> Contract:
    """Update a contract."""
    svc = FormConfigService(db)
    return await svc.update_contract(
        contract_id,
        data=data,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        request_id=request_id,
    )


@router.delete("/contracts/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(
    contract_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
    request_id: str = Depends(get_request_id),
) -> None:
    """Delete a contract."""
    svc = FormConfigService(db)
    await svc.delete_contract(
        contract_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        request_id=request_id,
    )


# ==================== System Setting Routes ====================


@router.get("/settings", response_model=SystemSettingListResponse)
async def list_system_settings(
    db: DbSession,
    current_user: CurrentUser,
    category: Optional[str] = Query(None),
) -> Any:
    """List all system settings."""
    svc = FormConfigService(db)
    settings = await svc.list_settings(
        tenant_id=current_user.tenant_id,
        category=category,
    )
    return SystemSettingListResponse(
        items=[SystemSettingResponse.model_validate(s) for s in settings],
        total=len(settings),
    )


@router.post("/settings", response_model=SystemSettingResponse, status_code=status.HTTP_201_CREATED)
async def create_system_setting(
    data: SystemSettingCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> SystemSetting:
    """Create a new system setting."""
    svc = FormConfigService(db)
    return await svc.create_setting(
        data=data,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )


@router.patch("/settings/{key}", response_model=SystemSettingResponse)
async def update_system_setting(
    key: str,
    data: SystemSettingUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> SystemSetting:
    """Update a system setting by key."""
    svc = FormConfigService(db)
    return await svc.update_setting(
        key,
        data=data,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )


# ==================== Lookup Option Routes ====================


@router.get("/lookup/{category}", response_model=LookupOptionListResponse)
async def list_lookup_options(
    category: str,
    db: DbSession,
    current_user: CurrentUser,
    is_active: Optional[bool] = Query(True),
) -> Any:
    """List lookup options by category."""
    svc = FormConfigService(db)
    options = await svc.list_lookup_options(
        category,
        tenant_id=current_user.tenant_id,
        is_active=is_active,
    )
    return LookupOptionListResponse(
        items=[LookupOptionResponse.model_validate(o) for o in options],
        total=len(options),
    )


@router.post("/lookup/{category}", response_model=LookupOptionResponse, status_code=status.HTTP_201_CREATED)
async def create_lookup_option(
    category: str,
    data: LookupOptionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> LookupOption:
    """Create a new lookup option."""
    svc = FormConfigService(db)
    return await svc.create_lookup_option(
        category,
        data=data,
        tenant_id=current_user.tenant_id,
    )


@router.patch("/lookup/{category}/{option_id}", response_model=LookupOptionResponse)
async def update_lookup_option(
    category: str,
    option_id: int,
    data: LookupOptionUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> LookupOption:
    """Update a lookup option."""
    svc = FormConfigService(db)
    return await svc.update_lookup_option(
        category,
        option_id,
        data=data,
        tenant_id=current_user.tenant_id,
    )


@router.delete("/lookup/{category}/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lookup_option(
    category: str,
    option_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a lookup option."""
    svc = FormConfigService(db)
    await svc.delete_lookup_option(
        category,
        option_id,
        tenant_id=current_user.tenant_id,
    )
