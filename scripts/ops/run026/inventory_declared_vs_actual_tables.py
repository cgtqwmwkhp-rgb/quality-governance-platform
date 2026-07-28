#!/usr/bin/env python3
"""Which model-declared tables a real database actually has (Run026 ops park).

Read-only. Asks ``information_schema.tables`` what exists, compares that against
every table in ``Base.metadata``, and reports the ones the models declare but the
database does not carry. Optionally counts rows in the ones it does carry.

Why another parity tool
-----------------------
Three tools in this repository already compare models to schema, and none of them
can report this class of finding:

* ``alembic check`` builds its comparison database by running the migrations
  against an empty Postgres, then strips ``AddColumnOp`` / ``AlterColumnOp`` /
  ``DropColumnOp`` under ``ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1``.
* Both CI harnesses build their schema with ``Base.metadata.create_all``, so a
  table that no migration creates is present in every test database and absent
  from production. A test can therefore pass against a table that does not exist.
* ``scripts/ops/run025/verify_model_schema_parity.py`` does read a real database,
  but it drops ``alembic_check_excluded_tables()`` from the comparison first —
  and that deferral register is precisely the set of tables whose migrations
  never landed. Its ``missing_tables`` key can only ever report a table that
  nobody has already agreed to defer.

So this script deliberately excludes nothing. The deferral register is reported
alongside the finding rather than subtracted from it, because "known" and
"absent" are different facts and only the second one decides whether a user's
page can work.

Why ``information_schema`` rather than the SQLAlchemy inspector
--------------------------------------------------------------
The inspector reads ``pg_catalog`` and applies its own search-path handling. This
question — does the deployment carry this relation — is worth asking in the plain
SQL an operator can paste into ``psql`` next to the script's output and get the
same answer. It also means the query is auditable in a review without knowing
what the inspector does.

Row counts and what they mean
-----------------------------
``--count-rows`` reports ``COUNT(*)`` per present table. A count is only
meaningful if you know which deployment produced it, and an empty table on a
freshly migrated database says nothing at all about the deployment users touch,
so ``--environment-label`` is mandatory and is stamped on every report. A local
throwaway database will report almost everything empty; that is an artefact of
the database, not a finding about the product.

Note that a count read by a role without ``rolsuper`` / ``rolbypassrls`` can be
zero because row-level security hid the rows. Counts are labelled
``rls_forced`` where the table has ``FORCE ROW LEVEL SECURITY`` so a reader does
not mistake invisibility for emptiness.

Usage:
  env -u DATABASE_URL -u PRODDB -u STAGING_DB \\
    DATABASE_URL=postgresql+asyncpg://user@host/db \\
    python -m scripts.ops.run026.inventory_declared_vs_actual_tables \\
      --environment-label staging --count-rows --json
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
)
from scripts.ops.run025._models import alembic_check_excluded_tables, load_metadata
from scripts.ops.run025.inventory_tenant_id_nulls import dsn_label

# Asked of the database rather than inferred. ``BASE TABLE`` excludes views: a
# view named like a model would satisfy a presence check while carrying none of
# the columns the model writes, so counting it as present would be a false
# reassurance.
ACTUAL_TABLES_SQL = sa.text("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = current_schema()
      AND table_type = 'BASE TABLE'
    """)

# ``relforcerowsecurity`` rather than ``relrowsecurity``: a policy that the table
# owner bypasses cannot make a count read zero for the owner, whereas FORCE can.
RLS_FORCED_SQL = sa.text("""
    SELECT c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = current_schema()
      AND c.relforcerowsecurity
    """)


def declared_tables() -> tuple[str, ...]:
    """Every table name in the metadata Alembic itself compares against."""
    return tuple(sorted(load_metadata().tables))


def _actual_tables(sync_conn: Any) -> set[str]:
    return {row[0] for row in sync_conn.execute(ACTUAL_TABLES_SQL)}


def _rls_forced_tables(sync_conn: Any) -> set[str]:
    return {row[0] for row in sync_conn.execute(RLS_FORCED_SQL)}


def _count_rows(sync_conn: Any, tables: tuple[str, ...]) -> dict[str, int]:
    out: dict[str, int] = {}
    for name in tables:
        # Quoted identifier: table names come from information_schema, not from
        # user input, but quoting keeps a table named like a keyword countable.
        out[name] = int(sync_conn.execute(sa.text(f'SELECT count(*) FROM "{name}"')).scalar_one())
    return out


async def inventory(*, environment_label: str, count_rows: bool) -> dict[str, Any]:
    declared = declared_tables()
    deferred = alembic_check_excluded_tables()

    async with await open_session() as db:
        connection = await db.connection()
        actual = await connection.run_sync(_actual_tables)
        rls_forced = await connection.run_sync(_rls_forced_tables)

        absent = tuple(name for name in declared if name not in actual)
        present = tuple(name for name in declared if name in actual)

        counts: dict[str, int] = {}
        if count_rows:
            counts = await connection.run_sync(_count_rows, present)

    payload: dict[str, Any] = {
        "environment_label": environment_label,
        "database": dsn_label(require_database_url()),
        "declared_tables_total": len(declared),
        "actual_tables_total": len(actual),
        "absent_from_database": list(absent),
        "absent_from_database_total": len(absent),
        # Split by whether the absence is already acknowledged. Both halves are
        # unusable in production; the difference is only whether anyone knew.
        "absent_and_on_deferral_register": sorted(name for name in absent if name in deferred),
        "absent_and_undeclared_as_deferred": sorted(name for name in absent if name not in deferred),
        # Tables the database has that no model declares. Not a defect on its
        # own — junction tables and legacy names live here — but it is the other
        # half of the parity picture and cheap to report.
        "in_database_without_a_model": sorted(actual - set(declared)),
    }

    if count_rows:
        empty = sorted(name for name, count in counts.items() if count == 0)
        payload["empty_tables"] = empty
        payload["empty_tables_total"] = len(empty)
        payload["empty_and_rls_forced"] = sorted(name for name in empty if name in rls_forced)
        payload["row_counts"] = dict(sorted(counts.items()))
        payload["counts_caveat"] = (
            f"Row counts describe {environment_label!r} only. An empty table here is not "
            "evidence about any other deployment, and a table listed in "
            "'empty_and_rls_forced' may hold rows this role cannot see."
        )

    return payload


async def _amain(args: argparse.Namespace) -> int:
    if args.apply:
        print(
            "inventory_declared_vs_actual_tables is read-only; there is no --apply. It "
            "reports what a database does and does not carry so a human can decide "
            "whether the surfaces above it should be disclosing unavailability.",
            file=sys.stderr,
        )
        return 2

    mode = enforce_apply_safety(apply=False, i_understand_prod=False)
    require_database_url()

    payload: dict[str, Any] = {"script": "inventory_declared_vs_actual_tables", "mode": mode}
    payload.update(
        await inventory(
            environment_label=args.environment_label,
            count_rows=args.count_rows,
        )
    )
    emit_report(payload, as_json=args.json)
    # Exit 0 even when tables are absent. Absence is the finding this script
    # exists to publish, not a failure of the run, and a non-zero exit would stop
    # a runbook that is only gathering evidence.
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    parser.add_argument(
        "--environment-label",
        required=True,
        metavar="NAME",
        help=(
            "Which deployment this is, e.g. production / staging / "
            "local-alembic-head. Stamped on the report: a finding whose "
            "environment is unknown cannot be acted on and must not be quoted "
            "as a fact about production."
        ),
    )
    parser.add_argument(
        "--count-rows",
        action="store_true",
        default=False,
        help=("Also COUNT(*) every present table. Only meaningful against a " "deployment that real users write to."),
    )
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
