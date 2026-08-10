#!/usr/bin/env python3
"""Hard-delete named duplicate audit runs and everything that belongs to them.

FR-DEDUP-01. Production shows the same B2 audit for Plantexpand Limited three
times: ``AUD-2026-0043`` and ``AUD-2026-0048`` are re-imports of a report that was
already imported and subsequently updated. The two re-imports are to be removed as
if they had never existed; the earlier, updated audit survives.

This deletes rows. It does not set a ``deleted_at`` column, and it is not a
soft delete wearing a different name — the requirement is that the register stops
showing the duplicate anywhere, including in exports and analytics that do not
filter on a deleted flag.

Why the rows are deleted explicitly rather than by cascade
----------------------------------------------------------
Deleting the ``audit_runs`` row and letting the database do the rest looks
sufficient — ``audit_responses``, ``audit_findings``, ``external_audit_import_jobs``
and ``external_audit_import_drafts`` all cascade. It is not.
``external_audit_records.audit_run_id`` carries no ``ondelete`` clause, so it is
``NO ACTION``: on an imported audit the cascade delete raises a foreign key
violation and rolls back, and the operator sees a stack trace rather than a purge.
So every row is deleted explicitly, children first, in an order computed from the
reflected foreign keys. See ``_closure``.

What it refuses to do
---------------------
Dry-run is the default; ``--apply`` is opt-in and needs ``--i-understand-prod`` on a
production-looking environment. On top of that it refuses, rather than warns, on:

* **A reference that is not there.** A typo would otherwise report "nothing to
  delete, all clear" and be believed.
* **A reference belonging to another tenant.** The tenant is asserted on the command
  line and checked against the row, which is what catches being pointed at the wrong
  database.
* **Deleting a whole duplicate group.** If nothing sharing the audit's identity
  survives the purge, this stops. The instruction was to remove duplicates, and a
  "duplicate" with no surviving original is just a record being destroyed. See
  ``--allow-no-survivor``.
* **A referencing table nobody has classified.** New tables get added; a purge that
  silently swept them, or silently orphaned them, would be worse than one that stops.
* **A CAPA action raised from a doomed finding.** Corrective actions are a governed
  register with their own reference numbers and verification history. They are
  reported and the purge stops; a human withdraws or reassigns them first.
* **Freeing a reference number for reuse or collision.** ``ReferenceNumberService``
  mints ``max(MAX(suffix), COUNT(*)) + 1``, so deleting rows can only lower the next
  value. ``AUD-2026-0048`` is very likely the highest audit reference for the year.
  See ``--accept-reference-reuse-risk`` and ``run025/_references``.
* **``--apply`` without ``--manifest``.** The manifest is the only remaining record
  of the row contents.

The purge is recorded in the tenant's hash-chained ``audit_log_entries`` in the same
transaction as the deletes — see ``_chain``.

Usage:
  # Dry run (default). Writes nothing.
  env DATABASE_URL=postgresql+asyncpg://user@host/db \\
    python -m scripts.ops.run027.purge_duplicate_audit_runs \\
    --tenant-id 1 --reference AUD-2026-0043 --reference AUD-2026-0048 --json

  # Apply, after the runbook sign-off.
  env DATABASE_URL=postgresql+asyncpg://user@host/db APP_ENV=production \\
    python -m scripts.ops.run027.purge_duplicate_audit_runs \\
    --tenant-id 1 --reference AUD-2026-0043 --reference AUD-2026-0048 \\
    --apply --i-understand-prod --manifest /tmp/dedup-audit-twins-manifest.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Optional

import sqlalchemy as sa

from scripts.ops.run021._common import (
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    open_session,
    require_database_url,
    utc_now_iso,
)
from scripts.ops.run025._dependencies import RowKey, deletion_order
from scripts.ops.run025._references import mixed_reference_schemes, reference_arithmetic
from scripts.ops.run027._chain import record_purge
from scripts.ops.run027._closure import descendant_closure, row_snapshots
from scripts.ops.run027._duplicates import REGISTERS, fetch_rows, identity_key, resolve
from scripts.ops.run027._soft_links import delete_soft_links, soft_link_hits

__all__ = [
    "FR_DEDUP_01_REFERENCES",
    "FR_DEDUP_01_TENANT",
    "PurgeBlocked",
    "plan",
    "apply_plan",
    "main",
]

#: The references FR-DEDUP-01 authorises, and the tenant they belong to.
#:
#: Not a default. They are pinned so the runbook, the tests and the PR body cannot
#: drift from one another, but the operator still names them on the command line —
#: a delete of a governed record is authorised by a human naming the record, not by
#: a constant in a file.
FR_DEDUP_01_REFERENCES: tuple[str, ...] = ("AUD-2026-0043", "AUD-2026-0048")
FR_DEDUP_01_TENANT: int = 1

#: The register whose rows are the roots of the purge.
ROOT_TABLE = "audit_runs"


class PurgeBlocked(RuntimeError):
    """Raised when the named rows cannot be deleted safely."""


async def _roots_by_reference(
    db: Any,
    references: list[str],
    *,
    tenant_id: Optional[int],
) -> tuple[list[dict[str, Any]], list[str]]:
    """The ``audit_runs`` rows for these references, and any reason to stop.

    ``reference_number`` is UNIQUE, so the tenant is not needed to identify the row.
    It is still required and still checked: the failure this catches is not an
    ambiguous reference, it is an operator connected to the wrong database or the
    wrong tenant's data, and in that situation a globally-unique reference resolves
    perfectly to entirely the wrong record.
    """
    blockers: list[str] = []
    if not references:
        return [], ["no --reference given; this script only ever deletes rows named explicitly"]

    placeholders = ", ".join(f":ref_{index}" for index in range(len(references)))
    params = {f"ref_{index}": reference for index, reference in enumerate(references)}
    rows = (
        (
            await db.execute(
                sa.text(
                    f"SELECT * FROM {ROOT_TABLE} "  # noqa: S608
                    f"WHERE reference_number IN ({placeholders}) ORDER BY id"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    found = [dict(row) for row in rows]

    seen = {str(row.get("reference_number")) for row in found}
    for reference in references:
        if reference not in seen:
            blockers.append(
                f"{reference} does not exist in {ROOT_TABLE}. Refusing rather than reporting "
                "'nothing to delete': a mistyped reference and an already-purged one look "
                "identical from here"
            )

    if tenant_id is not None:
        for row in found:
            if row.get("tenant_id") != tenant_id:
                blockers.append(
                    f"{row.get('reference_number')} belongs to tenant {row.get('tenant_id')!r}, "
                    f"not the asserted tenant {tenant_id}. Refusing: either the wrong tenant was "
                    "given or this is the wrong database"
                )

    return found, blockers


async def _survivor_check(
    db: Any,
    roots: list[dict[str, Any]],
    *,
    tenant_id: Optional[int],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Whether anything sharing each doomed audit's identity survives the purge.

    This is the check that makes the operation a deduplication rather than a
    deletion. It uses the same identity definition as the scanner, so the two cannot
    disagree about what counts as the same audit.
    """
    resolved, _skipped = await db.run_sync(resolve, [spec for spec in REGISTERS if spec.table == ROOT_TABLE])
    if not resolved:
        return [], [
            f"{ROOT_TABLE} could not be resolved for duplicate identity, so it is not possible to "
            "confirm a survivor would remain. Refusing"
        ]

    register = resolved[0]
    rows = await fetch_rows(db, register, tenant_id=tenant_id)
    doomed_ids = {row["id"] for row in roots}

    by_key: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        by_key.setdefault(identity_key(row, register), []).append(row)

    report: list[dict[str, Any]] = []
    blockers: list[str] = []
    for root in roots:
        key = identity_key(root, register)
        group = by_key.get(key, [])
        survivors = [row for row in group if row[register.key_column] not in doomed_ids]
        report.append(
            {
                "purging": root.get("reference_number"),
                "identity": dict(zip(register.identity_columns, key[1:])),
                "group_size": len(group),
                "survivors": [
                    {
                        "id": row[register.key_column],
                        "reference": row.get("reference_number"),
                        "created_at": row.get("created_at"),
                        "completed_at": row.get("completed_at"),
                    }
                    for row in survivors
                ],
            }
        )
        if not survivors:
            blockers.append(
                f"purging {root.get('reference_number')} would leave nothing sharing its identity "
                f"({dict(zip(register.identity_columns, key[1:]))}). That is not deduplication, it is "
                "destroying the only copy of an audit. Re-run with --allow-no-survivor only if a named "
                "human has accepted that"
            )

    return report, blockers


async def _collateral_risks(db: Any, finding_ids: list[int]) -> list[dict[str, Any]]:
    """Enterprise risks linked to doomed findings by the junction being deleted.

    The junction row goes, the risk does not. Reported because a risk escalated from
    a duplicate finding is itself probably a duplicate — and because after the purge
    its title may name an audit that no longer exists, which is the sort of dangling
    reference an auditor notices. Deleting a risk register entry is a bigger decision
    than deduplicating an audit, so it stays a human's.
    """
    if not finding_ids:
        return []
    inspector_tables = await db.run_sync(lambda sync: sa.inspect(sync.get_bind()).get_table_names())
    if "audit_finding_risks" not in inspector_tables or "risks_v2" not in inspector_tables:
        return []

    placeholders = ", ".join(f":id_{index}" for index in range(len(finding_ids)))
    params = {f"id_{index}": value for index, value in enumerate(finding_ids)}
    rows = (
        (
            await db.execute(
                sa.text(
                    "SELECT j.audit_finding_id, r.id AS risk_id, r.reference, r.title "
                    "FROM audit_finding_risks j JOIN risks_v2 r ON r.id = j.risk_id "
                    f"WHERE j.audit_finding_id IN ({placeholders}) ORDER BY r.id"  # noqa: S608
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    return [
        {
            "risk": f"risks_v2#{row['risk_id']}",
            "reference": row.get("reference"),
            "title": row.get("title"),
            "was_linked_to": f"audit_findings#{row['audit_finding_id']}",
            "effect": "link removed; the risk row survives and is not touched by this purge",
        }
        for row in rows
    ]


async def plan(*, references: list[str], tenant_id: Optional[int], limit: int) -> dict[str, Any]:
    """Work out exactly what would be deleted and whether it is safe. Read-only."""
    async with await open_session() as db:
        roots, blockers = await _roots_by_reference(db, references, tenant_id=tenant_id)
        if blockers:
            # Returned with the same keys as a full plan, all empty. A caller that
            # reads result["deletion_order"] must not get a KeyError depending on how
            # far the plan got.
            return {
                "references": references,
                "tenant_id": tenant_id,
                "audits_found": [
                    {"id": row["id"], "reference_number": row.get("reference_number"), "title": row.get("title")}
                    for row in roots
                ],
                "rows_to_delete": 0,
                "rows_per_table": {},
                "deletion_order": [],
                "child_inventory": [],
                "child_inventory_total": 0,
                "rows_set_to_null_outside_purge": [],
                "soft_references": [],
                "collateral_risks": [],
                "duplicate_group_survivors": [],
                "reference_arithmetic": [],
                "reference_scheme_caveats": [],
                "blockers": blockers,
                "_survivor_blockers": [],
                "_hazards": [],
                "_order": [],
                "_snapshots": {},
                "_soft_hits": [],
                "_roots": roots,
                "_key_columns": {},
            }

        root_keys: list[RowKey] = [(ROOT_TABLE, int(row["id"])) for row in roots]
        closure = await descendant_closure(db, roots=root_keys)
        blockers.extend(closure.blockers)

        soft_hits, soft_blockers = await soft_link_hits(db, purge_keys=sorted(closure.purge_keys))
        blockers.extend(soft_blockers)

        survivors, survivor_blockers = await _survivor_check(db, roots, tenant_id=tenant_id)

        snapshots = await row_snapshots(db, sorted(closure.purge_keys), closure.key_columns)
        collateral = await _collateral_risks(db, closure.ids_for("audit_findings"))

        # Reference arithmetic for every purged table that mints references, not just
        # audit_runs: deleting findings moves the FND sequence by exactly the same
        # mechanism, and a collision there stops anyone raising a finding at all.
        arithmetic: list[dict[str, Any]] = []
        caveats: list[dict[str, Any]] = []
        for table, rows in sorted(snapshots.items()):
            if not rows:
                continue
            column = next((candidate for candidate in ("reference_number", "reference") if candidate in rows[0]), None)
            if column is None:
                continue
            key_column = closure.key_columns[table]
            doomed = {row[key_column]: row.get(column) for row in rows}
            for entry in await reference_arithmetic(
                db, table=table, column=column, key_column=key_column, doomed=doomed
            ):
                arithmetic.append(entry.as_report())
            caveat = await mixed_reference_schemes(db, table, column)
            if caveat:
                caveats.append(caveat)

        try:
            order = deletion_order(closure.purge_keys, closure.edges)
        except RuntimeError as exc:
            order = []
            blockers.append(str(exc))

    hazards = [entry for entry in arithmetic if entry["verdict"].startswith(("COLLISION", "REISSUE"))]

    return {
        "references": references,
        "tenant_id": tenant_id,
        "audits_found": [
            {
                "id": row["id"],
                "reference_number": row.get("reference_number"),
                "title": row.get("title"),
                "status": str(row.get("status")),
                "score_percentage": row.get("score_percentage"),
                "completed_at": row.get("completed_at"),
            }
            for row in roots
        ],
        "rows_to_delete": len(closure.purge_keys),
        "rows_per_table": closure.rows_per_table(),
        "deletion_order": [f"{table}#{row_id}" for table, row_id in order],
        "child_inventory": closure.found[: max(1, limit)],
        "child_inventory_total": len(closure.found),
        "rows_set_to_null_outside_purge": closure.detached,
        "soft_references": [hit.as_report() for hit in soft_hits],
        "collateral_risks": collateral,
        "duplicate_group_survivors": survivors,
        "reference_arithmetic": arithmetic,
        "reference_scheme_caveats": caveats,
        "blockers": blockers,
        "_survivor_blockers": survivor_blockers,
        "_hazards": hazards,
        "_order": order,
        "_snapshots": snapshots,
        "_soft_hits": soft_hits,
        "_roots": roots,
        "_key_columns": closure.key_columns,
    }


async def apply_plan(
    *,
    order: list[RowKey],
    soft_hits: list[Any],
    snapshots: dict[str, list[dict[str, Any]]],
    key_columns: dict[str, str],
    references: list[str],
    tenant_id: int,
    actor_email: Optional[str],
) -> dict[str, Any]:
    """Delete the planned rows and record the purge, in one transaction.

    Everything happens inside a single transaction: the soft-referencing rows, the
    foreign-key closure children-first, and the audit trail entry. A failure at any
    point leaves the register exactly as it was, and there is no state in which the
    rows are gone but the trail does not say so.
    """
    deleted: dict[str, int] = {}
    async with await open_session() as db:
        soft_deleted = await delete_soft_links(db, soft_hits)

        for table, row_id in order:
            key_column = key_columns[table]
            result = await db.execute(
                sa.text(f"DELETE FROM {table} WHERE {key_column} = :row_id"),  # noqa: S608
                {"row_id": row_id},
            )
            affected = result.rowcount or 0
            if affected != 1:
                # Reflected, planned, then not deleted. Either something else removed
                # it between the plan and the apply, or the delete matched more than
                # the row it named. Both mean the plan no longer describes reality.
                raise PurgeBlocked(
                    f"DELETE FROM {table} WHERE {key_column} = {row_id} affected {affected} rows, "
                    "expected 1. Rolling back; re-run the dry run"
                )
            deleted[table] = deleted.get(table, 0) + affected

        trail = await record_purge(
            db,
            tenant_id=tenant_id,
            references=references,
            old_values={"audit_runs": snapshots.get("audit_runs", [])},
            metadata={
                "script": "scripts.ops.run027.purge_duplicate_audit_runs",
                "requirement": "FR-DEDUP-01",
                "rows_deleted_per_table": {**soft_deleted, **deleted},
                "reason": "duplicate re-import of an audit report already present in the register",
            },
            actor_email=actor_email,
        )

        # Prove the rows are gone before committing, rather than inferring it from
        # rowcounts. A residual row here means the plan and the schema disagree.
        placeholders = ", ".join(f":ref_{index}" for index in range(len(references)))
        residual = (
            (
                await db.execute(
                    sa.text(
                        f"SELECT reference_number FROM {ROOT_TABLE} "  # noqa: S608
                        f"WHERE reference_number IN ({placeholders})"
                    ),
                    {f"ref_{index}": reference for index, reference in enumerate(references)},
                )
            )
            .scalars()
            .all()
        )
        if residual:
            raise PurgeBlocked(f"{sorted(residual)} still present after the delete. Rolling back")

        await db.commit()

    return {"foreign_key_rows": deleted, "soft_reference_rows": soft_deleted, "audit_trail_entry": trail}


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


async def _amain(args: argparse.Namespace) -> int:
    mode = enforce_apply_safety(apply=args.apply, i_understand_prod=args.i_understand_prod)
    require_database_url()

    references = list(dict.fromkeys(args.reference or []))
    result = await plan(references=references, tenant_id=args.tenant_id, limit=args.limit)

    order = result.pop("_order")
    snapshots = result.pop("_snapshots")
    soft_hits = result.pop("_soft_hits")
    result.pop("_roots")
    key_columns = result.pop("_key_columns")
    survivor_blockers = result.pop("_survivor_blockers", [])
    hazards = result.pop("_hazards", [])

    blockers = list(result["blockers"])
    if survivor_blockers and not args.allow_no_survivor:
        blockers.extend(survivor_blockers)
    if hazards and not args.accept_reference_reuse_risk:
        blockers.append(
            f"{len(hazards)} reference pattern(s) would reissue a deleted number or collide with a "
            "surviving one; see reference_arithmetic. Re-run with --accept-reference-reuse-risk only "
            "if a named human has accepted that"
        )
    if args.apply and args.tenant_id is None:
        blockers.append("--apply requires --tenant-id: the tenant must be asserted and checked, not inferred")
    result["blockers"] = blockers

    payload: dict[str, Any] = {"script": "purge_duplicate_audit_runs", "mode": mode, **result}

    if args.manifest:
        _write_manifest(
            Path(args.manifest),
            {
                "script": "purge_duplicate_audit_runs",
                "requirement": "FR-DEDUP-01",
                "mode": mode,
                "captured_at": utc_now_iso(),
                "references": references,
                "tenant_id": args.tenant_id,
                "deletion_order": result["deletion_order"],
                "rows": snapshots,
                "soft_references": result["soft_references"],
                "rows_set_to_null_outside_purge": result["rows_set_to_null_outside_purge"],
                "collateral_risks": result["collateral_risks"],
                "duplicate_group_survivors": result["duplicate_group_survivors"],
                "reference_arithmetic": result["reference_arithmetic"],
                "blockers": blockers,
                "note": (
                    "Full contents of every row proposed for deletion, captured before any delete ran. "
                    "The purge is also recorded in the tenant's hash-chained audit_log_entries; this "
                    "file is the row-level detail that the trail entry summarises. Attach it to the "
                    "change record."
                ),
            },
        )
        payload["manifest_written_to"] = str(args.manifest)

    if blockers:
        payload["outcome"] = "refused"
        payload["note"] = "Nothing was deleted. Resolve every blocker above, then re-run the dry run."
        emit_report(payload, as_json=args.json)
        return 3

    if not order:
        payload["outcome"] = "nothing-to-do"
        payload["note"] = "No rows matched. Nothing to purge."
        emit_report(payload, as_json=args.json)
        return 0

    if not args.apply:
        payload["outcome"] = "dry-run"
        payload["note"] = (
            "No writes performed. Review child_inventory, soft_references, collateral_risks and "
            "duplicate_group_survivors, keep the manifest with the change record, then re-run with "
            "--apply (plus --i-understand-prod on production)."
        )
        emit_report(payload, as_json=args.json)
        return 1

    if not args.manifest:
        payload["outcome"] = "refused"
        payload["note"] = "--apply requires --manifest: an unrecorded hard delete of an audit is not acceptable."
        emit_report(payload, as_json=args.json)
        return 2

    try:
        payload["deleted"] = await apply_plan(
            order=order,
            soft_hits=soft_hits,
            snapshots=snapshots,
            key_columns=key_columns,
            references=references,
            tenant_id=int(args.tenant_id),
            actor_email=args.actor_email,
        )
    except PurgeBlocked as exc:
        payload["outcome"] = "refused"
        payload["note"] = f"Transaction rolled back: {exc}"
        emit_report(payload, as_json=args.json)
        return 4

    payload["outcome"] = "applied"
    payload["note"] = (
        "Rows deleted, children first, and the purge recorded in audit_log_entries. Re-run this "
        "script with the same arguments to confirm it now refuses with 'does not exist'."
    )
    emit_report(payload, as_json=args.json)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    parser.add_argument(
        "--reference",
        action="append",
        default=None,
        metavar="AUD-YYYY-NNNN",
        help=(
            "Audit reference to purge. Repeatable, and required — nothing is deleted unless it is "
            f"named here. FR-DEDUP-01 authorises exactly {' and '.join(FR_DEDUP_01_REFERENCES)}."
        ),
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Path to write the full pre-deletion row contents. Required with --apply.",
    )
    parser.add_argument(
        "--actor-email",
        default=None,
        help="Email of the human who approved this run, recorded on the audit trail entry.",
    )
    parser.add_argument(
        "--allow-no-survivor",
        action="store_true",
        default=False,
        dest="allow_no_survivor",
        help="Proceed even though no record sharing the audit's identity would survive the purge.",
    )
    parser.add_argument(
        "--accept-reference-reuse-risk",
        action="store_true",
        default=False,
        dest="accept_reference_reuse_risk",
        help="Proceed even though a deleted reference could later be reissued or collide.",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
