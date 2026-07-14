"""Helpers for investigation closure gates (open CAPA / actions)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.investigation import InvestigationAction, InvestigationActionStatus

CLOSURE_REASON_OPEN_ACTIONS_REMAIN = "OPEN_ACTIONS_REMAIN"
_INVESTIGATION_ACTION_STORAGE_KIND = "investigation_action"

_INVESTIGATION_ACTION_DONE_STATUSES: tuple[InvestigationActionStatus, ...] = (
    InvestigationActionStatus.COMPLETED,
    InvestigationActionStatus.CANCELLED,
)


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
    """Return investigation-scoped actions that are not completed or cancelled."""
    query = (
        select(InvestigationAction)
        .where(
            InvestigationAction.investigation_id == investigation_id,
            InvestigationAction.tenant_id == tenant_id,
            InvestigationAction.status.notin_(_INVESTIGATION_ACTION_DONE_STATUSES),
        )
        .order_by(InvestigationAction.created_at.asc(), InvestigationAction.id.asc())
    )
    result = await db.execute(query)
    rows = result.scalars().all()

    items: list[OpenWorkItem] = []
    for row in rows:
        status = _status_value(row.status)
        items.append(
            OpenWorkItem(
                kind="investigation_action",
                id=row.id,
                reference_number=row.reference_number or f"INV-ACT-{row.id}",
                title=row.title,
                status=status,
                action_key=f"{_INVESTIGATION_ACTION_STORAGE_KIND}:{row.id}",
            )
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
