"""Converge case/action ``tenant_id`` to the NOT NULL the ORM has always declared.

Revision ID: 20260901_case_tenant_nn
Revises: 20260831_lookup_enum_align
Create Date: 2026-09-01

Why this exists
---------------
``20260222_add_tenant_columns`` and ``20260308_tenant`` both introduced
``tenant_id`` as ``nullable=True`` across the estate. The July 2026 WCS-TEN2 wave
then tried to tighten each table with a *conditional* migration: backfill from a
parent, count the residual NULLs, and only ``SET NOT NULL`` when that count is
zero (``should_enforce_not_null``). On an empty database the count is always
zero, so CI and every fresh developer database end up matching the ORM. On
staging and production, rows created by tenant-less superuser service accounts
survive the backfill, the count is non-zero, and the wave logs a FAIL-SAFE
warning and leaves the column nullable.

The result is drift that no fresh-database check can see: the ORM declares
``nullable=False``, the physical column permits NULL, and the ``tenant_isolation``
RLS policy (``tenant_id = current_setting('app.current_tenant_id')``) evaluates to
NULL for those rows, so they are invisible to every tenant including their
rightful owner. ``GET /api/v1/rtas/`` reporting a total of 0 while
``RTA-2026-0001`` sits in the table is that, exactly.

What this migration does — and deliberately does not do
-------------------------------------------------------
It is **pure DDL**. It does not backfill, move, delete or re-attribute a single
row, and it never invents a tenant.

There is no defensible way for a migration to decide which client an orphaned
road traffic collision belongs to. The two derivations that are definitionally
sound (child action inherits its parent case; case inherits its creating user)
are already in the chain and have already been exhausted — they are precisely
what failed, because the creator is a tenant-less service account. Everything
else available (``asset_id``, ``reporter_email``, "there is only one active
tenant so it must be that one") is inference, and mis-attributing one client's
collision to another client is worse than an unusable row. Deciding the owner of
a legally significant governance record is a human act with evidence behind it,
not a side effect of ``alembic upgrade head``.

So this migration converges the schema or it refuses. It never leaves a
divergence behind, which is the whole failure of the wave it replaces:

* zero NULLs  -> ``SET NOT NULL`` on every table that is still nullable.
* any NULLs   -> raise :class:`TenantOrphanRowsError` naming each table, its
  count, and the read-only inventory script to run. The transaction rolls back;
  nothing is half-applied.

Applying this to staging or production **will fail today**, by design. Run
``scripts/ops/run025/inventory_tenant_id_nulls.py`` first, decide each orphan's
owner with a human on the record, repair, then re-run.

Reversibility
-------------
Fully reversible. ``downgrade()`` restores ``nullable=True`` on every table this
migration tightened and touches no data, because this migration writes no data.

Row-level security caveat
-------------------------
Every case table and most action tables are under ``FORCE ROW LEVEL SECURITY``.
A connection whose role is neither ``rolsuper`` nor ``rolbypassrls`` sees *no*
rows in them at all — a NULL ``tenant_id`` can never satisfy the policy — so its
``COUNT(*) WHERE tenant_id IS NULL`` returns 0 while ``ALTER TABLE ... SET NOT
NULL`` (which scans the heap and ignores RLS) would still abort. Rather than
trust a count we cannot trust, ``upgrade()`` refuses to run at all on such a
role.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260901_case_tenant_nn"
down_revision: Union[str, Sequence[str], None] = "20260831_lookup_enum_align"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

# Every table whose model declares tenant_id nullable=False and whose only
# tightening migration is data-conditional (so it is nullable on any database
# that held an orphan when the wave ran), plus compliance_evidence_links, which
# no migration has ever tightened and which is therefore nullable everywhere,
# including CI.
#
# Deliberately excluded: document_access_logs and obsolete_document_records.
# Their models declare tenant_id NOT NULL but the physical tables have no
# tenant_id column at all, so the fix there is ADD COLUMN plus a backfill in the
# document-control tenancy area, not an ALTER. See the PR body.
TARGET_TABLES: tuple[str, ...] = (
    # Case registers (all four are under FORCE ROW LEVEL SECURITY).
    "complaints",
    "incidents",
    "near_misses",
    "road_traffic_collisions",
    # Action registers hanging off those cases.
    "capa_actions",
    "complaint_actions",
    "incident_actions",
    "investigation_actions",
    "rta_actions",
    # Same defect class, found during the sweep; nullable on every database.
    "compliance_evidence_links",
)


class TenantOrphanRowsError(RuntimeError):
    """Raised when a target table still holds rows with a NULL ``tenant_id``."""


class TenantScopeInvisibleError(RuntimeError):
    """Raised when row-level security would hide orphan rows from this connection."""


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _present_tables() -> list[str]:
    """Target tables that exist on this database and carry a ``tenant_id``."""
    inspector = _inspector()
    present = []
    for table in TARGET_TABLES:
        if not inspector.has_table(table):
            continue
        if "tenant_id" not in {column["name"] for column in inspector.get_columns(table)}:
            continue
        present.append(table)
    return present


def _tenant_id_is_nullable(table: str) -> bool:
    for column in _inspector().get_columns(table):
        if column["name"] == "tenant_id":
            return bool(column["nullable"])
    raise RuntimeError(f"{table}.tenant_id disappeared between inspections")


def _null_counts(tables: Sequence[str]) -> dict[str, int]:
    # Table names come from TARGET_TABLES, a module-level literal tuple, and are
    # filtered through the inspector before reaching here. No caller input.
    bind = op.get_bind()
    counts: dict[str, int] = {}
    for table in tables:
        result = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NULL"))
        counts[table] = int(result.scalar() or 0)
    return counts


def _assert_orphans_are_visible(tables: Sequence[str]) -> None:
    """Refuse to trust a NULL count that row-level security may have filtered.

    ``FORCE ROW LEVEL SECURITY`` applies the ``tenant_isolation`` policy to the
    table owner as well, and ``tenant_id = current_setting(...)`` is never true
    for a NULL. A role that does not bypass RLS therefore counts zero orphans in
    a table full of them, while ``SET NOT NULL`` still fails. Better to stop with
    an explanation than to act on a number we know is wrong.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    role = bind.execute(sa.text("SELECT current_user")).scalar()
    bypasses = bind.execute(
        sa.text("SELECT COALESCE(bool_or(rolsuper OR rolbypassrls), false) FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    if bypasses:
        return

    # Intersect in Python rather than binding an array parameter, so this does
    # not depend on how the active driver adapts a list into a Postgres array.
    forced_in_schema = set(
        bind.execute(
            sa.text(
                """
                SELECT c.relname
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = current_schema()
                  AND c.relforcerowsecurity
                """
            )
        )
        .scalars()
        .all()
    )
    forced = forced_in_schema.intersection(tables)
    if not forced:
        return

    raise TenantScopeInvisibleError(
        "Refusing to run: this connection cannot see rows with a NULL tenant_id.\n"
        f"  role            : {role}\n"
        f"  FORCE RLS tables: {', '.join(sorted(forced))}\n"
        "The tenant_isolation policy compares tenant_id against "
        "current_setting('app.current_tenant_id'), which is never true for NULL, and "
        "FORCE ROW LEVEL SECURITY applies it to the table owner too. This role would "
        "count zero orphans in a table that has them, and then ALTER TABLE ... SET NOT "
        "NULL would abort anyway because the heap scan ignores RLS.\n"
        "Re-run migrations as a role with rolsuper or rolbypassrls."
    )


def _set_tenant_id_nullable(table: str, *, nullable: bool) -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=nullable)
        return
    op.alter_column(table, "tenant_id", existing_type=sa.Integer(), nullable=nullable)


def upgrade() -> None:
    tables = _present_tables()
    if not tables:
        logger.warning("Skipping %s: none of the target tables carry a tenant_id column.", revision)
        return

    _assert_orphans_are_visible(tables)

    counts = _null_counts(tables)
    orphaned = {table: count for table, count in counts.items() if count}
    if orphaned:
        detail = "\n".join(f"    {table}: {count} row(s)" for table, count in sorted(orphaned.items()))
        raise TenantOrphanRowsError(
            "Refusing to enforce NOT NULL while rows have no tenant.\n"
            f"{detail}\n"
            "These rows are already unreachable through the API: the tenant_isolation RLS "
            "policy cannot match a NULL tenant_id, so they are invisible to every tenant, "
            "and case closure refuses them with TENANT_SCOPE_UNRESOLVED.\n"
            "This migration will not guess an owner. Assigning one client's case to another "
            "client is worse than leaving it unusable.\n"
            "Next steps:\n"
            "  1. env -u DATABASE_URL -u PRODDB -u STAGING_DB DATABASE_URL=<dsn> \\\n"
            "       python -m scripts.ops.run025.inventory_tenant_id_nulls --json\n"
            "  2. Establish each row's rightful tenant from evidence, with a named human on "
            "the record.\n"
            "  3. Repair the rows, then re-run this migration. It is idempotent."
        )

    tightened = [table for table in tables if _tenant_id_is_nullable(table)]
    for table in tightened:
        _set_tenant_id_nullable(table, nullable=False)

    logger.info(
        "%s: tenant_id NOT NULL enforced on %s; already NOT NULL on %s.",
        revision,
        ", ".join(tightened) or "(none)",
        len(tables) - len(tightened),
    )


def downgrade() -> None:
    """Restore ``nullable=True`` on every target table.

    This is deliberately broader than a strict inverse. Alembic carries no record
    of which columns *this* revision tightened, and on a database that ran the
    July wave successfully some targets were already NOT NULL beforehand. Rather
    than guess, downgrade returns all targets to the state the previous revision
    tolerated, which for these tables is "nullable is permitted" — that is
    exactly what the wave's own ``downgrade`` does. Loosening a constraint
    rejects no existing row, so it is safe; the cost is that a downgrade also
    relaxes the two tables (``capa_actions``, ``investigation_actions``) that the
    wave had managed to tighten. Re-running ``upgrade`` restores them.

    No data is touched, because ``upgrade`` writes none.
    """
    for table in _present_tables():
        if not _tenant_id_is_nullable(table):
            _set_tenant_id_nullable(table, nullable=True)
