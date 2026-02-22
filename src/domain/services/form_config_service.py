"""Form configuration domain service.

Extracts business logic from form_config routes into a testable service class.
Handles CRUD for form templates, steps, fields, contracts, settings,
and lookup options.  Raises domain exceptions instead of HTTPException.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas.error_codes import ErrorCode
from src.api.utils.update import apply_updates
from src.domain.exceptions import AuthorizationError, ConflictError, NotFoundError
from src.domain.models.form_config import (
    Contract,
    FormField,
    FormStep,
    FormTemplate,
    LookupOption,
    SystemSetting,
)
from src.domain.services.audit_service import record_audit_event
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric


class FormConfigService:
    """Handles CRUD for form configuration entities."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _get_or_raise(
        self,
        model: type,
        entity_id: int,
        tenant_id: int | None = None,
    ) -> Any:
        """Fetch an entity by primary key or raise *NotFoundError*."""
        model_any: Any = model
        stmt = select(model).where(model_any.id == entity_id)
        if tenant_id is not None and hasattr(model, "tenant_id"):
            stmt = stmt.where(model_any.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        entity = result.scalar_one_or_none()
        if entity is None:
            raise NotFoundError(f"{model.__name__} with ID {entity_id} not found")
        return entity

    # ================================================================== #
    #  Form Template methods                                               #
    # ================================================================== #

    async def list_templates(
        self,
        *,
        tenant_id: int,
        form_type: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """List form templates with pagination."""
        query = (
            select(FormTemplate)
            .where(FormTemplate.tenant_id == tenant_id)
            .options(selectinload(FormTemplate.steps))
        )
        if form_type:
            query = query.where(FormTemplate.form_type == form_type)
        if is_active is not None:
            query = query.where(FormTemplate.is_active == is_active)
        query = query.order_by(FormTemplate.name)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total: int = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.db.execute(query.offset(offset).limit(page_size))
        items = list(result.scalars().all())

        pages = (total + page_size - 1) // page_size if total > 0 else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }

    async def create_template(
        self,
        *,
        data: BaseModel,
        user_id: int,
        request_id: str,
    ) -> FormTemplate:
        """Create a new form template with optional nested steps and fields."""
        existing = await self.db.execute(
            select(FormTemplate).where(FormTemplate.slug == data.slug)  # type: ignore[union-attr]
        )
        if existing.scalar_one_or_none():
            raise ConflictError(ErrorCode.DUPLICATE_ENTITY)

        template = FormTemplate(  # type: ignore[call-arg]
            name=data.name,  # type: ignore[union-attr]
            slug=data.slug,  # type: ignore[union-attr]
            description=data.description,  # type: ignore[union-attr]
            form_type=data.form_type,  # type: ignore[union-attr]
            icon=data.icon,  # type: ignore[union-attr]
            color=data.color,  # type: ignore[union-attr]
            allow_drafts=data.allow_drafts,  # type: ignore[union-attr]
            allow_attachments=data.allow_attachments,  # type: ignore[union-attr]
            require_signature=data.require_signature,  # type: ignore[union-attr]
            auto_assign_reference=data.auto_assign_reference,  # type: ignore[union-attr]
            reference_prefix=data.reference_prefix,  # type: ignore[union-attr]
            notify_on_submit=data.notify_on_submit,  # type: ignore[union-attr]
            notification_emails=data.notification_emails,  # type: ignore[union-attr]
            workflow_id=data.workflow_id,  # type: ignore[union-attr]
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        self.db.add(template)
        await self.db.flush()

        if getattr(data, "steps", None):
            for step_order, step_data in enumerate(data.steps):  # type: ignore[union-attr]
                step = FormStep(  # type: ignore[call-arg]
                    template_id=template.id,
                    name=step_data.name,
                    description=step_data.description,
                    order=step_order,
                    icon=step_data.icon,
                    show_condition=step_data.show_condition,
                )
                self.db.add(step)
                await self.db.flush()

                if getattr(step_data, "fields", None):
                    for field_order, field_data in enumerate(step_data.fields):
                        field = FormField(  # type: ignore[call-arg]
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
                        self.db.add(field)

        await self.db.commit()
        await self.db.refresh(template)
        track_metric("form_config.mutation", 1)
        track_metric("form_config.templates_created", 1)

        await record_audit_event(
            db=self.db,
            entity_type="form_template",
            entity_id=template.id,
            action="created",
            user_id=user_id,
            details={"name": template.name, "form_type": template.form_type},
            request_id=request_id,
        )

        return template

    async def get_template(
        self,
        template_id: int,
        *,
        tenant_id: int,
    ) -> FormTemplate:
        """Get a form template by ID, scoped to tenant."""
        return await self._get_or_raise(FormTemplate, template_id, tenant_id=tenant_id)

    async def get_template_by_slug(self, slug: str) -> FormTemplate:
        """Get an active, published form template by slug."""
        result = await self.db.execute(
            select(FormTemplate)
            .where(FormTemplate.slug == slug)
            .where(FormTemplate.is_active == True)  # noqa: E712
            .where(FormTemplate.is_published == True)  # noqa: E712
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
        return template

    async def update_template(
        self,
        template_id: int,
        *,
        data: BaseModel,
        user_id: int,
        tenant_id: int,
        request_id: str,
    ) -> FormTemplate:
        """Update a form template."""
        template = await self._get_or_raise(FormTemplate, template_id, tenant_id=tenant_id)

        update_data = apply_updates(template, data)
        template.updated_by_id = user_id
        template.version += 1

        await self.db.commit()
        await self.db.refresh(template)
        await invalidate_tenant_cache(tenant_id, "form_config")
        track_metric("form_config.mutation", 1)

        await record_audit_event(
            db=self.db,
            entity_type="form_template",
            entity_id=template.id,
            action="updated",
            user_id=user_id,
            details=update_data,
            request_id=request_id,
        )

        return template

    async def publish_template(
        self,
        template_id: int,
        *,
        user_id: int,
        tenant_id: int,
        request_id: str,
    ) -> FormTemplate:
        """Publish a form template to make it available in the portal."""
        template = await self._get_or_raise(FormTemplate, template_id, tenant_id=tenant_id)

        template.is_published = True
        template.published_at = datetime.now(timezone.utc)
        template.updated_by_id = user_id

        await self.db.commit()
        await self.db.refresh(template)

        await record_audit_event(
            db=self.db,
            entity_type="form_template",
            entity_id=template.id,
            action="published",
            user_id=user_id,
            details={"published_at": template.published_at.isoformat()},
            request_id=request_id,
        )

        return template

    async def delete_template(
        self,
        template_id: int,
        *,
        user_id: int,
        tenant_id: int,
        request_id: str,
    ) -> None:
        """Delete a form template."""
        template = await self._get_or_raise(FormTemplate, template_id, tenant_id=tenant_id)

        await record_audit_event(
            db=self.db,
            entity_type="form_template",
            entity_id=template.id,
            action="deleted",
            user_id=user_id,
            details={"name": template.name},
            request_id=request_id,
        )

        await self.db.delete(template)
        await self.db.commit()
        await invalidate_tenant_cache(tenant_id, "form_config")
        track_metric("form_config.mutation", 1)

    # ================================================================== #
    #  Form Step methods                                                   #
    # ================================================================== #

    async def create_step(
        self,
        template_id: int,
        *,
        data: BaseModel,
        tenant_id: int,
    ) -> FormStep:
        """Create a new step in a form template."""
        await self._get_or_raise(FormTemplate, template_id, tenant_id=tenant_id)

        step = FormStep(  # type: ignore[call-arg]
            template_id=template_id,
            name=data.name,  # type: ignore[union-attr]
            description=data.description,  # type: ignore[union-attr]
            order=data.order,  # type: ignore[union-attr]
            icon=data.icon,  # type: ignore[union-attr]
            show_condition=data.show_condition,  # type: ignore[union-attr]
        )
        self.db.add(step)
        await self.db.flush()

        if getattr(data, "fields", None):
            for field_order, field_data in enumerate(data.fields):  # type: ignore[union-attr]
                field = FormField(  # type: ignore[call-arg]
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
                self.db.add(field)

        await self.db.commit()
        await self.db.refresh(step)
        return step

    async def update_step(
        self,
        step_id: int,
        *,
        data: BaseModel,
        tenant_id: int,
    ) -> FormStep:
        """Update a form step."""
        step = await self._get_or_raise(FormStep, step_id, tenant_id=tenant_id)
        apply_updates(step, data, set_updated_at=False)
        await self.db.commit()
        await self.db.refresh(step)
        return step

    async def delete_step(
        self,
        step_id: int,
        *,
        tenant_id: int,
    ) -> None:
        """Delete a form step."""
        step = await self._get_or_raise(FormStep, step_id, tenant_id=tenant_id)
        await self.db.delete(step)
        await self.db.commit()

    # ================================================================== #
    #  Form Field methods                                                  #
    # ================================================================== #

    async def create_field(
        self,
        step_id: int,
        *,
        data: BaseModel,
        tenant_id: int,
    ) -> FormField:
        """Create a new field in a form step."""
        await self._get_or_raise(FormStep, step_id, tenant_id=tenant_id)

        field = FormField(  # type: ignore[call-arg]
            step_id=step_id,
            name=data.name,  # type: ignore[union-attr]
            label=data.label,  # type: ignore[union-attr]
            field_type=data.field_type,  # type: ignore[union-attr]
            order=data.order,  # type: ignore[union-attr]
            placeholder=data.placeholder,  # type: ignore[union-attr]
            help_text=data.help_text,  # type: ignore[union-attr]
            is_required=data.is_required,  # type: ignore[union-attr]
            min_length=data.min_length,  # type: ignore[union-attr]
            max_length=data.max_length,  # type: ignore[union-attr]
            min_value=data.min_value,  # type: ignore[union-attr]
            max_value=data.max_value,  # type: ignore[union-attr]
            pattern=data.pattern,  # type: ignore[union-attr]
            default_value=data.default_value,  # type: ignore[union-attr]
            options=data.options,  # type: ignore[union-attr]
            show_condition=data.show_condition,  # type: ignore[union-attr]
            width=data.width,  # type: ignore[union-attr]
        )
        self.db.add(field)
        await self.db.commit()
        await self.db.refresh(field)
        return field

    async def update_field(
        self,
        field_id: int,
        *,
        data: BaseModel,
        tenant_id: int,
    ) -> FormField:
        """Update a form field."""
        field = await self._get_or_raise(FormField, field_id, tenant_id=tenant_id)
        apply_updates(field, data, set_updated_at=False)
        await self.db.commit()
        await self.db.refresh(field)
        return field

    async def delete_field(
        self,
        field_id: int,
        *,
        tenant_id: int,
    ) -> None:
        """Delete a form field."""
        field = await self._get_or_raise(FormField, field_id, tenant_id=tenant_id)
        await self.db.delete(field)
        await self.db.commit()

    # ================================================================== #
    #  Contract methods                                                    #
    # ================================================================== #

    async def list_contracts(
        self,
        *,
        tenant_id: int,
        is_active: bool | None = None,
    ) -> Sequence[Contract]:
        """List all contracts for a tenant."""
        query = select(Contract).where(Contract.tenant_id == tenant_id)
        if is_active is not None:
            query = query.where(Contract.is_active == is_active)
        query = query.order_by(Contract.display_order, Contract.name)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_contract(
        self,
        *,
        data: BaseModel,
        user_id: int,
        tenant_id: int,
        request_id: str,
    ) -> Contract:
        """Create a new contract."""
        existing = await self.db.execute(
            select(Contract).where(Contract.code == data.code)  # type: ignore[union-attr]
        )
        if existing.scalar_one_or_none():
            raise ConflictError(ErrorCode.DUPLICATE_ENTITY)

        contract = Contract(  # type: ignore[call-arg]
            name=data.name,  # type: ignore[union-attr]
            code=data.code,  # type: ignore[union-attr]
            description=data.description,  # type: ignore[union-attr]
            client_name=data.client_name,  # type: ignore[union-attr]
            client_contact=data.client_contact,  # type: ignore[union-attr]
            client_email=data.client_email,  # type: ignore[union-attr]
            is_active=data.is_active,  # type: ignore[union-attr]
            start_date=data.start_date,  # type: ignore[union-attr]
            end_date=data.end_date,  # type: ignore[union-attr]
            display_order=data.display_order,  # type: ignore[union-attr]
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        self.db.add(contract)
        await self.db.commit()
        await self.db.refresh(contract)
        await invalidate_tenant_cache(tenant_id, "form_config")
        track_metric("form_config.mutation", 1)

        await record_audit_event(
            db=self.db,
            entity_type="contract",
            entity_id=contract.id,
            action="created",
            user_id=user_id,
            details={"name": contract.name, "code": contract.code},
            request_id=request_id,
        )

        return contract

    async def get_contract(
        self,
        contract_id: int,
        *,
        tenant_id: int,
    ) -> Contract:
        """Get a contract by ID, scoped to tenant."""
        return await self._get_or_raise(Contract, contract_id, tenant_id=tenant_id)

    async def update_contract(
        self,
        contract_id: int,
        *,
        data: BaseModel,
        user_id: int,
        tenant_id: int,
        request_id: str,
    ) -> Contract:
        """Update a contract."""
        contract = await self._get_or_raise(Contract, contract_id, tenant_id=tenant_id)

        update_data = apply_updates(contract, data)
        contract.updated_by_id = user_id

        await self.db.commit()
        await self.db.refresh(contract)
        await invalidate_tenant_cache(tenant_id, "form_config")
        track_metric("form_config.mutation", 1)

        await record_audit_event(
            db=self.db,
            entity_type="contract",
            entity_id=contract.id,
            action="updated",
            user_id=user_id,
            details=update_data,
            request_id=request_id,
        )

        return contract

    async def delete_contract(
        self,
        contract_id: int,
        *,
        user_id: int,
        tenant_id: int,
        request_id: str,
    ) -> None:
        """Delete a contract."""
        contract = await self._get_or_raise(Contract, contract_id, tenant_id=tenant_id)

        await record_audit_event(
            db=self.db,
            entity_type="contract",
            entity_id=contract.id,
            action="deleted",
            user_id=user_id,
            details={"name": contract.name},
            request_id=request_id,
        )

        await self.db.delete(contract)
        await self.db.commit()
        await invalidate_tenant_cache(tenant_id, "form_config")
        track_metric("form_config.mutation", 1)

    # ================================================================== #
    #  System Setting methods                                              #
    # ================================================================== #

    async def list_settings(
        self,
        *,
        tenant_id: int,
        category: str | None = None,
    ) -> Sequence[SystemSetting]:
        """List all system settings for a tenant."""
        query = select(SystemSetting).where(SystemSetting.tenant_id == tenant_id)
        if category:
            query = query.where(SystemSetting.category == category)
        query = query.order_by(SystemSetting.category, SystemSetting.key)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_setting(
        self,
        *,
        data: BaseModel,
        user_id: int,
        tenant_id: int,
    ) -> SystemSetting:
        """Create a new system setting."""
        existing = await self.db.execute(
            select(SystemSetting).where(SystemSetting.key == data.key)  # type: ignore[union-attr]
        )
        if existing.scalar_one_or_none():
            raise ConflictError(ErrorCode.DUPLICATE_ENTITY)

        setting = SystemSetting(  # type: ignore[call-arg]
            key=data.key,  # type: ignore[union-attr]
            value=data.value,  # type: ignore[union-attr]
            category=data.category,  # type: ignore[union-attr]
            description=data.description,  # type: ignore[union-attr]
            value_type=data.value_type,  # type: ignore[union-attr]
            is_public=data.is_public,  # type: ignore[union-attr]
            is_editable=data.is_editable,  # type: ignore[union-attr]
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        self.db.add(setting)
        await self.db.commit()
        await self.db.refresh(setting)
        await invalidate_tenant_cache(tenant_id, "form_config")
        track_metric("form_config.mutation", 1)
        return setting

    async def update_setting(
        self,
        key: str,
        *,
        data: BaseModel,
        user_id: int,
        tenant_id: int,
    ) -> SystemSetting:
        """Update a system setting by key."""
        result = await self.db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        if not setting:
            raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
        if not setting.is_editable:
            raise AuthorizationError(ErrorCode.PERMISSION_DENIED)

        apply_updates(setting, data)
        setting.updated_by_id = user_id

        await self.db.commit()
        await self.db.refresh(setting)
        await invalidate_tenant_cache(tenant_id, "form_config")
        track_metric("form_config.mutation", 1)
        return setting

    # ================================================================== #
    #  Lookup Option methods                                               #
    # ================================================================== #

    async def list_lookup_options(
        self,
        category: str,
        *,
        tenant_id: int,
        is_active: bool | None = True,
    ) -> Sequence[LookupOption]:
        """List lookup options by category."""
        query = select(LookupOption).where(
            LookupOption.category == category,
            LookupOption.tenant_id == tenant_id,
        )
        if is_active is not None:
            query = query.where(LookupOption.is_active == is_active)
        query = query.order_by(LookupOption.display_order, LookupOption.label)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_lookup_option(
        self,
        category: str,
        *,
        data: BaseModel,
        tenant_id: int,
    ) -> LookupOption:
        """Create a new lookup option."""
        if getattr(data, "category", None) != category:
            data.category = category  # type: ignore[union-attr]

        option = LookupOption(  # type: ignore[call-arg]
            category=data.category,  # type: ignore[union-attr]
            code=data.code,  # type: ignore[union-attr]
            label=data.label,  # type: ignore[union-attr]
            description=data.description,  # type: ignore[union-attr]
            is_active=data.is_active,  # type: ignore[union-attr]
            display_order=data.display_order,  # type: ignore[union-attr]
            parent_id=data.parent_id,  # type: ignore[union-attr]
        )
        self.db.add(option)
        await self.db.commit()
        await self.db.refresh(option)
        await invalidate_tenant_cache(tenant_id, "form_config")
        track_metric("form_config.mutation", 1)
        return option

    async def update_lookup_option(
        self,
        category: str,
        option_id: int,
        *,
        data: BaseModel,
        tenant_id: int,
    ) -> LookupOption:
        """Update a lookup option."""
        result = await self.db.execute(
            select(LookupOption)
            .where(LookupOption.id == option_id)
            .where(LookupOption.category == category)
        )
        option = result.scalar_one_or_none()
        if not option:
            raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)

        apply_updates(option, data, set_updated_at=False)

        await self.db.commit()
        await self.db.refresh(option)
        await invalidate_tenant_cache(tenant_id, "form_config")
        track_metric("form_config.mutation", 1)
        return option

    async def delete_lookup_option(
        self,
        category: str,
        option_id: int,
        *,
        tenant_id: int,
    ) -> None:
        """Delete a lookup option."""
        result = await self.db.execute(
            select(LookupOption)
            .where(LookupOption.id == option_id)
            .where(LookupOption.category == category)
        )
        option = result.scalar_one_or_none()
        if not option:
            raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)

        await self.db.delete(option)
        await self.db.commit()
        await invalidate_tenant_cache(tenant_id, "form_config")
        track_metric("form_config.mutation", 1)
