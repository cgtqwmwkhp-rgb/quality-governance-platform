"""Add WITH CHECK to existing RLS policies + expand FORCE RLS to 3 owned tables.

Revision ID: 20260711_rls_wc_exp
Revises: 20260711_dann_tenant_nn
Create Date: 2026-07-11

WCS DB-02 / DB-01 (phased):
1. Rewrite ``tenant_isolation`` on the original 12 RLS tables so writes are
   gated with ``WITH CHECK`` matching the existing ``USING`` predicate.
2. ENABLE + FORCE + policy (USING + WITH CHECK) on three TEN2-complete owned
   tables that previously had app-filter only: policies, audit_findings,
   investigation_actions.

App must continue to set ``app.current_tenant_id`` via TenantContextMiddleware /
``apply_tenant_guc``. Unset GUC fails closed. Admin/migration uses BYPASSRLS
(``qgp_migrations``).
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

from alembic import op

revision: str = "20260711_rls_wc_exp"
down_revision: Union[str, Sequence[str], None] = "20260711_dann_tenant_nn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

# Original 20260222 / 20260710 FORCE set — policies exist; add WITH CHECK.
EXISTING_RLS_TABLES = [
    "incidents",
    "complaints",
    "risks",
    "capa_actions",
    "audit_runs",
    "investigation_runs",
    "documents",
    "near_misses",
    "road_traffic_collisions",
    "workflow_rules",
    "users",
    "audit_log_entries",
]

# TEN2-complete owned tables — first expansion beyond the original 12.
EXPAND_RLS_TABLES = [
    "policies",
    "audit_findings",
    "investigation_actions",
]

_POLICY_PREDICATE = "tenant_id = current_setting(''app.current_tenant_id'', true)::int"


def _recreate_tenant_isolation_with_check(table: str) -> None:
    """Drop and recreate tenant_isolation with USING + WITH CHECK (PG only)."""
    op.execute(
        f"DO $$ BEGIN "
        f"  IF EXISTS ("
        f"    SELECT 1 FROM information_schema.columns "
        f"    WHERE table_schema = 'public' AND table_name = '{table}' "
        f"      AND column_name = 'tenant_id'"
        f"  ) THEN "
        f"    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON {table}'; "
        f"    EXECUTE 'CREATE POLICY tenant_isolation ON {table} "
        f"      USING ({_POLICY_PREDICATE}) "
        f"      WITH CHECK ({_POLICY_PREDICATE})'; "
        f"    RAISE NOTICE 'RLS WITH CHECK applied on {table}'; "
        f"  ELSE "
        f"    RAISE NOTICE 'RLS WITH CHECK skip missing tenant_id on {table}'; "
        f"  END IF; "
        f"EXCEPTION WHEN OTHERS THEN "
        f"  RAISE NOTICE 'RLS WITH CHECK skip for {table}: %', SQLERRM; "
        f"END $$"
    )
    logger.info("RLS WITH CHECK applied (or skipped) for %s", table)


def _enable_force_and_policy(table: str) -> None:
    """ENABLE + FORCE RLS and create tenant_isolation WITH CHECK."""
    op.execute(
        f"DO $$ BEGIN "
        f"  IF EXISTS ("
        f"    SELECT 1 FROM information_schema.columns "
        f"    WHERE table_schema = 'public' AND table_name = '{table}' "
        f"      AND column_name = 'tenant_id'"
        f"  ) THEN "
        f"    EXECUTE 'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'; "
        f"    EXECUTE 'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'; "
        f"    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON {table}'; "
        f"    EXECUTE 'CREATE POLICY tenant_isolation ON {table} "
        f"      USING ({_POLICY_PREDICATE}) "
        f"      WITH CHECK ({_POLICY_PREDICATE})'; "
        f"    RAISE NOTICE 'FORCE RLS + WITH CHECK enabled on {table}'; "
        f"  ELSE "
        f"    RAISE NOTICE 'FORCE RLS expand skip missing tenant_id on {table}'; "
        f"  END IF; "
        f"EXCEPTION WHEN OTHERS THEN "
        f"  RAISE NOTICE 'FORCE RLS expand skip for {table}: %', SQLERRM; "
        f"END $$"
    )
    logger.info("FORCE RLS expand applied (or skipped) for %s", table)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        logger.info("Skipping RLS WITH CHECK expand (non-PostgreSQL)")
        return

    for table in EXISTING_RLS_TABLES:
        _recreate_tenant_isolation_with_check(table)

    for table in EXPAND_RLS_TABLES:
        _enable_force_and_policy(table)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        logger.info("Skipping RLS WITH CHECK expand downgrade (non-PostgreSQL)")
        return

    # Remove expansion tables entirely (policy + FORCE + ENABLE).
    for table in reversed(EXPAND_RLS_TABLES):
        op.execute(
            f"DO $$ BEGIN "
            f"  EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON {table}'; "
            f"  EXECUTE 'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY'; "
            f"  EXECUTE 'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY'; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'RLS expand downgrade skip for {table}: %', SQLERRM; "
            f"END $$"
        )
        logger.info("RLS expand downgrade applied (or skipped) for %s", table)

    # Restore USING-only policies on the original 12 (pre-WITH CHECK shape).
    using_only = "tenant_id = current_setting(''app.current_tenant_id'', true)::int"
    for table in reversed(EXISTING_RLS_TABLES):
        op.execute(
            f"DO $$ BEGIN "
            f"  IF EXISTS ("
            f"    SELECT 1 FROM information_schema.columns "
            f"    WHERE table_schema = 'public' AND table_name = '{table}' "
            f"      AND column_name = 'tenant_id'"
            f"  ) THEN "
            f"    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON {table}'; "
            f"    EXECUTE 'CREATE POLICY tenant_isolation ON {table} "
            f"      USING ({using_only})'; "
            f"  END IF; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'RLS WITH CHECK downgrade skip for {table}: %', SQLERRM; "
            f"END $$"
        )
        logger.info("RLS WITH CHECK downgrade applied (or skipped) for %s", table)
