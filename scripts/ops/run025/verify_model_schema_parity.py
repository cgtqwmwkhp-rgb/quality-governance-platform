#!/usr/bin/env python3
"""Assert the declared models match a real database's schema (Run025 ops park).

Read-only. For every column in ``Base.metadata``, check the target database
actually has it and that its nullability agrees with the model. Exit 1 on any
mismatch.

Why this exists, and why ``alembic check`` is not it
---------------------------------------------------
``alembic check`` is the repository's only model-versus-database comparison, and
it cannot catch either of the two drifts found in July 2026:

1. It runs in CI against a Postgres container that was **empty** when the
   migrations ran. The WCS-TEN2 ``tenant_id`` migrations are data-conditional —
   they only ``SET NOT NULL`` when the residual NULL count is zero — so on an
   empty database they always succeed and the CI schema always matches the
   models. The divergence only exists on databases that held orphaned rows at
   migration time, which is to say staging and production, which CI never sees.
2. The job sets ``ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1``, and
   ``alembic/env.py`` uses that to strip ``AlterColumnOp``, ``AddColumnOp`` and
   ``DropColumnOp`` from the comparison. Those are precisely the operations that
   would have reported a nullability mismatch and a missing
   ``legacy_key_risk_indicators`` column.

So the smallest guard that catches this whole class is a parity assertion run
against the database that *has the data* — which needs no write access, no
migration run, and no schema qualification beyond ``information_schema``. That is
this script. Point it at staging and production after every deploy.

Note the deliberate asymmetry with ``alembic check``: this compares only column
presence and nullability, not indexes, foreign keys, types or constraints.
Narrowing the scope is what makes it usable — the unfiltered ``alembic check``
diff on this repository is thousands of operations of long-standing naming and
index noise, which is why the filter was added in the first place. A check that
nobody can read is a check nobody acts on.

Usage:
  env -u DATABASE_URL -u PRODDB -u STAGING_DB \\
    DATABASE_URL=postgresql+asyncpg://user@host/db \\
    python -m scripts.ops.run025.verify_model_schema_parity --json
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


def _model_columns() -> dict[str, dict[str, bool]]:
    """``{table: {column: nullable}}`` for every mapped table."""
    return {
        table_name: {column.name: bool(column.nullable) for column in table.c}
        for table_name, table in load_metadata().tables.items()
    }


def _database_columns(sync_session: Any) -> dict[str, dict[str, bool]]:
    inspector = sa.inspect(sync_session.get_bind())
    out: dict[str, dict[str, bool]] = {}
    for table_name in inspector.get_table_names():
        out[table_name] = {column["name"]: bool(column["nullable"]) for column in inspector.get_columns(table_name)}
    return out


async def compare(*, limit: int, only_columns: Optional[list[str]] = None) -> dict[str, Any]:
    excluded = alembic_check_excluded_tables()
    model = {t: cols for t, cols in _model_columns().items() if t not in excluded}
    if only_columns:
        wanted = set(only_columns)
        model = {
            table: {name: nullable for name, nullable in columns.items() if name in wanted}
            for table, columns in model.items()
        }
        model = {table: columns for table, columns in model.items() if columns}

    async with await open_session() as db:
        actual = await db.run_sync(_database_columns)

    missing_tables: list[str] = []
    missing_columns: list[dict[str, Any]] = []
    nullability_mismatches: list[dict[str, Any]] = []

    for table_name, columns in sorted(model.items()):
        if table_name not in actual:
            missing_tables.append(table_name)
            continue
        for column_name, model_nullable in sorted(columns.items()):
            if column_name not in actual[table_name]:
                missing_columns.append({"table": table_name, "column": column_name})
                continue
            db_nullable = actual[table_name][column_name]
            if db_nullable != model_nullable:
                nullability_mismatches.append(
                    {
                        "table": table_name,
                        "column": column_name,
                        "model": "NULL" if model_nullable else "NOT NULL",
                        "database": "NULL" if db_nullable else "NOT NULL",
                    }
                )

    # A column the model allows to be NULL but the database requires is a
    # different and less urgent failure than the reverse: the database is
    # stricter than the code, so writes fail loudly rather than corrupting.
    model_stricter = [m for m in nullability_mismatches if m["model"] == "NOT NULL"]
    database_stricter = [m for m in nullability_mismatches if m["model"] == "NULL"]

    return {
        "database": dsn_label(require_database_url()),
        "columns_compared": sorted(only_columns) if only_columns else "(all)",
        "tables_compared": len(model),
        "excluded_tables": len(excluded),
        "missing_tables": missing_tables,
        "missing_columns": truncate(missing_columns, limit),
        "missing_columns_total": len(missing_columns),
        "model_requires_not_null_database_allows_null": truncate(model_stricter, limit),
        "model_requires_not_null_database_allows_null_total": len(model_stricter),
        "database_requires_not_null_model_allows_null": truncate(database_stricter, limit),
        "database_requires_not_null_model_allows_null_total": len(database_stricter),
        "failures": len(missing_tables) + len(missing_columns) + len(nullability_mismatches),
    }


async def _amain(args: argparse.Namespace) -> int:
    if args.apply:
        print(
            "verify_model_schema_parity is read-only; there is no --apply. It reports "
            "drift so a human can decide the repair.",
            file=sys.stderr,
        )
        return 2

    mode = enforce_apply_safety(apply=False, i_understand_prod=False)
    require_database_url()

    payload: dict[str, Any] = {"script": "verify_model_schema_parity", "mode": mode}
    payload.update(await compare(limit=args.limit, only_columns=args.column))
    payload["note"] = (
        "Compares column presence and nullability only. 'model requires NOT NULL, "
        "database allows NULL' is the tenant_id class of drift; 'missing columns' is the "
        "legacy_key_risk_indicators class. An unfiltered run on this repository currently "
        "reports several hundred pre-existing nullability mismatches, so gate on "
        "--column tenant_id first and widen as the backlog is retired."
    )
    emit_report(payload, as_json=args.json)
    return 1 if payload["failures"] else 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    parser.add_argument(
        "--column",
        action="append",
        default=None,
        metavar="NAME",
        help=(
            "Restrict the comparison to this column name; repeatable. Omit to compare "
            "every mapped column. Start with --column tenant_id: an unfiltered run "
            "surfaces a large pre-existing backlog that cannot be gated on today."
        ),
    )
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
