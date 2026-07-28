#!/usr/bin/env python3
"""Inventory rows whose ``tenant_id`` is NULL, per table (Run025 ops park).

Read-only. Reports, for every table whose SQLAlchemy model declares ``tenant_id``
``nullable=False``, how many rows actually hold NULL, plus a sample of primary
keys and reference numbers so an operator can identify each orphan. Nothing is
written; ``--apply`` is rejected outright, matching
``scripts/ops/run021/inventory_test_debris.py``.

Two things this script refuses to report quietly, because both would otherwise
produce a confidently wrong "0 orphans":

* **Row-level security blindness.** Every case table is under ``FORCE ROW LEVEL
  SECURITY`` with a ``tenant_isolation`` policy comparing ``tenant_id`` against
  ``current_setting('app.current_tenant_id')``. A NULL never satisfies that, and
  FORCE means even the table owner is subject to it, so a role without
  ``rolsuper`` or ``rolbypassrls`` sees *no* rows in those tables at all. Such
  tables are reported as ``rls_blinded``, not as zero.
* **Reading the wrong database.** Counts are meaningless unless you know which
  deployment produced them, so the report always names the host and database,
  with the password stripped.

Exit status is 1 when orphans exist or when any table was hidden by RLS, so this
can gate a runbook step; 0 only when every declared table is genuinely clean.

Usage:
  env -u DATABASE_URL -u PRODDB -u STAGING_DB \\
    DATABASE_URL=postgresql+asyncpg://user@host/db \\
    python -m scripts.ops.run025.inventory_tenant_id_nulls --json
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any, Optional
from urllib.parse import urlsplit

import sqlalchemy as sa

from scripts.ops.run021._common import (
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    open_session,
    require_database_url,
    truncate,
)
from scripts.ops.run025._models import tenant_required_tables

# Columns worth showing so a human can identify a row. Probed against the live
# schema; absent ones are skipped rather than erroring.
IDENTIFYING_COLUMNS: tuple[str, ...] = (
    "reference_number",
    "title",
    "status",
    "created_at",
    "created_by_id",
)


def dsn_label(dsn: str) -> str:
    """Host and database the counts came from, with any password removed.

    Never raises: this string exists to caption a report, and a caption that
    crashes the report is worse than one that says it could not be parsed.
    """
    scheme, separator, rest = dsn.partition("://")
    if not separator or not scheme:
        return "<unparseable dsn>"
    base = scheme.split("+", 1)[0]
    try:
        parts = urlsplit(f"{base}://{rest}")
        host = parts.hostname or "(local socket)"
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return "<unparseable dsn>"
    return f"{base}://{host}{port}{parts.path or ''}"


def _reflect(sync_session: Any, tables: list[str]) -> dict[str, dict[str, Any]]:
    """Reflect column presence and ``tenant_id`` nullability for each table.

    Uses the SQLAlchemy inspector rather than ``information_schema`` so the same
    code path works against SQLite, which is how this is tested.
    """
    inspector = sa.inspect(sync_session.get_bind())
    present = set(inspector.get_table_names())
    out: dict[str, dict[str, Any]] = {}
    for table in tables:
        if table not in present:
            out[table] = {"exists": False}
            continue
        columns = {column["name"]: column for column in inspector.get_columns(table)}
        tenant_column = columns.get("tenant_id")
        out[table] = {
            "exists": True,
            "columns": set(columns),
            "has_tenant_id": tenant_column is not None,
            "nullable": bool(tenant_column["nullable"]) if tenant_column else None,
        }
    return out


def _rls_blinded(sync_session: Any, tables: list[str]) -> set[str]:
    """Target tables whose rows this connection cannot see because of FORCE RLS."""
    bind = sync_session.get_bind()
    if bind.dialect.name != "postgresql":
        return set()

    bypasses = sync_session.execute(
        sa.text("SELECT COALESCE(bool_or(rolsuper OR rolbypassrls), false) FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    if bypasses:
        return set()

    forced = set(
        sync_session.execute(
            sa.text(
                "SELECT c.relname FROM pg_class AS c "
                "JOIN pg_namespace AS n ON n.oid = c.relnamespace "
                "WHERE n.nspname = current_schema() AND c.relforcerowsecurity"
            )
        )
        .scalars()
        .all()
    )
    return forced.intersection(tables)


async def collect(*, tenant_id: Optional[int], limit: int) -> dict[str, Any]:
    """Build the inventory. Performs SELECTs only."""
    declared = tenant_required_tables()

    async with await open_session() as db:
        reflected = await db.run_sync(_reflect, declared)
        blinded = await db.run_sync(_rls_blinded, declared)

        per_table: list[dict[str, Any]] = []
        samples: list[dict[str, Any]] = []
        not_countable: list[str] = []

        for table in declared:
            info = reflected[table]
            if not info["exists"]:
                not_countable.append(f"{table} (table not present in this database)")
                continue
            if not info["has_tenant_id"]:
                # The model declares the column NOT NULL but the physical table
                # has no tenant_id at all: ADD COLUMN drift, not NULL drift.
                not_countable.append(f"{table} (no tenant_id column — ADD COLUMN drift)")
                continue
            if table in blinded:
                per_table.append(
                    {
                        "table": table,
                        "null_tenant_rows": "rls_blinded",
                        "column_nullable": info["nullable"],
                        "note": "FORCE RLS hides every row from this role; no count attempted",
                    }
                )
                continue

            # Table names originate from SQLAlchemy metadata, never from argv.
            null_rows = (await db.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NULL"))).scalar()
            total_rows = (await db.execute(sa.text(f"SELECT COUNT(*) FROM {table}"))).scalar()

            per_table.append(
                {
                    "table": table,
                    "null_tenant_rows": int(null_rows or 0),
                    "total_rows": int(total_rows or 0),
                    "column_nullable": info["nullable"],
                    "schema_drift": info["nullable"] is True,
                }
            )

            if not null_rows:
                continue

            projected = ["id"] + [c for c in IDENTIFYING_COLUMNS if c in info["columns"]]
            sample_sql = sa.text(
                f"SELECT {', '.join(projected)} FROM {table} WHERE tenant_id IS NULL ORDER BY id LIMIT :row_limit"
            )
            for row in (await db.execute(sample_sql, {"row_limit": max(1, limit)})).mappings().all():
                samples.append({"table": table, **{key: row[key] for key in projected}})

    counted = [row for row in per_table if isinstance(row["null_tenant_rows"], int)]
    return {
        "database": dsn_label(require_database_url()),
        "tenant_filter": tenant_id,
        "models_declaring_tenant_id_not_null": len(declared),
        "total_orphan_rows": sum(int(row["null_tenant_rows"]) for row in counted),
        "tables_with_orphan_rows": sorted(row["table"] for row in counted if row["null_tenant_rows"]),
        "tables_where_column_still_nullable": sorted(
            row["table"] for row in per_table if row.get("column_nullable") is True
        ),
        "tables_hidden_by_rls": sorted(blinded),
        "tables_not_countable": not_countable,
        "per_table": per_table,
        "orphan_sample": truncate(samples, limit),
    }


async def _amain(args: argparse.Namespace) -> int:
    if args.apply:
        print(
            "inventory_tenant_id_nulls is read-only by design; there is no --apply. "
            "Deciding which tenant owns an orphaned case is a human judgement backed by "
            "evidence, not a scripted mutation. Use this report, repair the rows "
            "deliberately, then re-run the 20260901_case_tenant_nn migration.",
            file=sys.stderr,
        )
        return 2

    mode = enforce_apply_safety(apply=False, i_understand_prod=False)
    require_database_url()

    payload: dict[str, Any] = {"script": "inventory_tenant_id_nulls", "mode": mode}
    payload.update(await collect(tenant_id=args.tenant_id, limit=args.limit))
    payload["note"] = (
        "No writes performed. 'schema_drift' means the ORM declares tenant_id NOT NULL "
        "but the physical column permits NULL. 'rls_blinded' means this role cannot see "
        "the rows at all — re-run with a role holding rolsuper or rolbypassrls before "
        "trusting a zero."
    )
    emit_report(payload, as_json=args.json)

    return 1 if payload["total_orphan_rows"] or payload["tables_hidden_by_rls"] else 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
