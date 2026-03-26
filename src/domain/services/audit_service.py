"""Audit domain service.

Encapsulates all business logic and data access for audit templates,
sections, questions, runs, responses, and findings.  The API route
handlers delegate to this service so they remain thin
(parse request → call service → return response).

The standalone ``record_audit_event`` helper is kept at module level
for backward compatibility with other modules that import it directly.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.exceptions import NotFoundError, ValidationError
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
from src.domain.models.audit_log import AuditEvent
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.risk_register import EnterpriseRisk
from src.domain.services.audit_scoring_service import AuditScoringService
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_business_event, track_metric

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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
    "subcategory",
    "tags",
    "estimated_duration",
    "pass_threshold",
    "template_status",
}

_TEMPLATE_EXCLUDED_UPDATE_FIELDS = frozenset(
    {"standard_ids", "is_active", "is_published", "standard_ids_json", "external_id"}
)

_QUESTION_JSON_REMAPS: dict[str, str] = {
    "options": "options_json",
    "evidence_requirements": "evidence_requirements_json",
    "conditional_logic": "conditional_logic_json",
    "clause_ids": "clause_ids_json",
    "control_ids": "control_ids_json",
    "assessor_guidance": "assessor_guidance_json",
    "training_materials": "training_materials_json",
}

_TEMPLATE_JSON_REMAPS: dict[str, str] = {
    "tags": "tags_json",
}

_FINDING_JSON_REMAPS: dict[str, str] = {
    "clause_ids": "clause_ids_json_legacy",
    "control_ids": "control_ids_json",
    "risk_ids": "risk_ids_json",
}

_CHOICE_QUESTION_TYPES = {"radio", "dropdown", "checkbox"}

_QUESTION_CLONE_FIELDS = (
    "question_text",
    "question_type",
    "description",
    "help_text",
    "is_required",
    "allow_na",
    "is_active",
    "max_score",
    "weight",
    "options_json",
    "min_value",
    "max_value",
    "decimal_places",
    "min_length",
    "max_length",
    "evidence_requirements_json",
    "conditional_logic_json",
    "clause_ids_json",
    "control_ids_json",
    "risk_category",
    "risk_weight",
    "sort_order",
    "guidance",
    "criticality",
    "regulatory_reference",
    "guidance_notes",
    "sign_off_required",
    "assessor_guidance_json",
    "training_materials_json",
    "failure_triggers_action",
)

_SECTION_CLONE_FIELDS = (
    "title",
    "description",
    "sort_order",
    "weight",
    "is_repeatable",
    "max_repeats",
    "is_active",
)

_TEMPLATE_CLONE_FIELDS = (
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
    "standard_ids_json",
    "subcategory",
    "tags_json",
    "estimated_duration",
    "pass_threshold",
)

# ---------------------------------------------------------------------------
# Value objects returned by the service
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PaginatedResult:
    items: list[Any]
    total: int
    page: int
    page_size: int
    pages: int


@dataclasses.dataclass(frozen=True)
class RunDetail:
    """Composite returned by :pymeth:`AuditService.get_run_detail`."""

    run: AuditRun
    template_name: str | None
    completion_percentage: float


# ---------------------------------------------------------------------------
# Standalone audit-event helper (backward-compatible public API)
# ---------------------------------------------------------------------------


async def record_audit_event(
    db: AsyncSession,
    event_type: str,
    entity_type: str,
    entity_id: str,
    action: str,
    description: str | None = None,
    payload: dict[str, Any] | None = None,
    user_id: int | None = None,
    actor_user_id: int | None = None,
    request_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> AuditEvent:
    """Record a system-wide audit event with canonical schema.

    Note: Currently logs the event for observability but does not persist
    to the database. Full persistence requires schema migration.
    """
    final_actor_user_id = actor_user_id if actor_user_id is not None else user_id

    event = AuditEvent(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        description=description,
        payload=payload,
        actor_user_id=final_actor_user_id,
        request_id=request_id,
        resource_type=resource_type or entity_type,
        resource_id=resource_id or str(entity_id),
        user_id=final_actor_user_id,
    )

    track_business_event("audit_completed", {"event_type": event_type, "entity_type": entity_type})

    return event


# ---------------------------------------------------------------------------
# AuditService
# ---------------------------------------------------------------------------


class AuditService:
    """Domain service encapsulating all audit-related business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_entity(
        self,
        model: type,
        entity_id: int,
        *,
        tenant_id: int | None = None,
    ) -> Any:
        """Fetch entity by PK, optionally scoped to *tenant_id*."""
        model_any: Any = model
        stmt = select(model).where(model_any.id == entity_id)
        if tenant_id is not None:
            stmt = stmt.where(
                or_(
                    model_any.tenant_id == tenant_id,
                    model_any.tenant_id.is_(None),
                )
            )
        result = await self.db.execute(stmt)
        entity = result.scalar_one_or_none()
        if entity is None:
            raise NotFoundError(f"{model.__name__} {entity_id} not found")
        return entity

    async def _paginate(self, query: Any, page: int, page_size: int) -> PaginatedResult:
        offset = (page - 1) * page_size
        count_q = select(func.count()).select_from(query.subquery())
        total: int = (await self.db.execute(count_q)).scalar_one()
        items = (await self.db.execute(query.offset(offset).limit(page_size))).scalars().all()
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        return PaginatedResult(
            items=list(items),
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    @staticmethod
    def _apply_dict(
        entity: object,
        data: dict[str, Any],
        *,
        exclude: set[str] | frozenset[str] | None = None,
        set_updated_at: bool = False,
    ) -> None:
        """Apply *data* values to a SQLAlchemy model instance."""
        for key, value in data.items():
            if exclude and key in exclude:
                continue
            setattr(entity, key, value)
        if set_updated_at and hasattr(entity, "updated_at"):
            entity.updated_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE

    @staticmethod
    def _remap_json_fields(data: dict[str, Any], remaps: dict[str, str]) -> dict[str, Any]:
        """Pop schema-level keys and re-insert under their model JSON column names."""
        result = dict(data)
        for schema_key, model_key in remaps.items():
            value = result.pop(schema_key, None)
            if value:
                result[model_key] = value
        return result

    @staticmethod
    def _apply_json_field_updates(
        entity: object,
        update_data: dict[str, Any],
        remaps: dict[str, str],
    ) -> set[str]:
        """Set JSON columns on *entity* from *update_data* and return handled keys."""
        handled: set[str] = set()
        for schema_key, model_key in remaps.items():
            if schema_key in update_data:
                setattr(entity, model_key, update_data[schema_key])
                handled.add(schema_key)
        return handled

    @staticmethod
    def _validate_publishable_template(template: AuditTemplate) -> None:
        """Raise ValidationError when a template is incomplete for publishing."""
        if not (template.name or "").strip():
            raise ValidationError("Template name is required before publishing")
        if not template.sections or not template.questions:
            raise ValidationError("Template must have at least one question to publish")

        for section in template.sections:
            if not (section.title or "").strip():
                raise ValidationError("Every section must have a title before publishing")
            if not section.questions:
                raise ValidationError(f"Section '{section.title}' must contain at least one question")
            for question in section.questions:
                if not (question.question_text or "").strip():
                    raise ValidationError("Every question must include question text before publishing")
                if (question.weight or 0) <= 0:
                    raise ValidationError(f"Question '{question.question_text}' must have a weight greater than zero")
                if question.question_type in _CHOICE_QUESTION_TYPES:
                    options = question.options_json or []
                    if len(options) < 2:
                        raise ValidationError(
                            f"Question '{question.question_text}' must define at least two answer options"
                        )
                    for option in options:
                        if not isinstance(option, dict):
                            raise ValidationError(
                                f"Question '{question.question_text}' contains an invalid answer option"
                            )
                        if not str(option.get("label", "")).strip() or not str(option.get("value", "")).strip():
                            raise ValidationError(
                                f"Question '{question.question_text}' contains an incomplete answer option"
                            )

    # ==================================================================
    # Template methods
    # ==================================================================

    async def list_templates(
        self,
        tenant_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        category: str | None = None,
        audit_type: str | None = None,
        is_published: bool | None = None,
    ) -> PaginatedResult:
        query = (
            select(AuditTemplate)
            .options(selectinload(AuditTemplate.sections).selectinload(AuditSection.questions))
            .where(
                AuditTemplate.is_active == True,  # noqa: E712
                AuditTemplate.archived_at.is_(None),
                or_(
                    AuditTemplate.tenant_id == tenant_id,
                    AuditTemplate.tenant_id.is_(None),
                ),
            )
        )
        if search:
            pattern = f"%{search}%"
            query = query.where((AuditTemplate.name.ilike(pattern)) | (AuditTemplate.description.ilike(pattern)))
        if category:
            query = query.where(AuditTemplate.category == category)
        if audit_type:
            query = query.where(AuditTemplate.audit_type == audit_type)
        if is_published is not None:
            query = query.where(AuditTemplate.is_published == is_published)
        query = query.order_by(AuditTemplate.name)
        return await self._paginate(query, page, page_size)

    async def create_template(
        self,
        data: dict[str, Any],
        *,
        standard_ids: list[Any] | None,
        user_id: int,
        tenant_id: int,
    ) -> AuditTemplate:
        template = AuditTemplate(
            **data,
            standard_ids_json=standard_ids,
            created_by_id=user_id,
            tenant_id=tenant_id,
        )
        template.reference_number = await ReferenceNumberService.generate(
            self.db,
            "audit_template",
            AuditTemplate,
        )
        self.db.add(template)
        await self.db.flush()
        await self.db.refresh(template)
        await invalidate_tenant_cache(tenant_id, "audits")

        await record_audit_event(
            self.db,
            event_type="audit_template.created",
            entity_type="audit_template",
            entity_id=str(template.id),
            action="create",
            description=f"Template '{template.name}' created",
            actor_user_id=user_id,
        )
        return template

    async def list_archived_templates(
        self,
        tenant_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult:
        query = (
            select(AuditTemplate)
            .where(
                AuditTemplate.archived_at.isnot(None),
                or_(
                    AuditTemplate.tenant_id == tenant_id,
                    AuditTemplate.tenant_id.is_(None),
                ),
            )
            .order_by(AuditTemplate.archived_at.desc())
        )
        return await self._paginate(query, page, page_size)

    async def purge_expired_templates(
        self,
        tenant_id: int,
        actor_user_id: int,
    ) -> tuple[int, list[str]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        result = await self.db.execute(
            select(AuditTemplate).where(
                AuditTemplate.archived_at.isnot(None),
                AuditTemplate.archived_at < cutoff,
                or_(
                    AuditTemplate.tenant_id == tenant_id,
                    AuditTemplate.tenant_id.is_(None),
                ),
            )
        )
        expired = result.scalars().all()
        purged_count = len(expired)
        purged_names = [t.name for t in expired]

        for template in expired:
            await self.db.delete(template)

        if purged_count > 0:
            await self.db.flush()
            await record_audit_event(
                self.db,
                event_type="audit_template.purge",
                entity_type="audit_template",
                entity_id="batch",
                action="purge",
                description=f"Purged {purged_count} expired archived template(s)",
                actor_user_id=actor_user_id,
                payload={"purged_templates": purged_names},
            )

        return purged_count, purged_names

    async def get_template_detail(
        self,
        template_id: int,
        tenant_id: int,
    ) -> AuditTemplate:
        result = await self.db.execute(
            select(AuditTemplate)
            .options(
                selectinload(AuditTemplate.sections).selectinload(AuditSection.questions),
                selectinload(AuditTemplate.questions),
            )
            .where(
                AuditTemplate.id == template_id,
                or_(
                    AuditTemplate.tenant_id == tenant_id,
                    AuditTemplate.tenant_id.is_(None),
                ),
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError(f"AuditTemplate {template_id} not found")
        return template

    async def update_template(
        self,
        template_id: int,
        update_data: dict[str, Any],
        *,
        tenant_id: int,
        actor_user_id: int,
    ) -> AuditTemplate:
        template: AuditTemplate = await self._get_entity(
            AuditTemplate,
            template_id,
            tenant_id=tenant_id,
        )

        if template.is_published:
            template.version += 1
            template.is_published = False

        # Remap JSON shorthand names to actual column names
        for short, col in _TEMPLATE_JSON_REMAPS.items():
            if short in update_data:
                update_data[col] = update_data.pop(short)

        # Determine trackable changes (only fields in the allow-list)
        trackable = {k: v for k, v in update_data.items() if k in TEMPLATE_UPDATE_ALLOWED_FIELDS}
        if "standard_ids" in update_data:
            trackable["standard_ids_json"] = update_data["standard_ids"]

        changed_fields = [f for f, v in trackable.items() if getattr(template, f, None) != v]

        self._apply_dict(
            template,
            update_data,
            exclude=_TEMPLATE_EXCLUDED_UPDATE_FIELDS,
            set_updated_at=True,
        )
        if "standard_ids" in update_data:
            template.standard_ids_json = update_data["standard_ids"]

        await self.db.flush()
        await self.db.refresh(template)
        await invalidate_tenant_cache(tenant_id, "audits")

        if changed_fields:
            await record_audit_event(
                self.db,
                event_type="audit_template.updated",
                entity_type="audit_template",
                entity_id=str(template.id),
                action="update",
                description=(f"Template '{template.name}' updated: " f"{', '.join(changed_fields)}"),
                actor_user_id=actor_user_id,
                payload={"changed_fields": changed_fields},
            )

        return template

    async def publish_template(
        self,
        template_id: int,
        *,
        tenant_id: int,
        actor_user_id: int,
    ) -> AuditTemplate:
        result = await self.db.execute(
            select(AuditTemplate)
            .options(
                selectinload(AuditTemplate.questions),
                selectinload(AuditTemplate.sections).selectinload(AuditSection.questions),
            )
            .where(
                AuditTemplate.id == template_id,
                or_(
                    AuditTemplate.tenant_id == tenant_id,
                    AuditTemplate.tenant_id.is_(None),
                ),
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError(f"AuditTemplate {template_id} not found")

        self._validate_publishable_template(template)
        question_count = len(template.questions)

        template.is_published = True
        await self.db.flush()
        await self.db.refresh(template)

        await record_audit_event(
            self.db,
            event_type="audit_template.published",
            entity_type="audit_template",
            entity_id=str(template.id),
            action="publish",
            description=(f"Template '{template.name}' published " f"(v{template.version}, {question_count} questions)"),
            actor_user_id=actor_user_id,
        )
        return template

    async def clone_template(
        self,
        template_id: int,
        *,
        user_id: int,
        tenant_id: int,
    ) -> AuditTemplate:
        result = await self.db.execute(
            select(AuditTemplate)
            .options(
                selectinload(AuditTemplate.sections).selectinload(AuditSection.questions),
                selectinload(AuditTemplate.questions),
            )
            .where(
                AuditTemplate.id == template_id,
                or_(
                    AuditTemplate.tenant_id == tenant_id,
                    AuditTemplate.tenant_id.is_(None),
                ),
            )
        )
        original = result.scalar_one_or_none()
        if not original:
            raise NotFoundError(f"AuditTemplate {template_id} not found")

        ref = await ReferenceNumberService.generate(
            self.db,
            "audit_template",
            AuditTemplate,
        )

        clone_kwargs = {f: getattr(original, f) for f in _TEMPLATE_CLONE_FIELDS}
        cloned = AuditTemplate(
            name=f"Copy of {original.name}",
            **clone_kwargs,
            is_active=True,
            is_published=False,
            created_by_id=user_id,
            reference_number=ref,
            tenant_id=tenant_id,
        )
        self.db.add(cloned)
        await self.db.flush()

        for orig_section in original.sections:
            sec_kwargs = {f: getattr(orig_section, f) for f in _SECTION_CLONE_FIELDS}
            cloned_section = AuditSection(
                template_id=cloned.id,
                **sec_kwargs,
            )
            self.db.add(cloned_section)
            await self.db.flush()

            for orig_q in orig_section.questions:
                q_kwargs = {f: getattr(orig_q, f) for f in _QUESTION_CLONE_FIELDS}
                self.db.add(
                    AuditQuestion(
                        template_id=cloned.id,
                        section_id=cloned_section.id,
                        **q_kwargs,
                    )
                )

        for orig_q in original.questions:
            if orig_q.section_id is None:
                q_kwargs = {f: getattr(orig_q, f) for f in _QUESTION_CLONE_FIELDS}
                self.db.add(
                    AuditQuestion(
                        template_id=cloned.id,
                        section_id=None,
                        **q_kwargs,
                    )
                )

        await self.db.flush()
        await self.db.refresh(cloned)
        return cloned

    async def archive_template(
        self,
        template_id: int,
        *,
        tenant_id: int,
        actor_user_id: int,
    ) -> AuditTemplate:
        result = await self.db.execute(
            select(AuditTemplate).where(
                AuditTemplate.id == template_id,
                AuditTemplate.archived_at.is_(None),
                or_(
                    AuditTemplate.tenant_id == tenant_id,
                    AuditTemplate.tenant_id.is_(None),
                ),
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError(f"AuditTemplate {template_id} not found")

        template.archived_at = datetime.now(timezone.utc)
        template.archived_by_id = actor_user_id
        template.is_active = False
        await self.db.flush()
        await invalidate_tenant_cache(tenant_id, "audits")

        await record_audit_event(
            self.db,
            event_type="audit_template.archived",
            entity_type="audit_template",
            entity_id=str(template_id),
            action="archive",
            description=(f"Template '{template.name}' archived " "(recoverable for 30 days)"),
            actor_user_id=actor_user_id,
        )
        return template

    async def restore_template(
        self,
        template_id: int,
        *,
        tenant_id: int,
        actor_user_id: int,
    ) -> AuditTemplate:
        result = await self.db.execute(
            select(AuditTemplate).where(
                AuditTemplate.id == template_id,
                AuditTemplate.archived_at.isnot(None),
                or_(
                    AuditTemplate.tenant_id == tenant_id,
                    AuditTemplate.tenant_id.is_(None),
                ),
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError(f"AuditTemplate {template_id} not found")

        template.archived_at = None
        template.archived_by_id = None
        template.is_active = True
        await self.db.flush()
        await self.db.refresh(template)

        await record_audit_event(
            self.db,
            event_type="audit_template.restored",
            entity_type="audit_template",
            entity_id=str(template_id),
            action="restore",
            description=f"Template '{template.name}' restored from archive",
            actor_user_id=actor_user_id,
        )
        return template

    async def permanently_delete_template(
        self,
        template_id: int,
        *,
        tenant_id: int,
        actor_user_id: int,
    ) -> None:
        result = await self.db.execute(
            select(AuditTemplate).where(
                AuditTemplate.id == template_id,
                AuditTemplate.archived_at.isnot(None),
                or_(
                    AuditTemplate.tenant_id == tenant_id,
                    AuditTemplate.tenant_id.is_(None),
                ),
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError(f"AuditTemplate {template_id} not found")

        template_name = template.name
        await self.db.delete(template)
        await self.db.flush()
        await invalidate_tenant_cache(tenant_id, "audits")

        await record_audit_event(
            self.db,
            event_type="audit_template.permanently_deleted",
            entity_type="audit_template",
            entity_id=str(template_id),
            action="permanent_delete",
            description=f"Template '{template_name}' permanently deleted",
            actor_user_id=actor_user_id,
        )

    # ==================================================================
    # Section methods
    # ==================================================================

    async def create_section(
        self,
        template_id: int,
        data: dict[str, Any],
        *,
        tenant_id: int,
    ) -> AuditSection:
        await self._get_entity(AuditTemplate, template_id, tenant_id=tenant_id)

        section = AuditSection(template_id=template_id, **data)
        self.db.add(section)
        await self.db.flush()

        refreshed = await self.db.execute(
            select(AuditSection).options(selectinload(AuditSection.questions)).where(AuditSection.id == section.id)
        )
        return refreshed.scalar_one()

    async def update_section(
        self,
        section_id: int,
        update_data: dict[str, Any],
        *,
        tenant_id: int,
    ) -> AuditSection:
        result = await self.db.execute(
            select(AuditSection).options(selectinload(AuditSection.questions)).where(AuditSection.id == section_id)
        )
        section = result.scalar_one_or_none()
        if not section:
            raise NotFoundError(f"AuditSection {section_id} not found")

        await self._get_entity(
            AuditTemplate,
            section.template_id,
            tenant_id=tenant_id,
        )

        self._apply_dict(section, update_data)
        await self.db.flush()

        refreshed = await self.db.execute(
            select(AuditSection).options(selectinload(AuditSection.questions)).where(AuditSection.id == section.id)
        )
        return refreshed.scalar_one()

    async def delete_section(
        self,
        section_id: int,
        *,
        tenant_id: int,
    ) -> None:
        section: AuditSection = await self._get_entity(AuditSection, section_id)
        await self._get_entity(
            AuditTemplate,
            section.template_id,
            tenant_id=tenant_id,
        )
        section.is_active = False
        await self.db.flush()

    # ==================================================================
    # Question methods
    # ==================================================================

    async def create_question(
        self,
        template_id: int,
        data: dict[str, Any],
        *,
        tenant_id: int,
    ) -> AuditQuestion:
        await self._get_entity(AuditTemplate, template_id, tenant_id=tenant_id)

        if data.get("section_id") is not None:
            sec_result = await self.db.execute(
                select(AuditSection).where(
                    AuditSection.id == data["section_id"],
                    AuditSection.template_id == template_id,
                )
            )
            if not sec_result.scalar_one_or_none():
                raise ValidationError("Section does not belong to this template")

        question_dict = self._remap_json_fields(data, _QUESTION_JSON_REMAPS)

        question = AuditQuestion(template_id=template_id, **question_dict)
        self.db.add(question)
        await self.db.flush()
        await self.db.refresh(question)
        return question

    async def update_question(
        self,
        question_id: int,
        update_data: dict[str, Any],
        *,
        tenant_id: int,
    ) -> AuditQuestion:
        question: AuditQuestion = await self._get_entity(
            AuditQuestion,
            question_id,
        )
        await self._get_entity(
            AuditTemplate,
            question.template_id,
            tenant_id=tenant_id,
        )

        handled = self._apply_json_field_updates(
            question,
            update_data,
            _QUESTION_JSON_REMAPS,
        )
        self._apply_dict(question, update_data, exclude=handled)

        await self.db.flush()
        await self.db.refresh(question)
        return question

    async def delete_question(
        self,
        question_id: int,
        *,
        tenant_id: int,
    ) -> None:
        question: AuditQuestion = await self._get_entity(
            AuditQuestion,
            question_id,
        )
        await self._get_entity(
            AuditTemplate,
            question.template_id,
            tenant_id=tenant_id,
        )
        question.is_active = False
        await self.db.flush()

    # ==================================================================
    # Run methods
    # ==================================================================

    async def list_runs(
        self,
        tenant_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
        status_filter: str | None = None,
        template_id: int | None = None,
        assigned_to_id: int | None = None,
    ) -> PaginatedResult:
        query = (
            select(AuditRun)
            .options(selectinload(AuditRun.template))
            .where(or_(AuditRun.tenant_id == tenant_id, AuditRun.tenant_id.is_(None)))
        )
        if status_filter:
            query = query.where(AuditRun.status == status_filter)
        if template_id:
            query = query.where(AuditRun.template_id == template_id)
        if assigned_to_id:
            query = query.where(AuditRun.assigned_to_id == assigned_to_id)
        query = query.order_by(AuditRun.created_at.desc())
        return await self._paginate(query, page, page_size)

    async def create_run(
        self,
        data: dict[str, Any],
        *,
        user_id: int,
        tenant_id: int,
    ) -> AuditRun:
        _span = tracer.start_span("create_audit_run") if tracer else None
        if _span:
            _span.set_attribute("tenant_id", str(tenant_id or 0))

        result = await self.db.execute(
            select(AuditTemplate).where(
                and_(
                    AuditTemplate.id == data["template_id"],
                    AuditTemplate.is_published == True,  # noqa: E712
                    AuditTemplate.is_active == True,  # noqa: E712
                )
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError("Published template not found")

        run = AuditRun(
            **data,
            template_version=template.version,
            status=AuditStatus.SCHEDULED,
            created_by_id=user_id,
            tenant_id=tenant_id,
        )
        run.reference_number = await ReferenceNumberService.generate(
            self.db,
            "audit_run",
            AuditRun,
        )

        self.db.add(run)
        await self.db.flush()
        await self.db.refresh(run)
        await invalidate_tenant_cache(tenant_id, "audits")

        if _span:
            _span.end()
        return run

    async def get_run_detail(
        self,
        run_id: int,
        tenant_id: int,
    ) -> RunDetail:
        result = await self.db.execute(
            select(AuditRun)
            .options(
                selectinload(AuditRun.responses),
                selectinload(AuditRun.findings),
                selectinload(AuditRun.template),
            )
            .where(
                AuditRun.id == run_id,
                or_(AuditRun.tenant_id == tenant_id, AuditRun.tenant_id.is_(None)),
            )
        )
        run = result.scalar_one_or_none()
        if not run:
            raise NotFoundError(f"AuditRun {run_id} not found")

        template_name = run.template.name if run.template else None
        completion_pct = 0.0

        if run.template:
            total_questions = await self.db.scalar(
                select(func.count())
                .select_from(AuditQuestion)
                .where(
                    and_(
                        AuditQuestion.template_id == run.template_id,
                        AuditQuestion.is_active == True,  # noqa: E712
                    )
                )
            )
            answered = len(run.responses)
            if total_questions and total_questions > 0:
                completion_pct = answered / total_questions * 100

        return RunDetail(
            run=run,
            template_name=template_name,
            completion_percentage=completion_pct,
        )

    async def update_run(
        self,
        run_id: int,
        update_data: dict[str, Any],
        *,
        tenant_id: int,
    ) -> AuditRun:
        run: AuditRun = await self._get_entity(
            AuditRun,
            run_id,
            tenant_id=tenant_id,
        )

        if "status" in update_data:
            new_status = update_data["status"]
            if new_status == AuditStatus.COMPLETED.value:
                raise ValidationError("Cannot set status to completed directly; " "use the complete endpoint")
            try:
                validated = AuditStatus(new_status)
            except ValueError:
                raise ValidationError(f"Invalid audit status: {new_status}")
            if validated == AuditStatus.IN_PROGRESS and run.started_at is None:
                run.started_at = datetime.now(timezone.utc)
            run.status = validated

        self._apply_dict(run, update_data, exclude={"status"})

        await self.db.flush()
        await self.db.refresh(run)
        await invalidate_tenant_cache(tenant_id, "audits")
        return run

    async def start_run(
        self,
        run_id: int,
        *,
        tenant_id: int,
    ) -> AuditRun:
        run: AuditRun = await self._get_entity(
            AuditRun,
            run_id,
            tenant_id=tenant_id,
        )
        if run.status != AuditStatus.SCHEDULED:
            raise ValidationError("Only scheduled runs can be started")

        run.status = AuditStatus.IN_PROGRESS
        run.started_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(run)
        return run

    @staticmethod
    def _response_display_value(response: AuditResponse) -> str:
        if response.response_value:
            return response.response_value
        if response.response_text:
            return response.response_text
        if response.response_number is not None:
            return str(response.response_number)
        if response.response_bool is not None:
            return "yes" if response.response_bool else "no"
        if response.response_date is not None:
            return response.response_date.isoformat()
        return ""

    @classmethod
    def _response_creates_finding(cls, question: AuditQuestion, response: AuditResponse) -> bool:
        if response.is_na:
            return False

        answer = cls._response_display_value(response).strip().lower()
        question_type = (question.question_type or "").lower()
        positive_answer = (question.positive_answer or "yes").lower()

        if question_type == "pass_fail":
            return answer == "fail"

        if question_type in {"yes_no", "checkbox"}:
            negative_answer = "no" if positive_answer == "yes" else "yes"
            return answer == negative_answer

        if response.score is not None and response.max_score is not None and response.score < response.max_score:
            return True

        options = question.options_json or []
        for option in options:
            if not isinstance(option, dict):
                continue
            option_value = str(option.get("value", "")).strip().lower()
            option_label = str(option.get("label", "")).strip().lower()
            if option.get("triggers_finding") and answer in {option_value, option_label}:
                return True

        return False

    @staticmethod
    def _derive_finding_severity(question: AuditQuestion, response: AuditResponse) -> str:
        answer = AuditService._response_display_value(response).strip().lower()
        for option in question.options_json or []:
            if not isinstance(option, dict):
                continue
            option_value = str(option.get("value", "")).strip().lower()
            option_label = str(option.get("label", "")).strip().lower()
            if answer in {option_value, option_label} and option.get("finding_severity"):
                return str(option["finding_severity"]).lower()

        if question.risk_weight is not None:
            if question.risk_weight >= 5:
                return "critical"
            if question.risk_weight >= 4:
                return "high"
            if question.risk_weight >= 2.5:
                return "medium"
            return "low"

        if question.criticality == "essential":
            return "high"
        return "medium"

    @staticmethod
    def _priority_from_severity(severity: str) -> CAPAPriority:
        if severity == "critical":
            return CAPAPriority.CRITICAL
        if severity == "high":
            return CAPAPriority.HIGH
        if severity == "low":
            return CAPAPriority.LOW
        return CAPAPriority.MEDIUM

    @staticmethod
    def _build_finding_description(run: AuditRun, question: AuditQuestion, response: AuditResponse) -> str:
        response_value = AuditService._response_display_value(response) or "No response captured"
        context_bits = []
        if run.assurance_scheme:
            context_bits.append(f"Scheme: {run.assurance_scheme}")
        if run.external_reference:
            context_bits.append(f"Reference: {run.external_reference}")
        if run.external_body_name:
            context_bits.append(f"Audited by: {run.external_body_name}")

        lines = [
            f"Question: {question.question_text}",
            f"Observed response: {response_value}",
        ]
        if response.notes:
            lines.append(f"Response notes: {response.notes}")
        if context_bits:
            lines.append(" | ".join(context_bits))
        return "\n".join(lines)

    async def _ensure_action_for_finding(
        self,
        *,
        run: AuditRun,
        finding: AuditFinding,
        actor_user_id: int,
    ) -> CAPAAction | None:
        if not finding.corrective_action_required:
            return None

        existing_result = await self.db.execute(
            select(CAPAAction).where(
                CAPAAction.tenant_id == run.tenant_id,
                CAPAAction.source_type == CAPASource.AUDIT_FINDING,
                CAPAAction.source_id == finding.id,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing

        action = CAPAAction(
            tenant_id=run.tenant_id,
            reference_number=await ReferenceNumberService.generate(self.db, "capa", CAPAAction),
            title=f"Action plan: {finding.title}"[:255],
            description=finding.description,
            capa_type=CAPAType.CORRECTIVE,
            status=CAPAStatus.OPEN,
            priority=self._priority_from_severity(finding.severity),
            source_type=CAPASource.AUDIT_FINDING,
            source_id=finding.id,
            created_by_id=actor_user_id,
            assigned_to_id=run.assigned_to_id,
            due_date=finding.corrective_action_due_date,
            iso_standard=run.assurance_scheme,
            clause_reference=run.external_reference,
        )
        self.db.add(action)
        await self.db.flush()
        return action

    async def _ensure_risk_for_finding(
        self,
        *,
        run: AuditRun,
        finding: AuditFinding,
        action: CAPAAction | None,
        actor_user_id: int,
    ) -> EnterpriseRisk | None:
        if finding.severity not in {"critical", "high"}:
            return None

        title = f"Audit escalation: {run.reference_number} / {finding.reference_number}"[:255]
        existing_result = await self.db.execute(
            select(EnterpriseRisk).where(
                EnterpriseRisk.tenant_id == run.tenant_id,
                EnterpriseRisk.title == title,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            linked_audits = set(existing.linked_audits or [])
            linked_audits.update([run.reference_number, finding.reference_number])
            existing.linked_audits = sorted(linked_audits)
            if action is not None:
                linked_actions = set(existing.linked_actions or [])
                linked_actions.add(action.reference_number)
                existing.linked_actions = sorted(linked_actions)
            if finding.id not in (finding.risk_ids_json or []):
                finding.risk_ids_json = sorted({*(finding.risk_ids_json or []), existing.id})
            return existing

        likelihood = 4 if finding.severity == "critical" else 3
        impact = 5 if finding.severity == "critical" else 4
        score = likelihood * impact

        risk = EnterpriseRisk(
            tenant_id=run.tenant_id,
            reference=await ReferenceNumberService.generate(self.db, "risk", EnterpriseRisk),
            title=title,
            description=finding.description,
            category="compliance",
            subcategory="audit_finding",
            source="audit_finding",
            context=f"{run.assurance_scheme or 'audit'}:{run.reference_number}",
            department="quality",
            location=run.location,
            process="audit remediation",
            inherent_likelihood=likelihood,
            inherent_impact=impact,
            inherent_score=score,
            residual_likelihood=max(1, likelihood - 1),
            residual_impact=impact,
            residual_score=max(1, (likelihood - 1) * impact),
            risk_appetite="cautious",
            appetite_threshold=12,
            is_within_appetite=score <= 12,
            treatment_strategy="treat",
            treatment_plan="Raised automatically from an audit finding requiring remediation.",
            risk_owner_id=run.assigned_to_id,
            status="open",
            review_frequency_days=30,
            next_review_date=datetime.now(timezone.utc) + timedelta(days=30),
            is_escalated=True,
            escalation_reason=f"Auto-escalated from {finding.reference_number}",
            escalation_date=datetime.now(timezone.utc),
            linked_audits=[run.reference_number, finding.reference_number],
            linked_actions=[action.reference_number] if action is not None else [],
            created_by=actor_user_id,
        )
        self.db.add(risk)
        await self.db.flush()
        finding.risk_ids_json = sorted({*(finding.risk_ids_json or []), risk.id})
        return risk

    async def _auto_generate_findings_actions_and_risks(
        self,
        *,
        run: AuditRun,
        template: AuditTemplate | None,
        actor_user_id: int,
    ) -> None:
        if template is None or not template.auto_create_findings:
            return

        question_result = await self.db.execute(
            select(AuditQuestion).where(
                AuditQuestion.template_id == run.template_id,
                AuditQuestion.is_active == True,  # noqa: E712
            )
        )
        question_map = {question.id: question for question in question_result.scalars().all()}
        existing_by_question = {finding.question_id: finding for finding in run.findings if finding.question_id is not None}

        for response in run.responses:
            question = question_map.get(response.question_id)
            if question is None or not self._response_creates_finding(question, response):
                continue

            finding = existing_by_question.get(question.id)
            if finding is None:
                finding = AuditFinding(
                    run_id=run.id,
                    question_id=question.id,
                    title=question.question_text[:300],
                    description=self._build_finding_description(run, question, response),
                    severity=self._derive_finding_severity(question, response),
                    finding_type="nonconformity",
                    status=FindingStatus.OPEN,
                    corrective_action_required=question.failure_triggers_action,
                    corrective_action_due_date=datetime.now(timezone.utc) + timedelta(days=30),
                    created_by_id=actor_user_id,
                    tenant_id=run.tenant_id,
                    clause_ids_json_legacy=question.clause_ids_json,
                    control_ids_json=question.control_ids_json,
                )
                finding.reference_number = await ReferenceNumberService.generate(
                    self.db,
                    "audit_finding",
                    AuditFinding,
                )
                self.db.add(finding)
                await self.db.flush()
                run.findings.append(finding)
                existing_by_question[question.id] = finding

            action = await self._ensure_action_for_finding(
                run=run,
                finding=finding,
                actor_user_id=actor_user_id,
            )
            await self._ensure_risk_for_finding(
                run=run,
                finding=finding,
                action=action,
                actor_user_id=actor_user_id,
            )

    async def complete_run(
        self,
        run_id: int,
        *,
        tenant_id: int,
        actor_user_id: int | None = None,
    ) -> AuditRun:
        result = await self.db.execute(
            select(AuditRun)
            .options(
                selectinload(AuditRun.responses),
                selectinload(AuditRun.findings),
                selectinload(AuditRun.template),
            )
            .where(
                AuditRun.id == run_id,
                or_(AuditRun.tenant_id == tenant_id, AuditRun.tenant_id.is_(None)),
            )
        )
        run = result.scalar_one_or_none()
        if not run:
            raise NotFoundError(f"AuditRun {run_id} not found")

        if run.status != AuditStatus.IN_PROGRESS:
            raise ValidationError("Only in-progress runs can be completed")

        score = AuditScoringService.calculate_run_score(run.responses)
        run.score = score.total_score
        run.max_score = score.max_score
        run.score_percentage = score.score_percentage

        template = run.template
        if template is None:
            template_result = await self.db.execute(select(AuditTemplate).where(AuditTemplate.id == run.template_id))
            template = template_result.scalar_one_or_none()
        if template and template.passing_score is not None:
            run.passed = run.score_percentage >= template.passing_score

        await self._auto_generate_findings_actions_and_risks(
            run=run,
            template=template,
            actor_user_id=actor_user_id or run.created_by_id or 1,
        )

        run.status = AuditStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(run)
        await invalidate_tenant_cache(tenant_id, "audits")
        track_metric("audits.completed")
        return run

    # ==================================================================
    # Response methods
    # ==================================================================

    async def create_audit_response(
        self,
        run_id: int,
        data: dict[str, Any],
        *,
        tenant_id: int,
    ) -> AuditResponse:
        run: AuditRun = await self._get_entity(
            AuditRun,
            run_id,
            tenant_id=tenant_id,
        )

        if run.status not in (AuditStatus.SCHEDULED, AuditStatus.IN_PROGRESS):
            raise ValidationError("Cannot add responses to a completed or cancelled run")

        if run.status == AuditStatus.SCHEDULED:
            run.status = AuditStatus.IN_PROGRESS
            run.started_at = datetime.now(timezone.utc)

        existing = await self.db.execute(
            select(AuditResponse).where(
                and_(
                    AuditResponse.run_id == run_id,
                    AuditResponse.question_id == data["question_id"],
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError("Response already exists for this question in this run")

        response = AuditResponse(run_id=run_id, **data)
        self.db.add(response)
        await self.db.flush()
        await self.db.refresh(response)
        return response

    async def update_audit_response(
        self,
        response_id: int,
        update_data: dict[str, Any],
        *,
        tenant_id: int,
    ) -> AuditResponse:
        result = await self.db.execute(
            select(AuditResponse).options(selectinload(AuditResponse.run)).where(AuditResponse.id == response_id)
        )
        response = result.scalar_one_or_none()

        if response:
            await self._get_entity(
                AuditRun,
                response.run_id,
                tenant_id=tenant_id,
            )

        if not response:
            raise NotFoundError(f"AuditResponse {response_id} not found")

        if response.run.status == AuditStatus.COMPLETED:
            raise ValidationError("Cannot update responses on a completed run")

        self._apply_dict(response, update_data)
        await self.db.flush()
        await self.db.refresh(response)
        return response

    # ==================================================================
    # Finding methods
    # ==================================================================

    async def list_findings(
        self,
        tenant_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
        status_filter: str | None = None,
        severity: str | None = None,
        run_id: int | None = None,
    ) -> PaginatedResult:
        query = select(AuditFinding).where(
            or_(
                AuditFinding.tenant_id == tenant_id,
                AuditFinding.tenant_id.is_(None),
            ),
        )
        if status_filter:
            query = query.where(AuditFinding.status == status_filter)
        if severity:
            query = query.where(AuditFinding.severity == severity)
        if run_id:
            query = query.where(AuditFinding.run_id == run_id)
        query = query.order_by(AuditFinding.created_at.desc())
        return await self._paginate(query, page, page_size)

    async def create_finding(
        self,
        run_id: int,
        data: dict[str, Any],
        *,
        user_id: int,
        tenant_id: int,
    ) -> AuditFinding:
        run: AuditRun = await self._get_entity(AuditRun, run_id, tenant_id=tenant_id)

        finding_dict = self._remap_json_fields(data, _FINDING_JSON_REMAPS)

        finding = AuditFinding(
            run_id=run_id,
            status=FindingStatus.OPEN,
            created_by_id=user_id,
            tenant_id=tenant_id,
            **finding_dict,
        )

        finding.reference_number = await ReferenceNumberService.generate(
            self.db,
            "audit_finding",
            AuditFinding,
        )

        self.db.add(finding)
        await self.db.flush()
        action = await self._ensure_action_for_finding(
            run=run,
            finding=finding,
            actor_user_id=user_id,
        )
        await self._ensure_risk_for_finding(
            run=run,
            finding=finding,
            action=action,
            actor_user_id=user_id,
        )
        await self.db.refresh(finding)
        await invalidate_tenant_cache(tenant_id, "audits")
        track_metric("audits.findings")
        return finding

    async def update_finding(
        self,
        finding_id: int,
        update_data: dict[str, Any],
        *,
        tenant_id: int,
        actor_user_id: int | None = None,
    ) -> AuditFinding:
        finding: AuditFinding = await self._get_entity(
            AuditFinding,
            finding_id,
            tenant_id=tenant_id,
        )

        handled = self._apply_json_field_updates(
            finding,
            update_data,
            _FINDING_JSON_REMAPS,
        )
        self._apply_dict(finding, update_data, exclude=handled)

        run: AuditRun = await self._get_entity(AuditRun, finding.run_id, tenant_id=tenant_id)
        action = await self._ensure_action_for_finding(
            run=run,
            finding=finding,
            actor_user_id=actor_user_id or finding.created_by_id or run.created_by_id or 1,
        )
        await self._ensure_risk_for_finding(
            run=run,
            finding=finding,
            action=action,
            actor_user_id=actor_user_id or finding.created_by_id or run.created_by_id or 1,
        )
        await self.db.flush()
        await self.db.refresh(finding)
        await invalidate_tenant_cache(tenant_id, "audits")
        return finding
