"""Fail-safe expanded backfill + conditional NOT NULL for evidence_assets.tenant_id.

Revision ID: 20260720_ea_tenant_nn
Revises: 20260719_case_risk_jn
Create Date: 2026-07-20

GT-UAT R62 follow-up after 20260719_rls_gt_exp:
- Expand polymorphic parent backfill (audit/asset/certificate/assessment/induction)
- Secondary attribution via created_by_id → users.tenant_id
- Never invent tenant_id=1
- SET NOT NULL only when remaining NULL count is zero
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_ea_tenant_nn"
down_revision: Union[str, Sequence[str], None] = "20260719_case_risk_jn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

TABLE = "evidence_assets"

# Polymorphic source_module → parent table for tenant_id inheritance.
_EVIDENCE_PARENT_BACKFILLS = (
    ("incident", "incidents"),
    ("near_miss", "near_misses"),
    ("road_traffic_collision", "road_traffic_collisions"),
    ("complaint", "complaints"),
    ("investigation", "investigation_runs"),
    ("audit", "audit_runs"),
    ("asset", "assets"),
    ("certificate", "certificates"),
    ("assessment", "assessment_runs"),
    ("induction", "induction_runs"),
)


def should_enforce_not_null(remaining_null_count: int) -> bool:
    """Return True only when every evidence_assets row has a tenant_id."""
    return remaining_null_count == 0


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _count_null_tenant_ids() -> int:
    bind = op.get_bind()
    result = bind.execute(sa.text(f"SELECT COUNT(*) FROM {TABLE} WHERE tenant_id IS NULL"))
    return int(result.scalar() or 0)


def _backfill_from_source_parents() -> None:
    bind = op.get_bind()
    inspector = _inspector()
    if not inspector.has_table(TABLE):
        return

    for source_module, parent_table in _EVIDENCE_PARENT_BACKFILLS:
        if not inspector.has_table(parent_table):
            continue
        if "tenant_id" not in {c["name"] for c in inspector.get_columns(parent_table)}:
            continue
        op.execute(sa.text(f"""
                UPDATE {TABLE} AS ea
                SET tenant_id = parent.tenant_id
                FROM {parent_table} AS parent
                WHERE ea.tenant_id IS NULL
                  AND ea.source_module = :source_module
                  AND ea.source_id = CAST(parent.id AS VARCHAR)
                  AND parent.tenant_id IS NOT NULL
                """).bindparams(source_module=source_module))


def _backfill_from_creator_user() -> None:
    """Secondary attribution: inherit tenant from creating user."""
    inspector = _inspector()
    if not inspector.has_table(TABLE) or not inspector.has_table("users"):
        return
    cols = {c["name"] for c in inspector.get_columns(TABLE)}
    if "created_by_id" not in cols:
        return
    op.execute(sa.text(f"""
            UPDATE {TABLE}
            SET tenant_id = (
                SELECT parent.tenant_id
                FROM users AS parent
                WHERE parent.id = {TABLE}.created_by_id
            )
            WHERE tenant_id IS NULL
              AND EXISTS (
                SELECT 1
                FROM users AS parent
                WHERE parent.id = {TABLE}.created_by_id
                  AND parent.tenant_id IS NOT NULL
              )
            """))


def _set_tenant_id_nullable(nullable: bool) -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.alter_column(
                "tenant_id",
                existing_type=sa.Integer(),
                nullable=nullable,
            )
        return
    op.alter_column(TABLE, "tenant_id", existing_type=sa.Integer(), nullable=nullable)


def upgrade() -> None:
    bind = op.get_bind()
    if not _inspector().has_table(TABLE):
        logger.info("%s missing; skip ea_tenant_nn", TABLE)
        return

    _backfill_from_source_parents()
    _backfill_from_creator_user()

    remaining = _count_null_tenant_ids()
    if not should_enforce_not_null(remaining):
        logger.warning(
            "FAIL-SAFE: leaving %s.tenant_id nullable — remaining nulls=%s " "(never invent tenant_id=1)",
            TABLE,
            remaining,
        )
        return

    nullable = True
    for column in _inspector().get_columns(TABLE):
        if column["name"] == "tenant_id":
            nullable = bool(column["nullable"])
            break
    if nullable:
        _set_tenant_id_nullable(False)
        logger.info("Enforced NOT NULL on %s.tenant_id (remaining nulls=0).", TABLE)
    else:
        logger.info("%s.tenant_id already NOT NULL; nothing to alter.", TABLE)


def downgrade() -> None:
    if not _inspector().has_table(TABLE):
        return
    nullable = None
    for column in _inspector().get_columns(TABLE):
        if column["name"] == "tenant_id":
            nullable = bool(column["nullable"])
            break
    if nullable is False:
        _set_tenant_id_nullable(True)
        logger.info("Restored nullable on %s.tenant_id", TABLE)
