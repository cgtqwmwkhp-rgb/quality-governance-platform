"""Resolve the internal audit template used for external audit imports."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.models.audit import AuditTemplate

_INTAKE_TEMPLATE_NAME = "external audit intake"
_INTAKE_TEMPLATE_TAG = "external_audit_intake"


@dataclass(frozen=True)
class IntakeTemplateResolution:
    """Represents a deterministic intake template selection."""

    template: AuditTemplate
    scope: str
    rule: str


class ExternalAuditIntakeTemplateResolver:
    """Find the published intake template used by external imports."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def resolve(
        self,
        *,
        tenant_id: int | None,
        external_audit_type: str,
    ) -> IntakeTemplateResolution:
        tenant_order = case((AuditTemplate.tenant_id == tenant_id, 0), else_=1)
        result = await self.db.execute(
            select(AuditTemplate)
            .where(
                AuditTemplate.is_active == True,  # noqa: E712
                AuditTemplate.is_published == True,  # noqa: E712
                or_(
                    AuditTemplate.tenant_id == tenant_id,
                    AuditTemplate.tenant_id.is_(None),
                ),
            )
            .order_by(tenant_order, AuditTemplate.version.desc(), AuditTemplate.id.asc())
        )
        candidates = list(result.scalars().all())
        if not candidates:
            raise NotFoundError("No published audit templates are available for this tenant")

        rules = (
            (
                "external_type_tag",
                lambda template: self._has_tag(
                    template,
                    f"{_INTAKE_TEMPLATE_TAG}:{external_audit_type}",
                ),
            ),
            ("generic_intake_tag", lambda template: self._has_tag(template, _INTAKE_TEMPLATE_TAG)),
            ("canonical_name", lambda template: self._normalize(template.name) == _INTAKE_TEMPLATE_NAME),
        )

        for rule_name, matcher in rules:
            matches = [template for template in candidates if matcher(template)]
            if matches:
                return self._pick_unique_match(
                    matches=matches,
                    tenant_id=tenant_id,
                    rule=rule_name,
                    external_audit_type=external_audit_type,
                )

        raise NotFoundError(f"No published external audit intake template is configured for '{external_audit_type}'")

    def _pick_unique_match(
        self,
        *,
        matches: list[AuditTemplate],
        tenant_id: int | None,
        rule: str,
        external_audit_type: str,
    ) -> IntakeTemplateResolution:
        tenant_matches = [template for template in matches if tenant_id is not None and template.tenant_id == tenant_id]
        if tenant_matches:
            preferred_matches = tenant_matches
            scope = "tenant"
        else:
            preferred_matches = [template for template in matches if template.tenant_id is None]
            scope = "global"

        if len(preferred_matches) != 1:
            raise ConflictError(
                "Multiple published external audit intake templates match "
                f"'{external_audit_type}' for {scope} scope; keep exactly one active published intake template"
            )

        return IntakeTemplateResolution(template=preferred_matches[0], scope=scope, rule=rule)

    def _has_tag(self, template: AuditTemplate, tag: str) -> bool:
        tags = template.tags_json or []
        return any(self._normalize(candidate) == tag for candidate in tags if isinstance(candidate, str))

    def _normalize(self, value: str | None) -> str:
        return (value or "").strip().lower()
