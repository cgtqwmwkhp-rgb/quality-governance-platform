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

from sqlalchemy import and_, func, select
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
from src.domain.services.audit_scoring_service import AuditScoringService
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_business_event, track_metric

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]

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
}

_TEMPLATE_EXCLUDED_UPDATE_FIELDS = frozenset(
    {"standard_ids", "is_active", "is_published", "standard_ids_json"}
)

_QUESTION_JSON_REMAPS: dict[str, str] = {
    "options": "options_json",
    "evidence_requirements": "evidence_requirements_json",
    "conditional_logic": "conditional_logic_json",
    "clause_ids": "clause_ids_json",
    "control_ids": "control_ids_json",
}

_FINDING_JSON_REMAPS: dict[str, str] = {
    "clause_ids": "clause_ids_json",
    "control_ids": "control_ids_json",
    "risk_ids": "risk_ids_json",
}

_QUESTION_CLONE_FIELDS = (
    "question_text", "question_type", "description", "help_text",
    "is_required", "allow_na", "is_active", "max_score", "weight",
    "options_json", "min_value", "max_value", "decimal_places",
    "min_length", "max_length", "evidence_requirements_json",
    "conditional_logic_json", "clause_ids_json", "control_ids_json",
    "risk_category", "risk_weight", "sort_order",
)

_SECTION_CLONE_FIELDS = (
    "title", "description", "sort_order", "weight",
    "is_repeatable", "max_repeats", "is_active",
)

_TEMPLATE_CLONE_FIELDS = (
    "description", "category", "audit_type", "frequency",
    "scoring_method", "passing_score", "allow_offline", "require_gps",
    "require_signature", "require_approval", "auto_create_findings",
    "standard_ids_json",
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
            stmt = stmt.where(model_any.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        entity = result.scalar_one_or_none()
        if entity is None:
            raise NotFoundError(f"{model.__name__} {entity_id} not found")
        return entity

    async def _paginate(
        self, query: Any, page: int, page_size: int
    ) -> PaginatedResult:
        offset = (page - 1) * page_size
        count_q = select(func.count()).select_from(query.subquery())
        total: int = (await self.db.execute(count_q)).scalar_one()
        items = (
            (await self.db.execute(query.offset(offset).limit(page_size)))
            .scalars()
            .all()
        )
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        return PaginatedResult(
            items=list(items), total=total, page=page,
            page_size=page_size, pages=pages,
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
            entity.updated_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]

    @staticmethod
    def _remap_json_fields(
        data: dict[str, Any], remaps: dict[str, str]
    ) -> dict[str, Any]:
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
        query = select(AuditTemplate).where(
            AuditTemplate.is_active == True,  # noqa: E712
            AuditTemplate.archived_at.is_(None),
            AuditTemplate.tenant_id == tenant_id,
        )
        if search:
            pattern = f"%{search}%"
            query = query.where(
                (AuditTemplate.name.ilike(pattern))
                | (AuditTemplate.description.ilike(pattern))
            )
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
            self.db, "audit_template", AuditTemplate,
        )
        self.db.add(template)
        await self.db.commit()
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
        self, tenant_id: int, *, page: int = 1, page_size: int = 20,
    ) -> PaginatedResult:
        query = (
            select(AuditTemplate)
            .where(
                AuditTemplate.archived_at.isnot(None),
                AuditTemplate.tenant_id == tenant_id,
            )
            .order_by(AuditTemplate.archived_at.desc())
        )
        return await self._paginate(query, page, page_size)

    async def purge_expired_templates(
        self, tenant_id: int, actor_user_id: int,
    ) -> tuple[int, list[str]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        result = await self.db.execute(
            select(AuditTemplate).where(
                AuditTemplate.archived_at.isnot(None),
                AuditTemplate.archived_at < cutoff,
                AuditTemplate.tenant_id == tenant_id,
            )
        )
        expired = result.scalars().all()
        purged_count = len(expired)
        purged_names = [t.name for t in expired]

        for template in expired:
            await self.db.delete(template)

        if purged_count > 0:
            await self.db.commit()
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
        self, template_id: int, tenant_id: int,
    ) -> AuditTemplate:
        result = await self.db.execute(
            select(AuditTemplate)
            .options(
                selectinload(AuditTemplate.sections).selectinload(
                    AuditSection.questions
                ),
                selectinload(AuditTemplate.questions),
            )
            .where(
                AuditTemplate.id == template_id,
                AuditTemplate.tenant_id == tenant_id,
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
            AuditTemplate, template_id, tenant_id=tenant_id,
        )

        if template.is_published:
            template.version += 1
            template.is_published = False

        # Determine trackable changes (only fields in the allow-list)
        trackable = {
            k: v for k, v in update_data.items()
            if k in TEMPLATE_UPDATE_ALLOWED_FIELDS
        }
        if "standard_ids" in update_data:
            trackable["standard_ids_json"] = update_data["standard_ids"]

        changed_fields = [
            f for f, v in trackable.items()
            if getattr(template, f, None) != v
        ]

        self._apply_dict(
            template, update_data,
            exclude=_TEMPLATE_EXCLUDED_UPDATE_FIELDS, set_updated_at=True,
        )
        if "standard_ids" in update_data:
            template.standard_ids_json = update_data["standard_ids"]

        await self.db.commit()
        await self.db.refresh(template)
        await invalidate_tenant_cache(tenant_id, "audits")

        if changed_fields:
            await record_audit_event(
                self.db,
                event_type="audit_template.updated",
                entity_type="audit_template",
                entity_id=str(template.id),
                action="update",
                description=(
                    f"Template '{template.name}' updated: "
                    f"{', '.join(changed_fields)}"
                ),
                actor_user_id=actor_user_id,
                payload={"changed_fields": changed_fields},
            )

        return template

    async def publish_template(
        self, template_id: int, *, tenant_id: int, actor_user_id: int,
    ) -> AuditTemplate:
        result = await self.db.execute(
            select(AuditTemplate)
            .options(selectinload(AuditTemplate.questions))
            .where(
                AuditTemplate.id == template_id,
                AuditTemplate.tenant_id == tenant_id,
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError(f"AuditTemplate {template_id} not found")

        question_count = len(template.questions)
        if question_count == 0:
            raise ValidationError(
                "Template must have at least one question to publish"
            )

        template.is_published = True
        await self.db.commit()
        await self.db.refresh(template)

        await record_audit_event(
            self.db,
            event_type="audit_template.published",
            entity_type="audit_template",
            entity_id=str(template.id),
            action="publish",
            description=(
                f"Template '{template.name}' published "
                f"(v{template.version}, {question_count} questions)"
            ),
            actor_user_id=actor_user_id,
        )
        return template

    async def clone_template(
        self, template_id: int, *, user_id: int, tenant_id: int,
    ) -> AuditTemplate:
        result = await self.db.execute(
            select(AuditTemplate)
            .options(
                selectinload(AuditTemplate.sections).selectinload(
                    AuditSection.questions
                ),
                selectinload(AuditTemplate.questions),
            )
            .where(
                AuditTemplate.id == template_id,
                AuditTemplate.tenant_id == tenant_id,
            )
        )
        original = result.scalar_one_or_none()
        if not original:
            raise NotFoundError(f"AuditTemplate {template_id} not found")

        ref = await ReferenceNumberService.generate(
            self.db, "audit_template", AuditTemplate,
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
                template_id=cloned.id, **sec_kwargs,
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
                        template_id=cloned.id, section_id=None, **q_kwargs,
                    )
                )

        await self.db.commit()
        await self.db.refresh(cloned)
        return cloned

    async def archive_template(
        self, template_id: int, *, tenant_id: int, actor_user_id: int,
    ) -> AuditTemplate:
        result = await self.db.execute(
            select(AuditTemplate).where(
                AuditTemplate.id == template_id,
                AuditTemplate.archived_at.is_(None),
                AuditTemplate.tenant_id == tenant_id,
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError(f"AuditTemplate {template_id} not found")

        template.archived_at = datetime.now(timezone.utc)
        template.archived_by_id = actor_user_id
        template.is_active = False
        await self.db.commit()
        await invalidate_tenant_cache(tenant_id, "audits")

        await record_audit_event(
            self.db,
            event_type="audit_template.archived",
            entity_type="audit_template",
            entity_id=str(template_id),
            action="archive",
            description=(
                f"Template '{template.name}' archived "
                "(recoverable for 30 days)"
            ),
            actor_user_id=actor_user_id,
        )
        return template

    async def restore_template(
        self, template_id: int, *, tenant_id: int, actor_user_id: int,
    ) -> AuditTemplate:
        result = await self.db.execute(
            select(AuditTemplate).where(
                AuditTemplate.id == template_id,
                AuditTemplate.archived_at.isnot(None),
                AuditTemplate.tenant_id == tenant_id,
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError(f"AuditTemplate {template_id} not found")

        template.archived_at = None
        template.archived_by_id = None
        template.is_active = True
        await self.db.commit()
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
        self, template_id: int, *, tenant_id: int, actor_user_id: int,
    ) -> None:
        result = await self.db.execute(
            select(AuditTemplate).where(
                AuditTemplate.id == template_id,
                AuditTemplate.archived_at.isnot(None),
                AuditTemplate.tenant_id == tenant_id,
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError(f"AuditTemplate {template_id} not found")

        template_name = template.name
        await self.db.delete(template)
        await self.db.commit()
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
        self, template_id: int, data: dict[str, Any], *, tenant_id: int,
    ) -> AuditSection:
        await self._get_entity(AuditTemplate, template_id, tenant_id=tenant_id)

        section = AuditSection(template_id=template_id, **data)
        self.db.add(section)
        await self.db.commit()

        refreshed = await self.db.execute(
            select(AuditSection)
            .options(selectinload(AuditSection.questions))
            .where(AuditSection.id == section.id)
        )
        return refreshed.scalar_one()

    async def update_section(
        self, section_id: int, update_data: dict[str, Any], *, tenant_id: int,
    ) -> AuditSection:
        result = await self.db.execute(
            select(AuditSection)
            .options(selectinload(AuditSection.questions))
            .where(AuditSection.id == section_id)
        )
        section = result.scalar_one_or_none()
        if not section:
            raise NotFoundError(f"AuditSection {section_id} not found")

        await self._get_entity(
            AuditTemplate, section.template_id, tenant_id=tenant_id,
        )

        self._apply_dict(section, update_data)
        await self.db.commit()

        refreshed = await self.db.execute(
            select(AuditSection)
            .options(selectinload(AuditSection.questions))
            .where(AuditSection.id == section.id)
        )
        return refreshed.scalar_one()

    async def delete_section(
        self, section_id: int, *, tenant_id: int,
    ) -> None:
        section: AuditSection = await self._get_entity(AuditSection, section_id)
        await self._get_entity(
            AuditTemplate, section.template_id, tenant_id=tenant_id,
        )
        section.is_active = False
        await self.db.commit()

    # ==================================================================
    # Question methods
    # ==================================================================

    async def create_question(
        self, template_id: int, data: dict[str, Any], *, tenant_id: int,
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
                raise ValidationError(
                    "Section does not belong to this template"
                )

        question_dict = self._remap_json_fields(data, _QUESTION_JSON_REMAPS)

        question = AuditQuestion(template_id=template_id, **question_dict)
        self.db.add(question)
        await self.db.commit()
        await self.db.refresh(question)
        return question

    async def update_question(
        self, question_id: int, update_data: dict[str, Any], *, tenant_id: int,
    ) -> AuditQuestion:
        question: AuditQuestion = await self._get_entity(
            AuditQuestion, question_id,
        )
        await self._get_entity(
            AuditTemplate, question.template_id, tenant_id=tenant_id,
        )

        handled = self._apply_json_field_updates(
            question, update_data, _QUESTION_JSON_REMAPS,
        )
        self._apply_dict(question, update_data, exclude=handled)

        await self.db.commit()
        await self.db.refresh(question)
        return question

    async def delete_question(
        self, question_id: int, *, tenant_id: int,
    ) -> None:
        question: AuditQuestion = await self._get_entity(
            AuditQuestion, question_id,
        )
        await self._get_entity(
            AuditTemplate, question.template_id, tenant_id=tenant_id,
        )
        question.is_active = False
        await self.db.commit()

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
            .where(AuditRun.tenant_id == tenant_id)
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
        self, data: dict[str, Any], *, user_id: int, tenant_id: int,
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
            self.db, "audit_run", AuditRun,
        )

        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        await invalidate_tenant_cache(tenant_id, "audits")

        if _span:
            _span.end()
        return run

    async def get_run_detail(
        self, run_id: int, tenant_id: int,
    ) -> RunDetail:
        result = await self.db.execute(
            select(AuditRun)
            .options(
                selectinload(AuditRun.responses),
                selectinload(AuditRun.findings),
                selectinload(AuditRun.template),
            )
            .where(AuditRun.id == run_id, AuditRun.tenant_id == tenant_id)
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
        self, run_id: int, update_data: dict[str, Any], *, tenant_id: int,
    ) -> AuditRun:
        run: AuditRun = await self._get_entity(
            AuditRun, run_id, tenant_id=tenant_id,
        )

        if "status" in update_data:
            new_status = update_data["status"]
            if new_status == AuditStatus.COMPLETED.value:
                raise ValidationError(
                    "Cannot set status to completed directly; "
                    "use the complete endpoint"
                )
            try:
                validated = AuditStatus(new_status)
            except ValueError:
                raise ValidationError(f"Invalid audit status: {new_status}")
            if validated == AuditStatus.IN_PROGRESS and run.started_at is None:
                run.started_at = datetime.now(timezone.utc)
            run.status = validated

        self._apply_dict(run, update_data, exclude={"status"})

        await self.db.commit()
        await self.db.refresh(run)
        await invalidate_tenant_cache(tenant_id, "audits")
        return run

    async def start_run(
        self, run_id: int, *, tenant_id: int,
    ) -> AuditRun:
        run: AuditRun = await self._get_entity(
            AuditRun, run_id, tenant_id=tenant_id,
        )
        if run.status != AuditStatus.SCHEDULED:
            raise ValidationError("Only scheduled runs can be started")

        run.status = AuditStatus.IN_PROGRESS
        run.started_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def complete_run(
        self, run_id: int, *, tenant_id: int,
    ) -> AuditRun:
        result = await self.db.execute(
            select(AuditRun)
            .options(selectinload(AuditRun.responses))
            .where(AuditRun.id == run_id, AuditRun.tenant_id == tenant_id)
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

        template_result = await self.db.execute(
            select(AuditTemplate).where(AuditTemplate.id == run.template_id)
        )
        template = template_result.scalar_one_or_none()
        if template and template.passing_score is not None:
            run.passed = run.score_percentage >= template.passing_score

        run.status = AuditStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(run)
        track_metric("audits.completed")
        return run

    # ==================================================================
    # Response methods
    # ==================================================================

    async def create_audit_response(
        self, run_id: int, data: dict[str, Any], *, tenant_id: int,
    ) -> AuditResponse:
        run: AuditRun = await self._get_entity(
            AuditRun, run_id, tenant_id=tenant_id,
        )

        if run.status not in (AuditStatus.SCHEDULED, AuditStatus.IN_PROGRESS):
            raise ValidationError(
                "Cannot add responses to a completed or cancelled run"
            )

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
            raise ValidationError(
                "Response already exists for this question in this run"
            )

        response = AuditResponse(run_id=run_id, **data)
        self.db.add(response)
        await self.db.commit()
        await self.db.refresh(response)
        return response

    async def update_audit_response(
        self, response_id: int, update_data: dict[str, Any], *, tenant_id: int,
    ) -> AuditResponse:
        result = await self.db.execute(
            select(AuditResponse)
            .options(selectinload(AuditResponse.run))
            .where(AuditResponse.id == response_id)
        )
        response = result.scalar_one_or_none()

        if response:
            await self._get_entity(
                AuditRun, response.run_id, tenant_id=tenant_id,
            )

        if not response:
            raise NotFoundError(f"AuditResponse {response_id} not found")

        if response.run.status == AuditStatus.COMPLETED:
            raise ValidationError(
                "Cannot update responses on a completed run"
            )

        self._apply_dict(response, update_data)
        await self.db.commit()
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
        await self._get_entity(AuditRun, run_id, tenant_id=tenant_id)

        finding_dict = self._remap_json_fields(data, _FINDING_JSON_REMAPS)

        finding = AuditFinding(
            run_id=run_id,
            status=FindingStatus.OPEN,
            created_by_id=user_id,
            tenant_id=tenant_id,
            **finding_dict,
        )

        finding.reference_number = await ReferenceNumberService.generate(
            self.db, "audit_finding", AuditFinding,
        )

        self.db.add(finding)
        await self.db.commit()
        await self.db.refresh(finding)
        await invalidate_tenant_cache(tenant_id, "audits")
        track_metric("audits.findings")
        return finding

    async def update_finding(
        self, finding_id: int, update_data: dict[str, Any], *, tenant_id: int,
    ) -> AuditFinding:
        finding: AuditFinding = await self._get_entity(
            AuditFinding, finding_id, tenant_id=tenant_id,
        )

        handled = self._apply_json_field_updates(
            finding, update_data, _FINDING_JSON_REMAPS,
        )
        self._apply_dict(finding, update_data, exclude=handled)

        await self.db.commit()
        await self.db.refresh(finding)
        await invalidate_tenant_cache(tenant_id, "audits")
        return finding
