#!/usr/bin/env python3
"""Census the two schema drifts that break queries, taken from the database.

Read-only. Reports three things about a live database, and exits 1 if any of
them is non-empty outside the deferral register:

1. **Declared columns the database does not have.** Every one of these is a
   latent ``UndefinedColumn``: SQLAlchemy emits the full mapped column list for
   a whole-entity load, so a single absent column makes the entire table
   unreadable through the ORM, not just the queries that name it.
2. **Attribution columns with no foreign key to ``users``.** ``AuditTrailMixin``
   declares ``created_by_id`` / ``updated_by_id`` but attaches no
   ``ForeignKey``, so on every table that takes its attribution columns from the
   mixin alone, ``created_by_id`` may point at a user id that does not exist.
3. **Orphaned attribution values.** Adding the constraint in (2) fails on any
   database that already holds one, which is the failure mode migration #1398
   exists to prevent. Counted before anything is proposed, never repaired here.

Why this is not ``verify_model_schema_parity``
----------------------------------------------
That script is the right shape for drift 1 but has two blind spots, and both
understate it:

* It skips every name in ``_ALEMBIC_CHECK_EXCLUDED_TABLES``, so the columns
  missing from the ~40 deferred tables are not merely deferred, they are
  invisible. On this repository that is the difference between 15 findings and
  19.
* It reads the database through ``sa.inspect()``, whose ``get_table_names()`` is
  fine, but it then iterates the *model's* columns. For drift 1 that direction
  is correct. For drift 2 it is not: an attribution column on a table with no
  model, or with a model whose name was excluded, cannot be seen at all. So the
  attribution census here enumerates from ``information_schema`` and treats the
  models as the thing being audited rather than the source of the table list.

The reverse direction is reported too (``database_only_columns``), unranked and
ungated, because it is the direction every model-driven tool in this repository
is structurally unable to see, and because on this repository it is what
explains drift 1: the eight tables missing ``created_by_id`` all carry a
``created_by VARCHAR(100)`` that no model declares.

Usage:
  env -u DATABASE_URL -u PRODDB -u STAGING_DB \\
    DATABASE_URL=postgresql+asyncpg://user@host/db \\
    python -m scripts.ops.run026.audit_attribution_schema --json
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any, Optional

import sqlalchemy as sa

from scripts.ops.run021._common import (
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    open_session,
    require_database_url,
    truncate,
)
from scripts.ops.run025._models import alembic_check_excluded_tables, load_metadata
from scripts.ops.run025.inventory_tenant_id_nulls import dsn_label

#: The attribution columns ``AuditTrailMixin`` declares.
ATTRIBUTION_COLUMNS: tuple[str, ...] = ("created_by_id", "updated_by_id")

#: Table every attribution column must reference.
ATTRIBUTION_TARGET = "users"

# Declared-but-absent columns that are deliberately not being added, with the
# owner who holds the decision. Everything else in that list fails this check.
#
# soa_control_entries is not a case of "the database is missing four columns".
# The physical table is a rename of the legacy singular `soa_control_entry` and
# carries a different design: `inclusion_justification` + `exclusion_justification`
# where the model has one `justification`, `implementation_description` where the
# model has `implementation_method`, plus `responsible_party` and
# `target_completion_date` that the model does not declare at all. Which of the
# two justifications the model's single column means is an IMS domain question,
# not a schema question, and guessing it would silently mis-file compliance
# evidence. `SoAControlEntry` is queried by no live code path, so nothing is
# breaking while the owner decides.
DEFERRED_ABSENT_COLUMNS: dict[tuple[str, str], str] = {
    ("soa_control_entries", "implementation_method"): "IMS / ISO27001",
    ("soa_control_entries", "justification"): "IMS / ISO27001",
    ("soa_control_entries", "risk_treatment_reference"): "IMS / ISO27001",
    ("soa_control_entries", "tenant_id"): "IMS / ISO27001",
}

# Tables whose model is retained in metadata after a migration dropped the
# physical table. Absent columns on these are an artefact of the retained model,
# not drift, and are reported separately.
#
# Empty since 2026-07-29. Its only entry was `root_cause_analyses`, and the
# retained model was deleted rather than kept, so the table is no longer declared
# by anything and can never reach the loop below — which only walks tables
# `load_metadata()` returns. The set is kept rather than removed because the
# classification it drives (`absent_columns_on_dropped_tables`,
# `physical_table_dropped`) is part of this report's published shape, and because
# naming a table here that nothing declares would be a false claim that silently
# diverts findings away from the failing bucket if a model of that name returns.
DROPPED_PHYSICAL_TABLES: frozenset[str] = frozenset()


def _declared_columns() -> dict[str, dict[str, bool]]:
    """``{table: {column: nullable}}`` for every mapped table, nothing skipped."""
    return {
        table_name: {column.name: bool(column.nullable) for column in table.c}
        for table_name, table in load_metadata().tables.items()
    }


def _database_columns(sync_conn: Any) -> dict[str, dict[str, dict[str, Any]]]:
    """``{table: {column: {...}}}`` from ``information_schema``, base tables only."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    rows = sync_conn.execute(sa.text("""
            SELECT c.table_name, c.column_name, c.is_nullable, c.data_type
            FROM information_schema.columns AS c
            JOIN information_schema.tables AS t
              ON t.table_schema = c.table_schema AND t.table_name = c.table_name
            WHERE c.table_schema = current_schema() AND t.table_type = 'BASE TABLE'
            """))
    for row in rows:
        out.setdefault(row.table_name, {})[row.column_name] = {
            "nullable": row.is_nullable == "YES",
            "type": row.data_type,
        }
    return out


def _database_foreign_keys(sync_conn: Any) -> dict[tuple[str, str], list[str]]:
    """``{(table, column): [referenced table, ...]}`` from ``pg_constraint``.

    Read from the catalogue rather than the reflection layer so a composite key
    is attributed to each of its columns individually — an attribution column
    that is one member of a wider foreign key is still constrained.
    """
    out: dict[tuple[str, str], list[str]] = {}
    rows = sync_conn.execute(sa.text("""
            SELECT src.relname AS table_name,
                   srcatt.attname AS column_name,
                   tgt.relname AS referenced_table
            FROM pg_constraint AS con
            JOIN pg_class AS src ON src.oid = con.conrelid
            JOIN pg_class AS tgt ON tgt.oid = con.confrelid
            JOIN pg_namespace AS ns ON ns.oid = src.relnamespace
            JOIN unnest(con.conkey) WITH ORDINALITY AS ck(attnum, ord) ON TRUE
            JOIN pg_attribute AS srcatt
              ON srcatt.attrelid = con.conrelid AND srcatt.attnum = ck.attnum
            WHERE con.contype = 'f' AND ns.nspname = current_schema()
            """))
    for row in rows:
        out.setdefault((row.table_name, row.column_name), []).append(row.referenced_table)
    return out


def _orphan_count(sync_conn: Any, table: str, column: str) -> int:
    """Rows whose attribution value names a user that does not exist."""
    return int(
        sync_conn.execute(
            sa.text(
                f'SELECT count(*) FROM "{table}" AS t '  # noqa: S608 - identifiers come from the catalogue
                f'WHERE t."{column}" IS NOT NULL '
                f'AND NOT EXISTS (SELECT 1 FROM "{ATTRIBUTION_TARGET}" AS u WHERE u.id = t."{column}")'
            )
        ).scalar()
    )


def _collect(sync_conn: Any, *, count_orphans: bool) -> dict[str, Any]:
    actual = _database_columns(sync_conn)
    foreign_keys = _database_foreign_keys(sync_conn)
    declared = _declared_columns()
    excluded = alembic_check_excluded_tables()

    absent_columns: list[dict[str, Any]] = []
    absent_on_dropped_tables: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    absent_tables: list[dict[str, Any]] = []

    for table_name, columns in sorted(declared.items()):
        if table_name not in actual:
            absent_tables.append(
                {
                    "table": table_name,
                    "deferred_from_alembic_check": table_name in excluded,
                    "physical_table_dropped": table_name in DROPPED_PHYSICAL_TABLES,
                }
            )
            continue
        for column_name in sorted(columns):
            if column_name in actual[table_name]:
                continue
            finding = {
                "table": table_name,
                "column": column_name,
                "declared_nullable": columns[column_name],
                "deferred_from_alembic_check": table_name in excluded,
            }
            if table_name in DROPPED_PHYSICAL_TABLES:
                absent_on_dropped_tables.append(finding)
            elif (table_name, column_name) in DEFERRED_ABSENT_COLUMNS:
                deferred.append({**finding, "owner": DEFERRED_ABSENT_COLUMNS[(table_name, column_name)]})
            else:
                absent_columns.append(finding)

    # Enumerated from the database, so a table with no model is still counted.
    attribution: list[dict[str, Any]] = []
    for table_name, columns in sorted(actual.items()):
        for column_name in ATTRIBUTION_COLUMNS:
            if column_name not in columns:
                continue
            referenced = foreign_keys.get((table_name, column_name), [])
            entry: dict[str, Any] = {
                "table": table_name,
                "column": column_name,
                "type": columns[column_name]["type"],
                "references": referenced,
                "declared_by_a_model": table_name in declared,
                "deferred_from_alembic_check": table_name in excluded,
            }
            if not referenced and count_orphans:
                entry["orphans"] = _orphan_count(sync_conn, table_name, column_name)
            attribution.append(entry)

    unconstrained = [entry for entry in attribution if not entry["references"]]
    orphaned = [entry for entry in unconstrained if entry.get("orphans")]

    # The direction no model-driven census in this repository can see.
    database_only_columns = [
        {"table": table_name, "column": column_name}
        for table_name, columns in sorted(actual.items())
        if table_name in declared
        for column_name in sorted(columns)
        if column_name not in declared[table_name]
    ]

    return {
        "declared_tables": len(declared),
        "database_tables": len(actual),
        "absent_tables_total": len(absent_tables),
        "absent_tables": absent_tables,
        "absent_columns_total": len(absent_columns),
        "absent_columns": absent_columns,
        "absent_columns_deferred": deferred,
        "absent_columns_on_dropped_tables": absent_on_dropped_tables,
        "attribution_columns_total": len(attribution),
        "attribution_columns_unconstrained_total": len(unconstrained),
        "attribution_tables_unconstrained_total": len({entry["table"] for entry in unconstrained}),
        "attribution_columns_unconstrained": unconstrained,
        "attribution_orphans": orphaned,
        "attribution_orphans_total": sum(entry.get("orphans", 0) for entry in orphaned),
        "database_only_columns_total": len(database_only_columns),
        "database_only_columns": database_only_columns,
    }


async def audit(*, limit: int, count_orphans: bool = True) -> dict[str, Any]:
    async with await open_session() as db:
        payload = await db.run_sync(_collect, count_orphans=count_orphans)

    for key in ("absent_columns", "attribution_columns_unconstrained", "database_only_columns"):
        payload[key] = truncate(payload[key], limit)

    payload["database"] = dsn_label(require_database_url())
    payload["failures"] = payload["absent_columns_total"] + payload["attribution_columns_unconstrained_total"]
    return payload


async def _amain(args: argparse.Namespace) -> int:
    if args.apply:
        print(
            "audit_attribution_schema is read-only; there is no --apply. It reports drift so "
            "a human can decide the repair, and the repair is a migration.",
            file=sys.stderr,
        )
        return 2

    mode = enforce_apply_safety(apply=False, i_understand_prod=False)
    require_database_url()

    payload: dict[str, Any] = {"script": "audit_attribution_schema", "mode": mode}
    payload.update(await audit(limit=args.limit, count_orphans=not args.skip_orphan_counts))
    payload["note"] = (
        "absent_columns is the query-breaking class: a whole-entity ORM load emits every "
        "mapped column, so one absent column makes the whole table unreadable. "
        "attribution_columns_unconstrained is the unenforced-attribution class. "
        "attribution_orphans must be empty before the constraint can be added; a non-zero "
        "count is a data decision for an owner, not something this script repairs. "
        "database_only_columns is reported for information and is not gated."
    )
    emit_report(payload, as_json=args.json)
    return 1 if payload["failures"] else 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    parser.add_argument(
        "--skip-orphan-counts",
        action="store_true",
        default=False,
        help=(
            "Skip the per-column orphan scan. The scan is a sequential count over every "
            "unconstrained attribution column; skip it when the schema census is all that is wanted."
        ),
    )
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
