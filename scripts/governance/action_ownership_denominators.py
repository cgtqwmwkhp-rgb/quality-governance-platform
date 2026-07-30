"""Canonical ownership denominators for the six stores behind GET /actions/.

Board item ``w3-owner-count`` (PX-168 follow-up) recorded two measurements that
shared a total of 21 but disagreed on how many were owned (8/21 vs 0/21). The
stores do not share one ownership column:

* CAPA stores persist the assignee as ``assigned_to_id``.
* Operational action stores persist the assignee as ``owner_id``.

``GET /api/v1/actions/`` maps both onto the response field ``owner_id``. A raw
SQL count that only looks for ``owner_id IS NOT NULL`` therefore under-counts
(or reports zero for) every CAPA row that is actually assigned, and the reverse
mistake under-counts operational rows.

This module is the single label table for that distinction. The reconcile script
and the unit/integration specs import it so the numbers they print cannot drift
from the names they claim to measure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OwnershipColumn = Literal["owner_id", "assigned_to_id"]


@dataclass(frozen=True)
class ActionOwnershipStore:
    """One physical table that contributes rows to the unified Actions register."""

    table: str
    ownership_column: OwnershipColumn
    unified_response_field: str = "owner_id"
    storage_kind: str = ""
    notes: str = ""


# Order matches the six stores read by ``list_actions`` / ``/actions/summary``.
ACTION_OWNERSHIP_STORES: tuple[ActionOwnershipStore, ...] = (
    ActionOwnershipStore(
        table="incident_actions",
        ownership_column="owner_id",
        storage_kind="incident_action",
        notes="Operational store; ORM attribute is owner_id.",
    ),
    ActionOwnershipStore(
        table="rta_actions",
        ownership_column="owner_id",
        storage_kind="rta_action",
        notes="Operational store; ORM attribute is owner_id.",
    ),
    ActionOwnershipStore(
        table="complaint_actions",
        ownership_column="owner_id",
        storage_kind="complaint_action",
        notes="Operational store; ORM attribute is owner_id.",
    ),
    ActionOwnershipStore(
        table="investigation_actions",
        ownership_column="owner_id",
        storage_kind="investigation_action",
        notes="Operational store; ORM attribute is owner_id.",
    ),
    ActionOwnershipStore(
        table="capa_actions",
        ownership_column="assigned_to_id",
        storage_kind="capa",
        notes="CAPA store; no owner_id column. Unified API maps assigned_to_id → owner_id.",
    ),
    ActionOwnershipStore(
        table="capa_items",
        ownership_column="assigned_to_id",
        storage_kind="capa_item",
        notes="RCA CAPA item store; no owner_id column. Unified API maps assigned_to_id → owner_id.",
    ),
)


def ownership_column_for(table: str) -> OwnershipColumn:
    """Return the physical ownership column for ``table``, or raise KeyError."""
    for store in ACTION_OWNERSHIP_STORES:
        if store.table == table:
            return store.ownership_column
    raise KeyError(f"unknown action store table: {table!r}")


def naive_wrong_column(table: str) -> OwnershipColumn | None:
    """Column a mislabeled 'owner_id everywhere' query would probe.

    Returns ``None`` when the naive name and the real name already agree
    (operational stores), so a wrong-column probe is not meaningful.
    """
    real = ownership_column_for(table)
    if real == "owner_id":
        return None
    return "owner_id"


def format_store_row(store: ActionOwnershipStore) -> str:
    """One human-readable line for script / docs output."""
    return (
        f"{store.table:24} physical={store.ownership_column:16} "
        f"unified_response={store.unified_response_field}  ({store.notes})"
    )
