"""Expand FORCE RLS + WITH CHECK to three TEN2-complete action tables.

Revision ID: 20260711_rls_act_exp
Revises: 20260711_rls_wc_exp
Create Date: 2026-07-11

WCS DB-01 (phased expand): ENABLE + FORCE + tenant_isolation (USING + WITH CHECK)
on three owned action child tables that are already TEN2-complete
(nullable=False) and whose parents already have RLS:

- incident_actions
- complaint_actions
- rta_actions

App must continue to set ``app.current_tenant_id`` via TenantContextMiddleware /
``apply_tenant_guc``. Unset GUC fails closed. Admin/migration uses BYPASSRLS
(``qgp_migrations``).
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

from alembic import op

revision: str = "20260711_rls_act_exp"
down_revision: Union[str, Sequence[str], None] = "20260711_rls_wc_exp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

# TEN2-complete owned action tables — second expansion beyond WC-EXP.
EXPAND_RLS_TABLES = [
    "incident_actions",
    "complaint_actions",
    "rta_actions",
]

_POLICY_PREDICATE = "tenant_id = current_setting(''app.current_tenant_id'', true)::int"


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
        logger.info("Skipping RLS action expand (non-PostgreSQL)")
        return

    for table in EXPAND_RLS_TABLES:
        _enable_force_and_policy(table)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        logger.info("Skipping RLS action expand downgrade (non-PostgreSQL)")
        return

    for table in reversed(EXPAND_RLS_TABLES):
        op.execute(
            f"DO $$ BEGIN "
            f"  EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON {table}'; "
            f"  EXECUTE 'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY'; "
            f"  EXECUTE 'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY'; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'RLS action expand downgrade skip for {table}: %', SQLERRM; "
            f"END $$"
        )
        logger.info("RLS action expand downgrade applied (or skipped) for %s", table)
