"""Helpers for investigation closure gates (open CAPA / actions)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import String

from src.domain.exceptions import TenantAccessError
from src.domain.models.capa import CAPAAction, CAPASource, CAPAStatus
from src.domain.models.investigation import InvestigationAction, InvestigationActionStatus
from src.domain.models.rca_tools import CAPAItem
from src.domain.services.case_closure import resolve_case_tenant_id

logger = logging.getLogger(__name__)

CLOSURE_REASON_OPEN_ACTIONS_REMAIN = "OPEN_ACTIONS_REMAIN"
SUMMARY_SECTION_KEY = "summary"
SUMMARY_SECTION_LABEL = "Summary"
_INVESTIGATION_ACTION_STORAGE_KIND = "investigation_action"

_INVESTIGATION_ACTION_DONE_STATUSES: tuple[InvestigationActionStatus, ...] = (
    InvestigationActionStatus.COMPLETED,
    InvestigationActionStatus.CANCELLED,
)

_CAPA_DONE_STATUSES: tuple[CAPAStatus, ...] = (CAPAStatus.CLOSED,)
_CAPA_ITEM_DONE_STATUSES = frozenset({"completed", "verified", "closed", "cancelled"})


@dataclass(frozen=True)
class OpenWorkItem:
    """A CAPA/action item that blocks investigation closure."""

    kind: str
    id: int
    reference_number: str
    title: str
    status: str
    action_key: str


def _status_value(status: Any) -> str:
    return status.value if hasattr(status, "value") else str(status)


def resolve_investigation_closure_scope(investigation: Any, *, caller_tenant_id: Optional[int]) -> int:
    """Tenant to scope an investigation's closure probes to, taken from the run.

    #1382 established this for the four case registers: the scope is a property
    of the record, never of the caller. Probing the caller's tenant for a run
    that lives in another one finds none of that run's actions and reports a
    clean close over work nobody can see — the worst outcome an evidence system
    can produce. ``investigation_runs.tenant_id`` is NOT NULL, so a run without
    one is a corrupt row and is refused rather than guessed at.

    Where the two tenants differ we refuse instead of probing either. The four
    registers let a superuser edit across tenants and rely on their update route
    to say who may; the investigation update route makes no such check at all,
    so honouring the record's scope here without this guard would turn today's
    (accidental) refusal into a real cross-tenant close. Refusing keeps the probe
    honest without granting anything new.
    """
    tenant_id = resolve_case_tenant_id(investigation)
    if caller_tenant_id is None or int(caller_tenant_id) != tenant_id:
        logger.warning(
            "investigation_closure_scope_cross_tenant",
            extra={
                "investigation_id": getattr(investigation, "id", None),
                "reference_number": getattr(investigation, "reference_number", None),
                "record_tenant_id": tenant_id,
                "caller_tenant_id": caller_tenant_id,
            },
        )
        raise TenantAccessError(
            "Closure readiness for this investigation can only be assessed from the tenant that owns it.",
            details={"investigation_id": getattr(investigation, "id", None)},
        )
    return tenant_id


async def fetch_open_work_for_investigation(
    db: AsyncSession,
    *,
    investigation_id: int,
    tenant_id: int,
) -> list[OpenWorkItem]:
    """Return investigation-scoped actions/CAPAs that are not completed or cancelled.

    Each source query is isolated so a single schema/enum drift issue cannot
    hard-500 the close path. If every source probe fails, raise so callers can
    surface OPEN_ACTIONS_REMAIN instead of falsely reporting can_close.
    """
    items: list[OpenWorkItem] = []
    probe_failures = 0

    try:
        inv_query = (
            select(InvestigationAction)
            .where(
                InvestigationAction.investigation_id == investigation_id,
                InvestigationAction.tenant_id == tenant_id,
                InvestigationAction.status.notin_(_INVESTIGATION_ACTION_DONE_STATUSES),
            )
            .order_by(InvestigationAction.created_at.asc(), InvestigationAction.id.asc())
        )
        inv_result = await db.execute(inv_query)
        for inv_row in inv_result.scalars().all():
            items.append(
                OpenWorkItem(
                    kind="investigation_action",
                    id=inv_row.id,
                    reference_number=inv_row.reference_number or f"INV-ACT-{inv_row.id}",
                    title=inv_row.title,
                    status=_status_value(inv_row.status),
                    action_key=f"{_INVESTIGATION_ACTION_STORAGE_KIND}:{inv_row.id}",
                )
            )
    except Exception:  # noqa: BLE001 — never hard-500 close / closure-validation
        probe_failures += 1
        logger.exception(
            "fetch_open_work_investigation_actions_failed",
            extra={"investigation_id": investigation_id, "tenant_id": tenant_id},
        )

    try:
        # Compare as text so missing PG enum labels cannot abort the close gate.
        capa_query = (
            select(CAPAAction)
            .where(
                CAPAAction.tenant_id == tenant_id,
                cast(CAPAAction.source_type, String) == CAPASource.INVESTIGATION.value,
                CAPAAction.source_id == investigation_id,
                CAPAAction.status.notin_(_CAPA_DONE_STATUSES),
            )
            .order_by(CAPAAction.id.asc())
        )
        capa_result = await db.execute(capa_query)
        for capa_row in capa_result.scalars().all():
            capa_id = int(capa_row.id)
            items.append(
                OpenWorkItem(
                    kind="capa_action",
                    id=capa_id,
                    reference_number=str(capa_row.reference_number or f"CAPA-{capa_id}"),
                    title=str(capa_row.title or ""),
                    status=_status_value(capa_row.status),
                    action_key=f"capa:{capa_id}",
                )
            )
    except Exception:  # noqa: BLE001
        probe_failures += 1
        logger.exception(
            "fetch_open_work_capa_actions_failed",
            extra={"investigation_id": investigation_id, "tenant_id": tenant_id},
        )

    try:
        item_query = (
            select(CAPAItem)
            .where(
                CAPAItem.investigation_id == investigation_id,
                CAPAItem.tenant_id == tenant_id,
            )
            .order_by(CAPAItem.id.asc())
        )
        item_result = await db.execute(item_query)
        for capa_item in item_result.scalars().all():
            status = str(capa_item.status or "open").strip().lower()
            if status in _CAPA_ITEM_DONE_STATUSES:
                continue
            item_id = int(capa_item.id)
            items.append(
                OpenWorkItem(
                    kind="capa_item",
                    id=item_id,
                    reference_number=f"CAPA-ITEM-{item_id}",
                    title=str(capa_item.title or f"CAPA item {item_id}"),
                    status=status,
                    action_key=f"capa_item:{item_id}",
                )
            )
    except Exception:  # noqa: BLE001
        probe_failures += 1
        logger.exception(
            "fetch_open_work_capa_items_failed",
            extra={"investigation_id": investigation_id, "tenant_id": tenant_id},
        )

    if probe_failures == 3:
        raise RuntimeError(f"All open-work probes failed for investigation_id={investigation_id}")

    return items


def open_work_to_payload(items: list[OpenWorkItem]) -> list[dict[str, Any]]:
    """Serialize open-work items for API responses."""
    return [
        {
            "kind": item.kind,
            "id": item.id,
            "reference_number": item.reference_number,
            "title": item.title,
            "status": item.status,
            "action_key": item.action_key,
            "unblock_hint": "Complete or cancel this action on the Actions tab.",
        }
        for item in items
    ]


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def collect_summary_readiness_blockers(investigation: Any) -> tuple[list[str], list]:
    """Return reason codes + missing_items for summary-tab narrative gates."""
    from src.domain.models.investigation import InvestigationStatus
    from src.domain.services.investigation_service import ClosureMissingItem, ClosureReasonCode

    reasons: list[str] = []
    missing_items: list = []

    status_val = investigation.status.value if hasattr(investigation.status, "value") else str(investigation.status)
    if status_val == InvestigationStatus.DRAFT.value or getattr(investigation, "started_at", None) is None:
        reasons.append(ClosureReasonCode.INVESTIGATION_NOT_STARTED)
        missing_items.append(
            ClosureMissingItem(
                code=ClosureReasonCode.INVESTIGATION_NOT_STARTED,
                section_key=SUMMARY_SECTION_KEY,
                section_label=SUMMARY_SECTION_LABEL,
                field_key="started_at",
                field_label="Investigation start",
            )
        )

    has_lead = bool(getattr(investigation, "assigned_to_user_id", None))
    raw_data = investigation.data if isinstance(getattr(investigation, "data", None), dict) else {}
    if not has_lead and not _non_empty_text(raw_data.get("lead_investigator")):
        reasons.append(ClosureReasonCode.LEAD_INVESTIGATOR_NOT_ASSIGNED)
        missing_items.append(
            ClosureMissingItem(
                code=ClosureReasonCode.LEAD_INVESTIGATOR_NOT_ASSIGNED,
                section_key=SUMMARY_SECTION_KEY,
                section_label=SUMMARY_SECTION_LABEL,
                field_key="lead_investigator",
                field_label="Lead investigator",
            )
        )

    if not _non_empty_text(raw_data.get("findings")):
        reasons.append(ClosureReasonCode.MISSING_FINDINGS)
        missing_items.append(
            ClosureMissingItem(
                code=ClosureReasonCode.MISSING_FINDINGS,
                section_key=SUMMARY_SECTION_KEY,
                section_label=SUMMARY_SECTION_LABEL,
                field_key="findings",
                field_label="Findings",
            )
        )

    if not _non_empty_text(raw_data.get("conclusion")):
        reasons.append(ClosureReasonCode.MISSING_CONCLUSION)
        missing_items.append(
            ClosureMissingItem(
                code=ClosureReasonCode.MISSING_CONCLUSION,
                section_key=SUMMARY_SECTION_KEY,
                section_label=SUMMARY_SECTION_LABEL,
                field_key="conclusion",
                field_label="Conclusion",
            )
        )

    return reasons, missing_items


def user_can_supervisor_override_closure(user: Any, investigation: Any) -> bool:
    """Supervisor/senior investigator may override open-work gates with a reason."""
    if getattr(user, "is_superuser", False):
        return True
    has_permission = getattr(user, "has_permission", None)
    if callable(has_permission) and has_permission("investigations:view_all"):
        return True
    user_id = getattr(user, "id", None)
    return user_id in {
        getattr(investigation, "reviewer_user_id", None),
        getattr(investigation, "approved_by_id", None),
    }


async def assert_investigation_can_close(
    db: AsyncSession,
    *,
    investigation_id: int,
    tenant_id: int,
) -> list[OpenWorkItem]:
    """Raise StateTransitionError when open work remains; else return empty list."""
    from src.domain.exceptions import StateTransitionError

    open_work = await fetch_open_work_for_investigation(
        db,
        investigation_id=investigation_id,
        tenant_id=tenant_id,
    )
    if not open_work:
        return open_work

    raise StateTransitionError(
        "Cannot close investigation while open CAPA/actions remain",
        code=CLOSURE_REASON_OPEN_ACTIONS_REMAIN,
        details={
            "open_work": open_work_to_payload(open_work),
            "open_work_count": len(open_work),
        },
    )
