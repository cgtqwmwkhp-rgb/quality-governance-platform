"""UVDB catalogue rows keyed by ``audit_reference``, not by a foreign key.

``uvdb_audit`` is the UVDB Audit Status register. Promote sync writes
``UVDBAudit.audit_reference = AuditRun.reference_number``, so a twin re-import
mints a catalogue twin alongside the audit-run twin. There is **no** FK from
``uvdb_audit`` to ``audit_runs``, so the reflected FK closure in ``_closure``
never sees these rows — which is how PROD purge of ``AUD-2026-0043`` left UVDB
Audit Status still showing the twin (FR-DEDUP-01d).

Children ``uvdb_audit_response`` and ``uvdb_kpi_record`` cascade from
``uvdb_audit.id`` on PostgreSQL. Deletes here are still explicit and
children-first so SQLite fixtures (foreign keys off by default) and dialects
that do not honour ``ON DELETE CASCADE`` behave the same as production intent.

Disposition is always **purge** of catalogue rows whose ``audit_reference``
equals a purged run reference. Remap is not used: ``audit_reference`` is UNIQUE
and the survivor already carries (or will sync) its own catalogue row under its
own reference — rewriting a twin's reference onto the survivor would collide or
falsify which run the score card belongs to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import sqlalchemy as sa

__all__ = [
    "UVDB_AUDIT_TABLE",
    "UVDB_CHILD_TABLES",
    "UvdbCataloguePlan",
    "plan_uvdb_catalogue",
    "apply_uvdb_catalogue",
]

UVDB_AUDIT_TABLE = "uvdb_audit"
UVDB_CHILD_TABLES: tuple[str, ...] = ("uvdb_audit_response", "uvdb_kpi_record")

#: Why these rows are deleted with the audit-run purge.
UVDB_PURGE_RATIONALE = (
    "UVDB Audit Status catalogue row minted by promote sync with "
    "audit_reference equal to the purged audit_runs.reference_number. There is "
    "no foreign key to audit_runs, so the FK closure cannot see it. Leaving it "
    "shows a twin on /uvdb after the register purge. Children "
    "uvdb_audit_response and uvdb_kpi_record are deleted with it."
)


@dataclass
class UvdbCataloguePlan:
    """Catalogue rows (and counted children) to delete with a named audit purge."""

    audits: list[dict[str, Any]] = field(default_factory=list)
    child_row_ids: dict[str, list[int]] = field(default_factory=dict)
    table_present: bool = False
    rationale: str = UVDB_PURGE_RATIONALE

    @property
    def audit_ids(self) -> list[int]:
        return [int(row["id"]) for row in self.audits]

    def rows_per_table(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        if self.audits:
            counts[UVDB_AUDIT_TABLE] = len(self.audits)
        for table, row_ids in self.child_row_ids.items():
            if row_ids:
                counts[table] = len(row_ids)
        return counts

    def as_report(self) -> dict[str, Any]:
        return {
            "table": UVDB_AUDIT_TABLE,
            "matched_on": "audit_reference == purged audit_runs.reference_number",
            "disposition": "purge",
            "rationale": self.rationale,
            "table_present": self.table_present,
            "row_count": len(self.audits),
            "rows": [
                {
                    "id": row["id"],
                    "audit_reference": row.get("audit_reference"),
                    "company_name": row.get("company_name"),
                    "status": row.get("status"),
                    "percentage_score": row.get("percentage_score"),
                    "tenant_id": row.get("tenant_id"),
                }
                for row in self.audits
            ],
            "children_per_table": {table: len(ids) for table, ids in self.child_row_ids.items()},
            "rows_per_table": self.rows_per_table(),
        }


def _has_table(sync_session: Any, name: str) -> bool:
    return sa.inspect(sync_session.get_bind()).has_table(name)


async def plan_uvdb_catalogue(
    db: Any,
    *,
    references: Sequence[str],
    tenant_id: Optional[int] = None,
) -> UvdbCataloguePlan:
    """Read-only: UVDB catalogue rows whose reference matches a purged audit run."""
    plan = UvdbCataloguePlan()
    if not references:
        return plan

    present = await db.run_sync(lambda sync: _has_table(sync, UVDB_AUDIT_TABLE))
    plan.table_present = present
    if not present:
        return plan

    placeholders = ", ".join(f":ref_{index}" for index in range(len(references)))
    params: dict[str, Any] = {f"ref_{index}": reference for index, reference in enumerate(references)}
    tenant_clause = ""
    if tenant_id is not None:
        # tenant_id is nullable on uvdb_audit historically; assert when the operator did.
        tenant_clause = " AND (tenant_id = :tenant_id OR tenant_id IS NULL)"
        params["tenant_id"] = tenant_id

    rows = (
        (
            await db.execute(
                sa.text(
                    f"SELECT * FROM {UVDB_AUDIT_TABLE} "  # noqa: S608
                    f"WHERE audit_reference IN ({placeholders}){tenant_clause} "
                    "ORDER BY id"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    plan.audits = [dict(row) for row in rows]
    if not plan.audits:
        return plan

    audit_ids = plan.audit_ids
    id_placeholders = ", ".join(f":id_{index}" for index in range(len(audit_ids)))
    id_params = {f"id_{index}": value for index, value in enumerate(audit_ids)}

    for child in UVDB_CHILD_TABLES:
        child_present = await db.run_sync(lambda sync, name=child: _has_table(sync, name))
        if not child_present:
            plan.child_row_ids[child] = []
            continue
        child_ids = list(
            (
                await db.execute(
                    sa.text(
                        f"SELECT id FROM {child} WHERE audit_id IN ({id_placeholders}) "  # noqa: S608
                        "ORDER BY id"
                    ),
                    id_params,
                )
            )
            .scalars()
            .all()
        )
        plan.child_row_ids[child] = [int(value) for value in child_ids]

    return plan


async def apply_uvdb_catalogue(db: Any, plan: UvdbCataloguePlan) -> dict[str, int]:
    """Delete planned UVDB catalogue rows and children. Does not commit.

    Children first, then ``uvdb_audit``. Rowcounts must match the plan — drift
    between dry-run and apply rolls back with the surrounding purge transaction.
    """
    deleted: dict[str, int] = {}
    if not plan.audits:
        return deleted

    for child in UVDB_CHILD_TABLES:
        row_ids = plan.child_row_ids.get(child) or []
        if not row_ids:
            continue
        placeholders = ", ".join(f":id_{index}" for index in range(len(row_ids)))
        params = {f"id_{index}": row_id for index, row_id in enumerate(row_ids)}
        result = await db.execute(
            sa.text(f"DELETE FROM {child} WHERE id IN ({placeholders})"),  # noqa: S608
            params,
        )
        affected = result.rowcount or 0
        if affected != len(row_ids):
            raise RuntimeError(
                f"DELETE FROM {child} affected {affected} rows, expected {len(row_ids)}. "
                "Rolling back; re-run the dry run"
            )
        deleted[child] = affected

    audit_ids = plan.audit_ids
    placeholders = ", ".join(f":id_{index}" for index in range(len(audit_ids)))
    params = {f"id_{index}": row_id for index, row_id in enumerate(audit_ids)}
    result = await db.execute(
        sa.text(f"DELETE FROM {UVDB_AUDIT_TABLE} WHERE id IN ({placeholders})"),  # noqa: S608
        params,
    )
    affected = result.rowcount or 0
    if affected != len(audit_ids):
        raise RuntimeError(
            f"DELETE FROM {UVDB_AUDIT_TABLE} affected {affected} rows, expected {len(audit_ids)}. "
            "Rolling back; re-run the dry run"
        )
    deleted[UVDB_AUDIT_TABLE] = affected
    return deleted
