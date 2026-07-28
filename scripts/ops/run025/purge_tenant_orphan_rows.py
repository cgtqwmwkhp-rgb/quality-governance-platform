#!/usr/bin/env python3
"""Delete case/action rows that have no tenant, after proving the delete is bounded.

This is the production remediation for the orphans that make
``20260901_case_tenant_nn`` refuse, and therefore make the deploy fail. It is
dry-run by default; ``--apply`` is opt-in and a production-looking environment
additionally requires ``--i-understand-prod``.

What it will not do
-------------------
It refuses, rather than warns, on every one of these:

* **A dependent row outside the reviewed set.** If anything references a row we
  are about to delete and is not itself scheduled for deletion, we stop. A
  ``CASCADE`` would destroy it, ``SET NULL`` would quietly rewrite it, and
  ``NO ACTION`` would abort mid-operation. All three mean the reviewed row list
  was not the whole story, which invalidates the human approval it rests on.
* **Row-level security in the way.** Under ``FORCE ROW LEVEL SECURITY`` a role
  without ``rolsuper``/``rolbypassrls`` cannot see a NULL-tenant row at all, so it
  would report nothing to delete and then leave the deploy still failing.
* **Freeing the top of a reference sequence.** ``ReferenceNumberService`` mints
  the next number as ``max(MAX(suffix), COUNT(*)) + 1`` and ``reference_number``
  is UNIQUE, so while an orphan exists it *reserves* its number. Delete the
  highest one and that number becomes mintable again — a future, real record would
  carry a reference a deleted record already used. A gap in the sequence is
  harmless; a reuse is not, and it is invisible afterwards. Override only
  deliberately, with ``--accept-reference-reuse-risk``.

Deletion order is computed from the reflected foreign keys and enforced here,
children before parents, so the operation never relies on a cascade firing.

Audit trail
-----------
This deletes rows that belong to no tenant, and ``audit_log_entries.tenant_id`` is
NOT NULL with a foreign key to ``tenants``. There is therefore no way to record
this in the per-tenant, hash-chained trail without first inventing a tenant for it
— the same attribution the migration refuses to make, in the one register an
external auditor is entitled to trust. So this script does not write to
``audit_log_entries``. Instead ``--manifest`` captures every column of every row
before deletion, which is the evidence to attach to the change record. See the
module docstring of ``inventory_tenant_id_nulls`` and the PR body for the full
argument.

Usage:
  env -u DATABASE_URL -u PRODDB -u STAGING_DB \\
    DATABASE_URL=postgresql+asyncpg://user@host/db \\
    python -m scripts.ops.run025.purge_tenant_orphan_rows --json \\
    --manifest /tmp/orphan-purge-manifest.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
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
from scripts.ops.run025._dependencies import InboundRef, RowKey, deletion_order, dependent_ids, inbound_refs
from scripts.ops.run025._models import migration_target_tables
from scripts.ops.run025.inventory_tenant_id_nulls import dsn_label, _reflect, _rls_blinded

#: ``PREFIX-YYYY-NNNN``, the sequential form ``ReferenceNumberService`` mints.
SEQUENTIAL_REFERENCE = re.compile(r"^([A-Z]+)-(\d{4})-(\d+)$")


class PurgeBlocked(RuntimeError):
    """Raised when the reviewed row set cannot be deleted safely."""


def _reference_parts(reference: Optional[str]) -> Optional[tuple[str, str, int]]:
    if not reference:
        return None
    match = SEQUENTIAL_REFERENCE.match(reference.strip())
    if not match:
        return None
    return match.group(1), match.group(2), int(match.group(3))


async def _candidate_rows(db: Any, tables: list[str], reflected: dict[str, dict[str, Any]]) -> dict[str, list[dict]]:
    """Full contents of every NULL-tenant row, per table.

    Whole rows rather than a projection: this is the only record of what was
    destroyed, so it has to be complete enough to reconstruct from.
    """
    out: dict[str, list[dict]] = {}
    for table in tables:
        # Table name comes from the migration's own TARGET_TABLES literal.
        rows = (
            (await db.execute(sa.text(f"SELECT * FROM {table} WHERE tenant_id IS NULL ORDER BY id")))  # noqa: S608
            .mappings()
            .all()
        )
        if rows:
            out[table] = [dict(row) for row in rows]
    return out


async def _mixed_reference_schemes(db: Any, tables: list[str]) -> list[dict[str, Any]]:
    """Tables holding references the sequential generator cannot parse.

    ``ReferenceNumberService._next_sequence`` takes ``MAX(reference_number)`` as a
    *string*, then ``int(...split("-")[-1])``. The portal mints an eight-hex-digit
    suffix, which sorts above any four-digit one and fails that ``int()``; the
    exception is swallowed and the generator falls back to ``COUNT(*)``. Where both
    forms coexist, the next reference is governed by the row count, so deleting any
    row shifts it and the reuse analysis below cannot be relied on.

    Reported rather than blocking: it is a property of the existing generator, not
    of this deletion, and an operator should see it before drawing conclusions.
    """
    findings: list[dict[str, Any]] = []
    for table in tables:
        rows = (await db.execute(sa.text(f"SELECT reference_number FROM {table}"))).scalars().all()  # noqa: S608
        unparsable = [r for r in rows if r and _reference_parts(r) is None]
        if unparsable and len(unparsable) != len(rows):
            findings.append(
                {
                    "table": table,
                    "non_sequential_references": len(unparsable),
                    "example": unparsable[0],
                    "reason": (
                        "this table mixes sequential and non-sequential references, so the generator "
                        "falls back to COUNT(*) and the reference-reuse check below is not conclusive"
                    ),
                }
            )
    return findings


async def _reference_reuse_findings(db: Any, candidates: dict[str, list[dict]]) -> list[dict[str, Any]]:
    """Rows whose deletion would free a reference number for reuse."""
    findings: list[dict[str, Any]] = []
    for table, rows in candidates.items():
        doomed = {row["id"] for row in rows}
        for row in rows:
            parts = _reference_parts(row.get("reference_number"))
            if parts is None:
                continue
            prefix, year, suffix = parts
            # Compared in Python rather than with a SQL MAX over a substring cast:
            # the numeric suffix is only meaningful for references that match the
            # sequential form, and filtering that in SQL differs between
            # PostgreSQL and the SQLite these scripts are tested against.
            existing = (
                (
                    await db.execute(
                        sa.text(
                            f"SELECT id, reference_number FROM {table} WHERE reference_number LIKE :pattern"
                        ),  # noqa: S608
                        {"pattern": f"{prefix}-{year}-%"},
                    )
                )
                .mappings()
                .all()
            )
            surviving = [
                parsed[2]
                for other in existing
                if other["id"] not in doomed and (parsed := _reference_parts(other["reference_number"])) is not None
            ]
            surviving_max = max(surviving) if surviving else None
            if surviving_max is None or surviving_max < suffix:
                findings.append(
                    {
                        "table": table,
                        "id": row["id"],
                        "reference_number": row["reference_number"],
                        "highest_surviving_suffix": surviving_max,
                        "reason": (
                            "this is the highest reference for its prefix and year, so deleting it "
                            "makes the number mintable again and a future record would reuse it"
                        ),
                    }
                )
    return findings


async def plan(*, limit: int) -> dict[str, Any]:
    """Work out what would be deleted and whether it is safe. Read-only."""
    targets = list(migration_target_tables())

    async with await open_session() as db:
        reflected = await db.run_sync(_reflect, targets)
        blinded = await db.run_sync(_rls_blinded, targets)

        present = [t for t in targets if reflected[t].get("exists") and reflected[t].get("has_tenant_id")]
        blockers: list[str] = []
        if blinded:
            blockers.append(
                "row-level security hides NULL-tenant rows from this role in "
                f"{', '.join(sorted(blinded))}; re-run as a role with rolsuper or rolbypassrls, "
                "because otherwise this script cannot see what it is meant to delete"
            )

        candidates = await _candidate_rows(db, present, reflected)
        candidate_keys: set[RowKey] = {(table, int(row["id"])) for table, rows in candidates.items() for row in rows}

        refs = await db.run_sync(inbound_refs, sorted(candidates))
        edges: list[tuple[RowKey, RowKey]] = []
        in_scope: list[dict[str, Any]] = []
        out_of_scope: list[dict[str, Any]] = []

        for table, rows in candidates.items():
            for ref in refs.get(table, []):
                for row in rows:
                    parent_key: RowKey = (table, int(row["id"]))
                    for child_id in await dependent_ids(db, ref, int(row["id"])):
                        child_key: RowKey = (ref.child_table, child_id)
                        record = {
                            "constraint": ref.constraint,
                            "reference": ref.describe(),
                            "parent": f"{table}#{row['id']}",
                            "child": f"{ref.child_table}#{child_id}",
                            "on_delete": ref.on_delete,
                        }
                        if child_key in candidate_keys:
                            edges.append((child_key, parent_key))
                            in_scope.append(record)
                        else:
                            record["effect"] = _out_of_scope_effect(ref)
                            out_of_scope.append(record)

        if out_of_scope:
            blockers.append(
                f"{len(out_of_scope)} row(s) outside the reviewed set are affected by these deletes; "
                "see dependents_outside_reviewed_set. Deleting anyway would remove or silently "
                "rewrite records nobody approved"
            )

        reuse = await _reference_reuse_findings(db, candidates)
        mixed = await _mixed_reference_schemes(db, sorted(candidates))
        try:
            order = deletion_order(candidate_keys, edges)
        except RuntimeError as exc:
            order = []
            blockers.append(str(exc))

    return {
        "database": dsn_label(require_database_url()),
        "target_tables": targets,
        "rows_to_delete": sum(len(rows) for rows in candidates.values()),
        "rows_per_table": {table: len(rows) for table, rows in sorted(candidates.items())},
        "deletion_order": [f"{table}#{row_id}" for table, row_id in order],
        "rows": {table: rows[: max(1, limit)] for table, rows in sorted(candidates.items())},
        "dependents_inside_reviewed_set": in_scope,
        "dependents_outside_reviewed_set": out_of_scope,
        "reference_reuse_risk": reuse,
        "reference_scheme_caveats": mixed,
        "tables_hidden_by_rls": sorted(blinded),
        "blockers": blockers,
        "_order": order,
        "_candidates": candidates,
        "_reuse": reuse,
    }


def _out_of_scope_effect(ref: InboundRef) -> str:
    if ref.deletes_child:
        return "WOULD BE DELETED by cascade — destruction of a record outside the reviewed set"
    if ref.mutates_child:
        return f"WOULD BE MODIFIED ({ref.on_delete}) — silent rewrite of a row outside the reviewed set"
    return "WOULD BLOCK the delete — the statement will fail"


async def apply_plan(order: list[RowKey]) -> dict[str, int]:
    """Delete the planned rows, children first, in one transaction."""
    deleted: dict[str, int] = {}
    async with await open_session() as db:
        for table, row_id in order:
            result = await db.execute(
                sa.text(f"DELETE FROM {table} WHERE id = :row_id"),  # noqa: S608
                {"row_id": row_id},
            )
            deleted[table] = deleted.get(table, 0) + (result.rowcount or 0)
        await db.commit()
    return deleted


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


async def _amain(args: argparse.Namespace) -> int:
    mode = enforce_apply_safety(apply=args.apply, i_understand_prod=args.i_understand_prod)
    require_database_url()

    result = await plan(limit=args.limit)
    order = result.pop("_order")
    candidates = result.pop("_candidates")
    reuse = result.pop("_reuse")

    blockers = list(result["blockers"])
    if reuse and not args.accept_reference_reuse_risk:
        blockers.append(
            f"{len(reuse)} row(s) hold the highest reference number for their prefix and year; "
            "deleting them frees those numbers for reuse by a future record. Re-run with "
            "--accept-reference-reuse-risk only if a named human has accepted that"
        )
    result["blockers"] = blockers

    payload: dict[str, Any] = {"script": "purge_tenant_orphan_rows", "mode": mode, **result}

    if args.manifest:
        _write_manifest(
            Path(args.manifest),
            {
                "script": "purge_tenant_orphan_rows",
                "mode": mode,
                "database": result["database"],
                "captured_at": utc_now_iso(),
                "deletion_order": result["deletion_order"],
                "rows": candidates,
                "blockers": blockers,
                "note": (
                    "Full contents of every row proposed for deletion, captured before any "
                    "delete ran. These rows belong to no tenant, so the deletion cannot be "
                    "recorded in the per-tenant hash-chained audit_log_entries without "
                    "inventing a tenant for it. Attach this file to the change record instead."
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
        payload["note"] = "No NULL-tenant rows in the migration's target tables. The migration will apply cleanly."
        emit_report(payload, as_json=args.json)
        return 0

    if not args.apply:
        payload["outcome"] = "dry-run"
        payload["note"] = (
            "No writes performed. Review 'rows' and 'deletion_order', keep the manifest with the "
            "change record, then re-run with --apply (plus --i-understand-prod on production)."
        )
        emit_report(payload, as_json=args.json)
        return 1

    if not args.manifest:
        payload["outcome"] = "refused"
        payload["note"] = "--apply requires --manifest: an unrecorded delete of audited rows is not acceptable."
        emit_report(payload, as_json=args.json)
        return 2

    payload["deleted"] = await apply_plan(order)
    payload["outcome"] = "applied"
    payload["note"] = "Rows deleted, children first. Re-run inventory_tenant_id_nulls to confirm zero orphans."
    emit_report(payload, as_json=args.json)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    parser.add_argument(
        "--manifest",
        default=None,
        help="Path to write the full pre-deletion row contents. Required with --apply.",
    )
    parser.add_argument(
        "--accept-reference-reuse-risk",
        action="store_true",
        default=False,
        dest="accept_reference_reuse_risk",
        help="Proceed even though a deleted reference number could later be reissued.",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
