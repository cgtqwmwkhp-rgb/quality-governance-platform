"""CB-UI-4: coverage shortfall dues the location occurrence.

CB-PR5 painted ``coverage_gap`` on the location duty and left ``next_due_date``
alone. Live status is date-only (ADR-0020), so a gap that never moves the date
never becomes due. This module is the missing write: when Atlas says a matched
quota is short, pull that location requirement's ``next_due_date`` to today
(or keep an earlier overdue date).

It never:

* runs inside a schedule GET — overlay stays a second fact on the read path
* dues an unknown quota (no import, or ``match_department`` unset)
* creates a person-scoped ``ComplianceRequirement`` or a ``ComplianceRecord``
* auto-completes when cover recovers — the operator closes the occurrence
* writes PAMS, Citation, or Users
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import select

from src.domain.models.compliance_schedule import ComplianceRequirement, ComplianceRequirementTemplate
from src.domain.services.audit_service import record_audit_event
from src.domain.services.competence_coverage_service import (
    assemble_coverage,
    list_quotas_async,
    load_atlas_snapshot_async,
)


def _today() -> date:
    return datetime.now(timezone.utc).date()


@dataclass(frozen=True)
class CoverageDuePull:
    requirement_id: int
    quota_id: int
    previous_due: date
    next_due: date


async def apply_coverage_shortfall_dues_async(
    db: Any,
    *,
    tenant_id: int,
    today: Optional[date] = None,
    actor_user_id: Optional[int] = None,
) -> list[CoverageDuePull]:
    """Pull ``next_due_date`` to ``today`` on location duties whose quota is short.

    Flush-only. The caller owns the commit. A later import that restores cover
    does not roll the date forward — that is complete-occurrence, not this path.
    """
    as_of = today or _today()
    quotas = await list_quotas_async(db, tenant_id=tenant_id)
    if not quotas:
        return []
    snapshot = await load_atlas_snapshot_async(db, tenant_id)
    gap_states = [
        state
        for state in assemble_coverage(quotas=quotas, snapshot=snapshot, today=as_of)
        if state.gap and not state.unknown
    ]
    if not gap_states:
        return []

    location_ids = {state.location_id for state in gap_states}
    requirements = [
        row
        for row in (
            await db.scalars(
                select(ComplianceRequirement).where(
                    ComplianceRequirement.tenant_id == tenant_id,
                    ComplianceRequirement.location_id.in_(list(location_ids)),
                )
            )
        ).all()
        if getattr(row, "is_active", True)
    ]
    missing_template_ids = [
        row.template_id
        for row in requirements
        if getattr(row, "template", None) is None and getattr(row, "template_id", None)
    ]
    templates_by_id: dict[int, ComplianceRequirementTemplate] = {}
    if missing_template_ids:
        loaded = (
            await db.scalars(
                select(ComplianceRequirementTemplate).where(
                    ComplianceRequirementTemplate.id.in_(list(missing_template_ids)),
                )
            )
        ).all()
        templates_by_id = {row.id: row for row in loaded}

    wanted = {(state.location_id, state.template_key): state for state in gap_states}
    pulled: list[CoverageDuePull] = []
    for requirement in requirements:
        template = getattr(requirement, "template", None)
        if template is None:
            template = templates_by_id.get(getattr(requirement, "template_id", None))
        template_key = getattr(template, "template_key", None) if template is not None else None
        if not template_key:
            continue
        state = wanted.get((requirement.location_id, template_key))
        if state is None:
            continue
        previous = requirement.next_due_date
        if previous <= as_of:
            continue
        requirement.next_due_date = as_of
        await record_audit_event(
            db=db,
            event_type="compliance_schedule.coverage_shortfall_due",
            entity_type="compliance_requirement",
            entity_id=str(requirement.id),
            entity_name=getattr(requirement, "reference_number", None),
            action="update",
            description=(
                f"Coverage shortfall due-pulled requirement {requirement.id} "
                f"from {previous.isoformat()} to {as_of.isoformat()}"
            ),
            payload={
                "quota_id": state.quota_id,
                "role_key": state.role_key,
                "previous_due": previous.isoformat(),
                "next_due_date": as_of.isoformat(),
                "current_m": state.current_m,
                "required_n": state.required_n,
            },
            user_id=actor_user_id,
            actor_user_id=actor_user_id,
            changed_fields=["next_due_date"],
            tenant_id=tenant_id,
        )
        pulled.append(
            CoverageDuePull(
                requirement_id=requirement.id,
                quota_id=state.quota_id,
                previous_due=previous,
                next_due=as_of,
            )
        )
    if pulled:
        await db.flush()
    return pulled


__all__ = ["CoverageDuePull", "apply_coverage_shortfall_dues_async"]
