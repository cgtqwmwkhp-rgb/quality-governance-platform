"""Helpers for investigation closure gates (open CAPA / actions)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import String

from src.domain.models.capa import CAPAAction, CAPASource, CAPAStatus
from src.domain.models.investigation import InvestigationAction, InvestigationActionStatus
from src.domain.models.rca_tools import CAPAItem

logger = logging.getLogger(__name__)

CLOSURE_REASON_OPEN_ACTIONS_REMAIN = "OPEN_ACTIONS_REMAIN"
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
        raise RuntimeError(
            f"All open-work probes failed for investigation_id={investigation_id}"
        )

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
