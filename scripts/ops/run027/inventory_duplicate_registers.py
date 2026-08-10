#!/usr/bin/env python3
"""Find candidate duplicates across the audit, risk, action and case registers.

The second half of FR-DEDUP-01: having established that the same B2 audit was
imported three times, the obvious question is where else that has happened.

**This script has no ``--apply`` and never will.** It cannot delete anything, so
there is no dangerous flag to leave off by accident. That is deliberate rather than
unfinished: a duplicate is a judgement about two records meaning the same real-world
event, and only a human can make it. Two site inspections of the same yard on the
same day by the same auditor may be a double import, or may be a morning and
afternoon visit. Nothing in the database distinguishes those.

So the output is an input to a review. When a group has been reviewed and a decision
made, the removal goes through ``purge_duplicate_audit_runs`` with the surviving and
doomed references named explicitly on the command line.

What "the same record" means is defined in ``_duplicates`` and shared with the purge,
so the survivor check there and the groups here cannot disagree.

Reading the output
-----------------
* ``groups`` — rows sharing an identity, largest first. ``members`` carries each
  row's reference and the volatile columns (``created_at``, ``completed_at``,
  ``status``) that tell you which is the original.
* ``import_derived`` on an audit group — how many members have an
  ``external_audit_import_jobs`` row. A group where every member does is the
  signature of a re-imported report, which is the FR-DEDUP-01 case. A group where
  none do is more likely two genuine audits with the same name.
* ``registers_skipped`` — registers that were *not* examined, and why. Read this
  before concluding a register is clean: "no duplicates found" and "not looked at"
  are very different answers and this is where they are told apart.

Usage:
  env DATABASE_URL=postgresql+asyncpg://user@host/db \\
    python -m scripts.ops.run027.inventory_duplicate_registers --tenant-id 1 --json
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any, Optional

import sqlalchemy as sa

from scripts.ops.run021._common import emit_report, open_session, require_database_url
from scripts.ops.run027._duplicates import REGISTERS, fetch_rows, group_duplicates, resolve

__all__ = ["scan", "main"]


async def _import_derived_counts(db: Any, audit_ids: list[int]) -> dict[int, int]:
    """How many import jobs each audit run has.

    Distinguishes "the same report imported twice" from "two audits that happen to
    share a title", which is the difference between a defect and a coincidence.
    """
    if not audit_ids:
        return {}
    tables = await db.run_sync(lambda sync: sa.inspect(sync.get_bind()).get_table_names())
    if "external_audit_import_jobs" not in tables:
        return {}

    placeholders = ", ".join(f":id_{index}" for index in range(len(audit_ids)))
    params = {f"id_{index}": value for index, value in enumerate(audit_ids)}
    rows = (
        await db.execute(
            sa.text(
                "SELECT audit_run_id, COUNT(*) AS jobs FROM external_audit_import_jobs "
                f"WHERE audit_run_id IN ({placeholders}) GROUP BY audit_run_id"  # noqa: S608
            ),
            params,
        )
    ).all()
    return {int(row[0]): int(row[1]) for row in rows}


async def scan(*, tenant_id: Optional[int], limit: int, min_group_size: int) -> dict[str, Any]:
    """Group every resolvable register by identity. Read-only."""
    async with await open_session() as db:
        usable, skipped = await db.run_sync(resolve, REGISTERS)

        groups: list[dict[str, Any]] = []
        scanned: list[dict[str, Any]] = []

        for register in usable:
            rows = await fetch_rows(db, register, tenant_id=tenant_id)
            found = group_duplicates(rows, register, min_group_size=min_group_size)

            if register.table == "audit_runs":
                member_ids = [member["id"] for group in found for member in group["members"]]
                jobs = await _import_derived_counts(db, member_ids)
                for group in found:
                    for member in group["members"]:
                        member["import_jobs"] = jobs.get(member["id"], 0)
                    group["import_derived"] = sum(1 for member in group["members"] if member["import_jobs"])

            groups.extend(found)
            scanned.append(
                {
                    "register": register.name,
                    "table": register.table,
                    "rows_examined": len(rows),
                    "grouped_on": list(register.identity_columns),
                    "duplicate_groups": len(found),
                    "rows_in_duplicate_groups": sum(group["count"] for group in found),
                    **({"identity_columns_absent": list(register.skipped_columns)} if register.skipped_columns else {}),
                }
            )

    groups.sort(key=lambda group: (-group["count"], str(group["register"]), str(group["identity"])))

    return {
        "tenant_id": tenant_id,
        "registers_scanned": scanned,
        "registers_skipped": skipped,
        "duplicate_groups_total": len(groups),
        "rows_in_duplicate_groups_total": sum(group["count"] for group in groups),
        "groups": groups[: max(1, limit)],
        "groups_truncated": max(0, len(groups) - max(1, limit)),
        "note": (
            "Candidates for human review, not a work queue. Nothing here has been deleted or "
            "modified; this script cannot do either. Once a group is reviewed, purge the agreed "
            "duplicates with scripts.ops.run027.purge_duplicate_audit_runs, naming each reference "
            "explicitly. Check registers_skipped before concluding a register is clean."
        ),
    }


async def _amain(args: argparse.Namespace) -> int:
    require_database_url()
    result = await scan(tenant_id=args.tenant_id, limit=args.limit, min_group_size=args.min_group_size)
    emit_report({"script": "inventory_duplicate_registers", "mode": "report-only", **result}, as_json=args.json)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # add_safety_args is deliberately not used: it contributes --apply, and this
    # script must not have one.
    parser.add_argument("--tenant-id", type=int, default=None, help="Restrict the scan to one tenant.")
    parser.add_argument("--json", action="store_true", default=False, help="Emit machine-readable JSON.")
    parser.add_argument("--limit", type=int, default=200, help="Max groups to print (default 200).")
    parser.add_argument(
        "--min-group-size",
        type=int,
        default=2,
        dest="min_group_size",
        help="Only report identities shared by at least this many rows (default 2).",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
