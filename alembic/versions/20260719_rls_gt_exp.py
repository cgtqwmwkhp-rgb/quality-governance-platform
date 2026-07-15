"""Expand FORCE RLS + WITH CHECK to golden-thread tables.

Revision ID: 20260719_rls_gt_exp
Revises: 20260718_capa_nm_rta
Create Date: 2026-07-19

WCS GT-UAT D06: ENABLE + FORCE + tenant_isolation (USING + WITH CHECK) on:

- risks_v2 (TEN2-complete, tenant_id NOT NULL via 20260711_rv2_tenant_nn)
- evidence_assets (backfill tenant_id from polymorphic source parent where possible)

evidence_assets NOT NULL is applied only when zero NULL tenant_id rows remain after
parent backfill. Orphan rows without a resolvable parent stay nullable — follow-up
migration required before TEN2 enforcement on evidence_assets.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260719_rls_gt_exp"
down_revision: Union[str, Sequence[str], None] = "20260718_capa_nm_rta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

EXPAND_RLS_TABLES = [
    "risks_v2",
    "evidence_assets",
]

_POLICY_PREDICATE = "tenant_id = current_setting(''app.current_tenant_id'', true)::int"

# Polymorphic source_module → parent table for tenant_id inheritance.
_EVIDENCE_PARENT_BACKFILLS = (
    ("incident", "incidents"),
    ("near_miss", "near_misses"),
    ("road_traffic_collision", "road_traffic_collisions"),
    ("complaint", "complaints"),
    ("investigation", "investigation_runs"),
)


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


def _backfill_evidence_assets_tenant_id() -> None:
    """Inherit tenant_id from linked case/investigation parent rows."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = sa.inspect(bind)
    if not inspector.has_table("evidence_assets"):
        return

    for source_module, parent_table in _EVIDENCE_PARENT_BACKFILLS:
        if not inspector.has_table(parent_table):
            continue
        op.execute(sa.text(f"""
                UPDATE evidence_assets AS ea
                SET tenant_id = parent.tenant_id
                FROM {parent_table} AS parent
                WHERE ea.tenant_id IS NULL
                  AND ea.source_module = :source_module
                  AND ea.source_id = CAST(parent.id AS VARCHAR)
                  AND parent.tenant_id IS NOT NULL
                """).bindparams(source_module=source_module))

    result = bind.execute(sa.text("SELECT COUNT(*) FROM evidence_assets WHERE tenant_id IS NULL"))
    remaining = int(result.scalar() or 0)
    if remaining:
        logger.warning(
            "evidence_assets tenant_id backfill left %s NULL rows; skipping NOT NULL enforcement",
            remaining,
        )
        return

    nullable = True
    for column in inspector.get_columns("evidence_assets"):
        if column["name"] == "tenant_id":
            nullable = bool(column["nullable"])
            break
    if nullable:
        op.alter_column("evidence_assets", "tenant_id", existing_type=sa.Integer(), nullable=False)
        logger.info("evidence_assets.tenant_id set NOT NULL after zero-null backfill")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        logger.info("Skipping RLS GT expand (non-PostgreSQL)")
        return

    _backfill_evidence_assets_tenant_id()

    for table in EXPAND_RLS_TABLES:
        _enable_force_and_policy(table)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        logger.info("Skipping RLS GT expand downgrade (non-PostgreSQL)")
        return

    for table in reversed(EXPAND_RLS_TABLES):
        op.execute(
            f"DO $$ BEGIN "
            f"  EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON {table}'; "
            f"  EXECUTE 'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY'; "
            f"  EXECUTE 'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY'; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'RLS GT expand downgrade skip for {table}: %', SQLERRM; "
            f"END $$"
        )
        logger.info("RLS GT expand downgrade applied (or skipped) for %s", table)
