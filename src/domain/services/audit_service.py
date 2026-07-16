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
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.exceptions import NotFoundError, StateTransitionError, ValidationError
from src.domain.models.audit import (
    AuditFinding,
    AuditQuestion,
    AuditResponse,
    AuditRun,
    AuditSection,
    AuditStatus,
    AuditTemplate,
    FindingStatus,
    audit_finding_risks,
)
from src.domain.models.audit_log import AuditEvent
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.risk_register import EnterpriseRisk
from src.domain.models.user import User
from src.domain.services.audit_log_service import AuditLogService
from src.domain.services.audit_risk_gate import AUDIT_RISK_SEVERITIES, should_create_risk
from src.domain.services.audit_scoring_service import AuditScoringService
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_business_event, track_metric

logger = logging.getLogger(__name__)

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
    tenant_id: int | None = None,
) -> AuditEvent:
    """Record a system-wide audit event and persist an immutable AuditLogEntry.

    Bridges the lightweight ``AuditEvent`` API used by domain services into
    ``AuditLogService`` so Admin Audit Trail reflects CAPA / incident /
    complaint (and other) mutations. Persistence is flush-only so the caller's
    session/transaction (typically ``get_db``) owns the commit.

    When no tenant can be resolved, the event remains observability-only and a
    warning is logged — AuditLogEntry requires a non-null tenant_id.
    """
    final_actor_user_id = actor_user_id if actor_user_id is not None else user_id
    # Domain layer must not import infrastructure tenant_context (D09).
    # Callers pass tenant_id explicitly; without it we stay observability-only.
    resolved_tenant_id = tenant_id

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

    if resolved_tenant_id is None:
        logger.warning(
            "audit_bridge_skipped_no_tenant event_type=%s entity_type=%s entity_id=%s action=%s",
            event_type,
            entity_type,
            entity_id,
            action,
        )
        track_business_event(
            "audit_completed",
            {
                "event_type": event_type,
                "entity_type": entity_type,
                "persisted": "false",
            },
        )
        return event

    action_lower = (action or "").lower()
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    if action_lower == "delete":
        old_values = payload
    elif action_lower == "create":
        new_values = payload
    else:
        new_values = payload

    entry = await AuditLogService(db).log(
        tenant_id=resolved_tenant_id,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        user_id=final_actor_user_id,
        old_values=old_values,
        new_values=new_values,
        request_id=request_id,
        metadata={
            "event_type": event_type,
            "description": description,
            "resource_type": resource_type or entity_type,
            "resource_id": resource_id or str(entity_id),
        },
        entity_name=(description[:255] if description else None),
        action_category="data",
        commit=False,
    )
    event.id = int(entry.id)  # type: ignore[assignment]  # Optional[int] set after persist

    track_business_event(
        "audit_completed",
        {
            "event_type": event_type,
            "entity_type": entity_type,
            "persisted": "true",
            "audit_log_entry_id": str(entry.id),
        },
    )

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
        stmt: Any = select(model).where(model_any.id == entity_id)
        if tenant_id is not None:
            # Fail-closed: exact tenant match only. NULL tenant_id rows are not
            # visible when a tenant scope is provided (WCS C-01 / PR #574 follow-up).
            stmt = stmt.where(model_any.tenant_id == tenant_id)
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
                AuditTemplate.tenant_id == tenant_id,
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

    async def _is_external_audit_import_run(self, run: AuditRun) -> bool:
        template = run.__dict__.get("template")
        if template is None:
            template_result = await self.db.execute(select(AuditTemplate).where(AuditTemplate.id == run.template_id))
            template = template_result.scalar_one_or_none()
        if template is None:
            return False
        if template.audit_type == "external_import":
            return True
        return any(
            isinstance(candidate, str) and candidate.strip().lower() == "external_audit_intake"
            for candidate in (template.tags_json or [])
        )

    async def _ensure_run_is_executable(self, run: AuditRun) -> None:
        if await self._is_external_audit_import_run(run):
            raise ValidationError("Imported external audit outcomes cannot be executed from the audit run workflow")

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
        query = select(AuditRun).options(selectinload(AuditRun.template)).where(AuditRun.tenant_id == tenant_id)
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
                # Fail-closed: exact tenant match only (no OR IS NULL bleed).
                AuditRun.tenant_id == tenant_id,
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
            await self._ensure_run_is_executable(run)
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
        await self._ensure_run_is_executable(run)
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
        suggested_title: str | None = None,
        suggested_description: str | None = None,
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

        action_title = (suggested_title or f"Action plan: {finding.title}")[:255]
        action_desc = suggested_description or finding.description

        action = CAPAAction(
            tenant_id=run.tenant_id,
            reference_number=await ReferenceNumberService.generate(self.db, "capa", CAPAAction),
            title=action_title,
            description=action_desc,
            capa_type=CAPAType.CORRECTIVE,
            status=CAPAStatus.OPEN,
            priority=self._priority_from_severity(finding.severity),
            source_type=CAPASource.AUDIT_FINDING,
            source_id=finding.id,
            created_by_id=actor_user_id,
            assigned_to_id=run.assigned_to_id,
            due_date=(
                finding.corrective_action_due_date.replace(tzinfo=None)
                if finding.corrective_action_due_date and finding.corrective_action_due_date.tzinfo
                else finding.corrective_action_due_date
            ),
            iso_standard=run.assurance_scheme,
            clause_reference=run.external_reference,
        )
        self.db.add(action)
        await self.db.flush()
        return action

    _should_create_risk = staticmethod(should_create_risk)

    async def _link_risk_to_finding(self, finding: AuditFinding, risk: EnterpriseRisk) -> None:
        """Dual-write a finding/risk link during the JSON transition release."""
        await self.db.execute(
            pg_insert(audit_finding_risks)
            .values(audit_finding_id=finding.id, risk_id=risk.id)
            .on_conflict_do_nothing(
                index_elements=[
                    audit_finding_risks.c.audit_finding_id,
                    audit_finding_risks.c.risk_id,
                ]
            )
        )

        legacy_ids = getattr(finding, "_risk_ids_json", None)
        if legacy_ids is None:
            legacy_ids = finding.risk_ids_json
        finding.risk_ids_json = sorted({*(legacy_ids or []), risk.id})

        # Keep an already-loaded view-only relationship coherent for callers.
        loaded_risks = finding.__dict__.get("risks")
        if loaded_risks is not None and all(linked.id != risk.id for linked in loaded_risks):
            loaded_risks.append(risk)

    async def _ensure_risk_for_finding(
        self,
        *,
        run: AuditRun,
        finding: AuditFinding,
        action: CAPAAction | None,
        actor_user_id: int,
        suggested_title: str | None = None,
        external_import_triage_pending: bool = False,
        force_flag: bool = False,
    ) -> EnterpriseRisk | None:
        normalized_severity = (finding.severity or "").strip().lower()
        if force_flag and normalized_severity not in AUDIT_RISK_SEVERITIES:
            return None
        if not force_flag and not self._should_create_risk(finding):
            return None

        title = (suggested_title or f"Audit escalation: {run.reference_number} / {finding.reference_number}")[:255]
        source_result = await self.db.execute(
            select(EnterpriseRisk).where(
                EnterpriseRisk.tenant_id == run.tenant_id,
                cast(EnterpriseRisk.linked_audits, JSONB).contains(cast([finding.reference_number], JSONB)),
            )
        )
        existing = source_result.scalars().first()
        if existing is None:
            title_result = await self.db.execute(
                select(EnterpriseRisk).where(
                    EnterpriseRisk.tenant_id == run.tenant_id,
                    EnterpriseRisk.title == title,
                )
            )
            existing = title_result.scalars().first()
        if existing is not None:
            linked_audits = set(existing.linked_audits or [])
            linked_audits.update([run.reference_number, finding.reference_number])
            existing.linked_audits = sorted(linked_audits)
            if action is not None:
                linked_actions = set(existing.linked_actions or [])
                linked_actions.add(action.reference_number)
                existing.linked_actions = sorted(linked_actions)
            await self._link_risk_to_finding(finding, existing)
            return existing

        if normalized_severity == "critical":
            likelihood, impact = 4, 5
        elif normalized_severity == "high":
            likelihood, impact = 3, 4
        elif normalized_severity == "medium":
            likelihood, impact = 2, 3
        else:
            likelihood, impact = 1, 2
        score = likelihood * impact

        if external_import_triage_pending:
            risk_status = "identified"
            triage_plan = (
                "Raised from external audit import — review under Risk Register → Import triage "
                "before treating as a live register entry."
            )
            esc_reason = "Awaiting risk register triage (external audit import)."
            is_esc = False
            esc_date = None
            triage_flag = "pending"
        else:
            risk_status = "open"
            triage_plan = "Raised automatically from an audit finding requiring remediation."
            esc_reason = f"Auto-escalated from {finding.reference_number}"
            is_esc = True
            esc_date = datetime.now(timezone.utc).replace(tzinfo=None)
            triage_flag = None

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
            treatment_plan=triage_plan,
            risk_owner_id=run.assigned_to_id,
            status=risk_status,
            review_frequency_days=30,
            next_review_date=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30),
            is_escalated=is_esc,
            escalation_reason=esc_reason,
            escalation_date=esc_date,
            linked_audits=[run.reference_number, finding.reference_number],
            linked_actions=[action.reference_number] if action is not None else [],
            created_by=actor_user_id,
            suggestion_triage_status=triage_flag,
        )
        self.db.add(risk)
        await self.db.flush()
        await self._link_risk_to_finding(finding, risk)
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
        existing_by_question = {
            finding.question_id: finding for finding in run.findings if finding.question_id is not None
        }

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
                # Fail-closed: exact tenant match only (no OR IS NULL bleed).
                AuditRun.tenant_id == tenant_id,
            )
        )
        run = result.scalar_one_or_none()
        if not run:
            raise NotFoundError(f"AuditRun {run_id} not found")
        await self._ensure_run_is_executable(run)

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
        await self._ensure_run_is_executable(run)

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

        await self._ensure_run_is_executable(response.run)
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
            AuditFinding.tenant_id == tenant_id,
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

        suggested_action_title = finding_dict.pop("_suggested_action_title", None)
        suggested_action_description = finding_dict.pop("_suggested_action_description", None)
        suggested_risk_title = finding_dict.pop("_suggested_risk_title", None)
        external_import_triage_pending = bool(finding_dict.pop("_external_import_risk_triage_pending", False))
        # Strip any remaining internal keys that aren't AuditFinding columns
        finding_dict = {k: v for k, v in finding_dict.items() if not k.startswith("_")}

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
            suggested_title=suggested_action_title,
            suggested_description=suggested_action_description,
        )
        await self._ensure_risk_for_finding(
            run=run,
            finding=finding,
            action=action,
            actor_user_id=user_id,
            suggested_title=suggested_risk_title,
            external_import_triage_pending=external_import_triage_pending,
        )
        await self.db.refresh(finding)
        await invalidate_tenant_cache(tenant_id, "audits")
        await invalidate_tenant_cache(tenant_id, "capa")
        await invalidate_tenant_cache(tenant_id, "risk-register")
        await invalidate_tenant_cache(tenant_id, "risks")
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

        new_status = update_data.get("status")
        if new_status is not None:
            target_status = self._enum_value(new_status) or str(new_status)
            current_status = self._enum_value(finding.status) or FindingStatus.OPEN.value
            if target_status == FindingStatus.CLOSED.value and current_status != FindingStatus.CLOSED.value:
                await self._assert_no_open_capas_for_finding_close(finding)
            await self._assert_finding_lifecycle_chain_integrity(finding, target_status)

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

    async def flag_finding_to_organisational_risk(
        self,
        finding_id: int,
        *,
        tenant_id: int,
        actor_user_id: int,
        severity: str | None = None,
    ) -> AuditFinding:
        """Explicitly allocate a finding to the enterprise risk register.

        Used when operators escalate a significant issue (including positive/observation
        findings that would not auto-create risks). Idempotent when a linked risk already
        exists for the finding reference.
        """
        finding: AuditFinding = await self._get_entity(
            AuditFinding,
            finding_id,
            tenant_id=tenant_id,
        )
        run: AuditRun = await self._get_entity(AuditRun, finding.run_id, tenant_id=tenant_id)

        if severity:
            if severity not in {"critical", "high", "medium", "low"}:
                raise ValidationError("severity must be critical|high|medium|low when flagging to risk")
            finding.severity = severity
        elif finding.severity not in {"critical", "high", "medium", "low"}:
            # Observations / unset severity still need a registerable band when explicitly flagged.
            finding.severity = "high"

        action = await self._ensure_action_for_finding(
            run=run,
            finding=finding,
            actor_user_id=actor_user_id,
        )
        risk = await self._ensure_risk_for_finding(
            run=run,
            finding=finding,
            action=action,
            actor_user_id=actor_user_id,
            force_flag=True,
        )
        if risk is None:
            raise ValidationError("Unable to create organisational risk for finding")

        await self.db.flush()
        await self.db.refresh(finding)
        await invalidate_tenant_cache(tenant_id, "audits")
        await invalidate_tenant_cache(tenant_id, "risk-register")
        await invalidate_tenant_cache(tenant_id, "risks")
        track_metric("audits.findings.flag_risk")
        return finding

    async def _resolve_user_id_by_email(
        self,
        email: str,
        *,
        tenant_id: int,
    ) -> int:
        """Resolve a tenant-scoped user id by email; raise ValidationError if missing."""
        normalized = email.strip().lower()
        result = await self.db.execute(
            select(User).where(
                func.lower(User.email) == normalized,
                User.tenant_id == tenant_id,
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise ValidationError(f"No user found with email '{email}' in this tenant")
        return user.id

    async def create_capa_for_finding(
        self,
        finding_id: int,
        *,
        tenant_id: int,
        actor_user_id: int,
        title: str | None = None,
        description: str | None = None,
        assignee_email: str | None = None,
    ) -> CAPAAction:
        """Create a CAPA linked to an audit finding (primary finding→CAPA CUJ).

        Idempotent: if a CAPA already exists for this finding under the tenant,
        return the existing action. Explicit create always proceeds even when
        ``corrective_action_required`` is false (unlike ``_ensure_action_for_finding``).
        """
        finding: AuditFinding = await self._get_entity(
            AuditFinding,
            finding_id,
            tenant_id=tenant_id,
        )
        run: AuditRun = await self._get_entity(AuditRun, finding.run_id, tenant_id=tenant_id)

        existing_result = await self.db.execute(
            select(CAPAAction).where(
                CAPAAction.tenant_id == tenant_id,
                CAPAAction.source_type == CAPASource.AUDIT_FINDING,
                CAPAAction.source_id == finding.id,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing

        assigned_to_id = run.assigned_to_id
        if assignee_email:
            assigned_to_id = await self._resolve_user_id_by_email(
                assignee_email,
                tenant_id=tenant_id,
            )

        finding.corrective_action_required = True

        action_title = (title or f"Action plan: {finding.title}")[:255]
        action_desc = finding.description if description is None else description

        action = CAPAAction(
            tenant_id=tenant_id,
            reference_number=await ReferenceNumberService.generate(self.db, "capa", CAPAAction),
            title=action_title,
            description=action_desc,
            capa_type=CAPAType.CORRECTIVE,
            status=CAPAStatus.OPEN,
            priority=self._priority_from_severity(finding.severity),
            source_type=CAPASource.AUDIT_FINDING,
            source_id=finding.id,
            created_by_id=actor_user_id,
            assigned_to_id=assigned_to_id,
            due_date=(
                finding.corrective_action_due_date.replace(tzinfo=None)
                if finding.corrective_action_due_date and finding.corrective_action_due_date.tzinfo
                else finding.corrective_action_due_date
            ),
            iso_standard=run.assurance_scheme,
            clause_reference=run.external_reference,
        )
        self.db.add(action)
        await self.db.flush()
        await self.db.refresh(action)
        await invalidate_tenant_cache(tenant_id, "audits")
        await invalidate_tenant_cache(tenant_id, "capa")
        track_metric("audits.findings.create_capa")
        await record_audit_event(
            db=self.db,
            event_type="capa.created_from_finding",
            entity_type="capa",
            entity_id=str(action.id),
            action="create",
            description=(
                f"CAPA {action.reference_number} created from finding " f"{finding.reference_number or finding.id}"
            ),
            payload={"finding_id": finding.id, "title": action.title},
            user_id=actor_user_id,
            tenant_id=tenant_id,
        )
        return action

    # ------------------------------------------------------------------
    # CAPA → finding closure bridge (CUJ-AUDIT-CAPA-CLOSURE-BRIDGE)
    # ------------------------------------------------------------------

    @staticmethod
    def _enum_value(value: Any) -> str | None:
        if value is None:
            return None
        return value.value if hasattr(value, "value") else str(value)

    @classmethod
    def _capa_is_audit_finding_source(cls, capa: CAPAAction) -> bool:
        return cls._enum_value(capa.source_type) == CAPASource.AUDIT_FINDING.value and capa.source_id is not None

    @classmethod
    def _target_finding_status_for_capa(cls, capa_status: Any) -> FindingStatus | None:
        status_val = cls._enum_value(capa_status)
        if status_val == CAPAStatus.VERIFICATION.value:
            return FindingStatus.PENDING_VERIFICATION
        if status_val == CAPAStatus.CLOSED.value:
            return FindingStatus.CLOSED
        return None

    async def _assert_no_open_capas_for_finding_close(self, finding: AuditFinding) -> None:
        """Fail closed when closing a finding while linked CAPA actions remain open."""
        siblings_result = await self.db.execute(
            select(CAPAAction).where(
                CAPAAction.tenant_id == finding.tenant_id,
                CAPAAction.source_type == CAPASource.AUDIT_FINDING,
                CAPAAction.source_id == finding.id,
            )
        )
        siblings = list(siblings_result.scalars().all())
        blockers = [capa for capa in siblings if self._enum_value(capa.status) != CAPAStatus.CLOSED.value]
        if blockers:
            raise StateTransitionError("Cannot close finding while linked CAPA actions remain open")

    async def _assert_finding_lifecycle_chain_integrity(
        self,
        finding: AuditFinding,
        target_status: str,
        *,
        capas: list[CAPAAction] | None = None,
    ) -> None:
        """Reject a status write that would leave the finding/CAPA chain desynchronised.

        Historical alternate writers can still create rows with incomplete
        integrity metadata, so this evaluates only the lifecycle write being
        attempted. Legitimate close paths remain valid when all linked CAPAs
        are closed (or when the finding has no linked CAPA).
        """
        if capas is None:
            siblings_result = await self.db.execute(
                select(CAPAAction).where(
                    CAPAAction.tenant_id == finding.tenant_id,
                    CAPAAction.source_type == CAPASource.AUDIT_FINDING,
                    CAPAAction.source_id == finding.id,
                )
            )
            capas = list(siblings_result.scalars().all())

        chain_status = self._honest_chain_status(
            target_status,
            [{"status": self._enum_value(capa.status)} for capa in capas],
        )
        if chain_status.startswith("desynced_"):
            raise StateTransitionError(
                "Cannot update finding lifecycle while linked CAPA actions are desynchronised "
                f"({chain_status})"
            )

    async def apply_capa_closure_bridge(
        self,
        capa: CAPAAction,
        *,
        actor_user_id: int,
        tenant_id: int | None = None,
    ) -> dict[str, Any]:
        """Advance linked AuditFinding when an audit-sourced CAPA hits verification/closed.

        Idempotent: re-running with the same CAPA/finding state is a no-op.
        Does not commit; callers own the transaction. Does not notify (use
        ``notify_capa_closure_bridge`` after commit).
        """
        result: dict[str, Any] = {
            "bridged": False,
            "changed": False,
            "skipped_reason": None,
            "finding_id": None,
            "from_status": None,
            "to_status": None,
            "notify_user_id": None,
            "run_id": None,
        }

        if not self._capa_is_audit_finding_source(capa):
            result["skipped_reason"] = "not_audit_finding_source"
            return result

        target = self._target_finding_status_for_capa(capa.status)
        if target is None:
            result["skipped_reason"] = "capa_status_not_bridgeable"
            return result

        effective_tenant = tenant_id if tenant_id is not None else capa.tenant_id
        finding: AuditFinding = await self._get_entity(
            AuditFinding,
            int(capa.source_id),
            tenant_id=effective_tenant,
        )
        result["finding_id"] = finding.id
        result["run_id"] = finding.run_id

        from_status = self._enum_value(finding.status) or FindingStatus.OPEN.value
        result["from_status"] = from_status

        # Fail closed when sibling CAPAs still block terminal closure.
        siblings_result = await self.db.execute(
            select(CAPAAction).where(
                CAPAAction.tenant_id == finding.tenant_id,
                CAPAAction.source_type == CAPASource.AUDIT_FINDING,
                CAPAAction.source_id == finding.id,
            )
        )
        siblings = list(siblings_result.scalars().all())
        if target == FindingStatus.CLOSED:
            blockers = [
                s for s in siblings if s.id != capa.id and self._enum_value(s.status) != CAPAStatus.CLOSED.value
            ]
            if blockers:
                result["skipped_reason"] = "sibling_capa_not_closed"
                result["to_status"] = from_status
                return result
        elif target == FindingStatus.PENDING_VERIFICATION:
            blockers = [
                s
                for s in siblings
                if s.id != capa.id
                and self._enum_value(s.status)
                not in {
                    CAPAStatus.VERIFICATION.value,
                    CAPAStatus.CLOSED.value,
                }
            ]
            if blockers:
                result["skipped_reason"] = "sibling_capa_not_ready"
                result["to_status"] = from_status
                return result

        # Validate the state that this bridge will write. A closed finding with
        # a CAPA moving back into verification is already desynchronised and
        # must fail rather than silently preserving that state.
        await self._assert_finding_lifecycle_chain_integrity(
            finding,
            target.value,
            capas=siblings,
        )
        if (
            self._enum_value(finding.status) == FindingStatus.CLOSED.value
            and target != FindingStatus.CLOSED
        ):
            await self._assert_finding_lifecycle_chain_integrity(finding, FindingStatus.CLOSED.value, capas=siblings)

        # Never downgrade a closed finding back to pending_verification.
        if target == FindingStatus.PENDING_VERIFICATION and from_status == FindingStatus.CLOSED.value:
            result["skipped_reason"] = "finding_already_closed"
            result["to_status"] = from_status
            return result

        if from_status == target.value:
            result["bridged"] = True
            result["to_status"] = from_status
            result["skipped_reason"] = "already_synced"
            return result

        finding.status = target
        await self.db.flush()
        await invalidate_tenant_cache(finding.tenant_id, "audits")
        track_metric(
            "audit.finding.bridge_closed" if target == FindingStatus.CLOSED else "audit.finding.bridge_pending"
        )

        run: AuditRun = await self._get_entity(AuditRun, finding.run_id, tenant_id=finding.tenant_id)
        notify_user_id = run.assigned_to_id or run.created_by_id

        result.update(
            {
                "bridged": True,
                "changed": True,
                "to_status": target.value,
                "notify_user_id": notify_user_id,
            }
        )

        await record_audit_event(
            db=self.db,
            event_type="audit.finding.capa_bridge",
            entity_type="audit_finding",
            entity_id=str(finding.id),
            action="update",
            description=(
                f"Finding {finding.reference_number} status bridged "
                f"{from_status} → {target.value} via CAPA {capa.reference_number}"
            ),
            payload={
                "capa_id": capa.id,
                "capa_status": self._enum_value(capa.status),
                "from_status": from_status,
                "to_status": target.value,
            },
            user_id=actor_user_id,
        )
        return result

    async def notify_capa_closure_bridge(
        self,
        *,
        bridge_result: dict[str, Any],
        capa: CAPAAction,
        actor_user_id: int,
    ) -> None:
        """In-app notify the audit run owner after a successful bridge status change."""
        if not bridge_result.get("changed"):
            return
        notify_user_id = bridge_result.get("notify_user_id")
        if not notify_user_id:
            return

        from src.domain.models.notification import NotificationType
        from src.domain.services.notification_service import NotificationService

        to_status = bridge_result.get("to_status") or ""
        finding_id = bridge_result.get("finding_id")
        run_id = bridge_result.get("run_id")
        title = (
            "Audit finding closed via CAPA"
            if to_status == FindingStatus.CLOSED.value
            else "Audit finding pending verification via CAPA"
        )
        message = f"CAPA {capa.reference_number} moved the linked audit finding " f"to '{to_status}'."
        notif_type = (
            NotificationType.ACTION_COMPLETED
            if to_status == FindingStatus.CLOSED.value
            else NotificationType.AUDIT_FINDING
        )
        action_url = f"/audits?view=findings&findingId={finding_id}" if finding_id else "/audits?view=findings"
        if run_id:
            action_url = f"/audits/{run_id}?view=findings"

        capa_id = capa.id
        try:
            notifier = NotificationService(self.db)
            await notifier.create_status(
                user_id=int(notify_user_id),
                entity_type="audit_finding",
                entity_id=str(finding_id),
                from_status=bridge_result.get("from_status"),
                to_status=str(to_status),
                title=title,
                message=message,
                sender_id=actor_user_id,
                action_url=action_url,
                notification_type=notif_type,
            )
        except Exception:  # noqa: BLE001 — notification must not roll back closure
            import logging

            try:
                await self.db.rollback()
            except Exception:  # noqa: BLE001
                pass
            logging.getLogger(__name__).exception(
                "Failed to notify run owner for CAPA→finding bridge capa_id=%s finding_id=%s",
                capa_id,
                finding_id,
            )

    async def finding_golden_thread(
        self,
        finding_id: int,
        *,
        tenant_id: int,
    ) -> dict[str, Any]:
        """Honest finding → CAPA → risk chain status (no invented delivery events)."""
        finding: AuditFinding = await self._get_entity(
            AuditFinding,
            finding_id,
            tenant_id=tenant_id,
        )
        run: AuditRun = await self._get_entity(AuditRun, finding.run_id, tenant_id=tenant_id)

        capa_result = await self.db.execute(
            select(CAPAAction)
            .where(
                CAPAAction.tenant_id == tenant_id,
                CAPAAction.source_type == CAPASource.AUDIT_FINDING,
                CAPAAction.source_id == finding.id,
            )
            .order_by(CAPAAction.id.asc())
        )
        capas = list(capa_result.scalars().all())

        risk_ids = list(finding.risk_ids_json or [])
        junction = await self.db.execute(
            select(audit_finding_risks.c.risk_id).where(
                audit_finding_risks.c.audit_finding_id == finding.id,
            )
        )
        for rid in junction.scalars().all():
            if rid not in risk_ids:
                risk_ids.append(rid)

        risks: list[dict[str, Any]] = []
        if risk_ids:
            risk_rows = await self.db.execute(
                select(EnterpriseRisk).where(
                    EnterpriseRisk.tenant_id == tenant_id,
                    EnterpriseRisk.id.in_(risk_ids),
                )
            )
            for risk in risk_rows.scalars().all():
                risks.append(
                    {
                        "id": risk.id,
                        "reference_number": getattr(risk, "reference", None) or getattr(risk, "reference_number", None),
                        "title": risk.title,
                        "status": self._enum_value(getattr(risk, "status", None)),
                    }
                )

        finding_status = self._enum_value(finding.status) or FindingStatus.OPEN.value
        capa_payloads = [
            {
                "id": c.id,
                "reference_number": c.reference_number,
                "status": self._enum_value(c.status),
                "completed_at": c.completed_at.isoformat() if c.completed_at else None,
                "verified_at": c.verified_at.isoformat() if c.verified_at else None,
                "assigned_to_id": c.assigned_to_id,
            }
            for c in capas
        ]

        chain_status = self._honest_chain_status(finding_status, capa_payloads)

        events: list[dict[str, Any]] = [
            {
                "event": "audit_finding.created",
                "at": finding.created_at.isoformat() if finding.created_at else None,
                "actor_id": finding.created_by_id,
                "payload": {
                    "finding_id": finding.id,
                    "reference_number": finding.reference_number,
                    "run_id": finding.run_id,
                    "status": finding_status,
                },
            }
        ]
        for capa in capas:
            events.append(
                {
                    "event": "audit_finding.capa_linked",
                    "at": capa.created_at.isoformat() if capa.created_at else None,
                    "actor_id": capa.created_by_id,
                    "payload": {
                        "capa_id": capa.id,
                        "reference_number": capa.reference_number,
                        "status": self._enum_value(capa.status),
                    },
                }
            )
            if capa.completed_at:
                events.append(
                    {
                        "event": "audit_finding.capa_verification",
                        "at": capa.completed_at.isoformat(),
                        "actor_id": capa.assigned_to_id,
                        "payload": {"capa_id": capa.id, "status": CAPAStatus.VERIFICATION.value},
                    }
                )
            if capa.verified_at:
                events.append(
                    {
                        "event": "audit_finding.capa_closed",
                        "at": capa.verified_at.isoformat(),
                        "actor_id": capa.verified_by_id,
                        "payload": {"capa_id": capa.id, "status": CAPAStatus.CLOSED.value},
                    }
                )
        if finding_status in {
            FindingStatus.PENDING_VERIFICATION.value,
            FindingStatus.CLOSED.value,
        }:
            events.append(
                {
                    "event": "audit_finding.status",
                    "at": finding.updated_at.isoformat() if finding.updated_at else None,
                    "actor_id": None,
                    "payload": {"status": finding_status, "chain_status": chain_status},
                }
            )

        return {
            "finding": {
                "id": finding.id,
                "reference_number": finding.reference_number,
                "title": finding.title,
                "status": finding_status,
                "run_id": finding.run_id,
                "run_reference": run.reference_number,
            },
            "capas": capa_payloads,
            "risks": risks,
            "chain_status": chain_status,
            "events": events,
        }

    @classmethod
    def _honest_chain_status(cls, finding_status: str, capas: list[dict[str, Any]]) -> str:
        """Derive a truthful loop label — never claim closed when finding is open."""
        if not capas:
            if finding_status == FindingStatus.CLOSED.value:
                return "closed_without_capa"
            return "finding_open_no_capa"

        capa_statuses = {c.get("status") for c in capas}
        all_closed = capa_statuses == {CAPAStatus.CLOSED.value}
        any_verification = CAPAStatus.VERIFICATION.value in capa_statuses
        any_openish = bool(
            capa_statuses
            & {
                CAPAStatus.OPEN.value,
                CAPAStatus.IN_PROGRESS.value,
                CAPAStatus.OVERDUE.value,
            }
        )

        if all_closed and finding_status == FindingStatus.CLOSED.value:
            return "closed"
        if all_closed and finding_status != FindingStatus.CLOSED.value:
            return "desynced_capa_closed_finding_open"
        if finding_status == FindingStatus.CLOSED.value and not all_closed:
            return "desynced_finding_closed_capa_open"
        if (
            finding_status == FindingStatus.PENDING_VERIFICATION.value
            and (any_verification or all_closed)
            and not any_openish
        ):
            return "pending_verification"
        if any_openish or finding_status in {
            FindingStatus.OPEN.value,
            FindingStatus.IN_PROGRESS.value,
        }:
            return "open"
        return "in_progress"
