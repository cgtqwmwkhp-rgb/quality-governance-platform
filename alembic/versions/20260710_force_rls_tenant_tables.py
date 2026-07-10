"""FORCE ROW LEVEL SECURITY on existing tenant-policy tables.

Revision ID: 20260710_force_rls
Revises: 20260710_inv_rev_evt_nn
Create Date: 2026-07-10

L2-F02: Tables already have ENABLE RLS + tenant_isolation policies from
20260222_add_row_level_security. FORCE RLS ensures even the table owner is
subject to policies unless the role has BYPASSRLS (e.g. qgp_migrations).

App connections must set ``app.current_tenant_id`` via set_config / SET LOCAL
on the request session; unset GUC fails closed (no rows match).
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

from alembic import op

revision: str = "20260710_force_rls"
down_revision: Union[str, Sequence[str], None] = "20260710_inv_rev_evt_nn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

RLS_TABLES = [
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


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        logger.info("Skipping FORCE RLS (non-PostgreSQL)")
        return

    for table in RLS_TABLES:
        op.execute(
            f"DO $$ BEGIN "
            f"  IF EXISTS ("
            f"    SELECT 1 FROM information_schema.tables "
            f"    WHERE table_schema = 'public' AND table_name = '{table}'"
            f"  ) THEN "
            f"    EXECUTE 'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'; "
            f"    RAISE NOTICE 'FORCE RLS enabled on {table}'; "
            f"  ELSE "
            f"    RAISE NOTICE 'FORCE RLS skip missing table {table}'; "
            f"  END IF; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'FORCE RLS skip for {table}: %', SQLERRM; "
            f"END $$"
        )
        logger.info("FORCE RLS applied (or skipped) for %s", table)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        logger.info("Skipping NO FORCE RLS (non-PostgreSQL)")
        return

    for table in reversed(RLS_TABLES):
        op.execute(
            f"DO $$ BEGIN "
            f"  IF EXISTS ("
            f"    SELECT 1 FROM information_schema.tables "
            f"    WHERE table_schema = 'public' AND table_name = '{table}'"
            f"  ) THEN "
            f"    EXECUTE 'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY'; "
            f"  END IF; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'NO FORCE RLS skip for {table}: %', SQLERRM; "
            f"END $$"
        )
        logger.info("NO FORCE RLS applied (or skipped) for %s", table)
