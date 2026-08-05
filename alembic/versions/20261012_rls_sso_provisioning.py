"""ENABLE + FORCE tenant_isolation on sso_provisioning_requests.

Revision ID: 20261012_rls_sso_prov
Revises: 20261012_sso_prov_req
Create Date: 2026-10-12

Why this is a separate revision from the table create
-----------------------------------------------------
``20260902_rls_guc_guard`` names the tables that existed at that revision and
cannot be edited to protect tables that land later. Every table created after
it has to be brought under the hardened predicate by a revision that still
runs, and registered in ``HARDENING_MIGRATIONS`` in
``tests/unit/test_run026_rls_least_privilege.py``. Splitting create from RLS
keeps the additive schema deployable alone and mirrors the constraint that
revision must declare ``ADOPT_TABLES``, a verbatim ``HARDENED_PREDICATE``,
ENABLE + FORCE, USING *and* WITH CHECK, and a ``pg_policy`` re-read that
raises rather than reporting a success it did not achieve.

The policy is inert while the application connects as a ``rolbypassrls`` role
(CUT-6 cutover). The table is correct in advance rather than added to CUT-4's
backlog.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261012_rls_sso_prov"
down_revision: Union[str, Sequence[str], None] = "20261012_sso_prov_req"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

# Kept as a literal rather than imported from
# src.infrastructure.middleware.tenant_context.TENANT_ISOLATION_PREDICATE, for the
# same reason 20260902_rls_guc_guard / 20260913_cs_wave0 keep their own copy: a
# migration must describe the database as it was at this revision and must not
# change meaning when application code is edited later. A unit test asserts the
# two stay identical.
HARDENED_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::int"

# Named to match the ADOPT_TABLES vocabulary of 20260902_rls_guc_guard, which is
# the constant the coverage registry in tests/unit/test_run026_rls_least_privilege.py
# reads.
ADOPT_TABLES: tuple[str, ...] = ("sso_provisioning_requests",)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _enable_rls(table: str) -> None:
    """ENABLE + FORCE row-level security on ``table`` and install the policy.

    ENABLE alone exempts the table owner, which is every identity the migrations
    run as, so FORCE is what makes the policy bind. WITH CHECK carries the same
    predicate as USING so a write cannot land in a tenant the caller is not
    serving; a policy with only USING filters reads and permits any INSERT.
    """
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({HARDENED_PREDICATE}) WITH CHECK ({HARDENED_PREDICATE})"
        )
    )


def _assert_policies_match(tables: Sequence[str], expected_fragment: str) -> None:
    """Re-read pg_policy and raise unless every table really carries the predicate.

    ``expected_fragment`` is matched against the normalised expression PostgreSQL
    stores, not against the SQL sent above, so a statement that parsed without
    taking effect cannot satisfy this.
    """
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("""
            SELECT c.relname AS table_name,
                   c.relrowsecurity AS enabled,
                   c.relforcerowsecurity AS forced,
                   pg_get_expr(p.polqual, p.polrelid) AS using_expr,
                   pg_get_expr(p.polwithcheck, p.polrelid) AS check_expr
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            LEFT JOIN pg_policy AS p ON p.polrelid = c.oid AND p.polname = 'tenant_isolation'
            WHERE n.nspname = current_schema() AND c.relname = ANY(:tables)
            """),
        {"tables": list(tables)},
    ).mappings()
    state = {row["table_name"]: row for row in rows}

    problems: list[str] = []
    for table in tables:
        row = state.get(table)
        if row is None:
            problems.append(f"{table}: relation not visible in current_schema()")
            continue
        if not row["enabled"] or not row["forced"]:
            problems.append(f"{table}: enabled={row['enabled']} forced={row['forced']} (both must be true)")
        for label in ("using_expr", "check_expr"):
            expr = row[label]
            if expr is None:
                problems.append(f"{table}: tenant_isolation has no {label}")
            elif expected_fragment not in expr:
                problems.append(f"{table}: {label} is {expr!r}, expected it to contain {expected_fragment!r}")

    if problems:
        raise RuntimeError(
            f"{revision} did not achieve the policy state it reported. "
            "Refusing to record this revision as applied.\n  " + "\n  ".join(problems)
        )


def upgrade() -> None:
    protected = [table for table in ADOPT_TABLES if _table_exists(table)]
    for table in protected:
        _enable_rls(table)

    if protected and op.get_bind().dialect.name == "postgresql":
        _assert_policies_match(protected, "NULLIF")
        logger.info("%s: tenant_isolation enabled and forced on %s", revision, ", ".join(protected))
    elif not protected:
        logger.warning("%s: ADOPT_TABLES missing at upgrade time — nothing hardened", revision)


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    for table in reversed(ADOPT_TABLES):
        if _table_exists(table):
            op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
            op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
            op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
