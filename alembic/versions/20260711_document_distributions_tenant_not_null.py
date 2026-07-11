"""Fail-safe backfill + conditional NOT NULL for document_distributions.tenant_id.

Revision ID: 20260711_ddist_tenant_nn
Revises: 20260711_dal_tenant_nn
Create Date: 2026-07-11

Inherit from controlled_documents via document_id. Never invent tenant_id=1.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260711_ddist_tenant_nn"
down_revision: Union[str, Sequence[str], None] = "20260711_dal_tenant_nn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

TABLE = "document_distributions"
PARENT = "controlled_documents"
PARENT_KEY = "document_id"


def should_enforce_not_null(remaining_null_count: int) -> bool:
    return remaining_null_count == 0


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in _inspector().get_columns(table_name)}


def _column_nullable(table_name: str, column_name: str) -> bool | None:
    for column in _inspector().get_columns(table_name):
        if column["name"] == column_name:
            return bool(column["nullable"])
    return None


def _count_null_tenant_ids() -> int:
    bind = op.get_bind()
    result = bind.execute(sa.text(f"SELECT COUNT(*) FROM {TABLE} WHERE tenant_id IS NULL"))
    return int(result.scalar() or 0)


def _backfill_from_parent() -> None:
    op.execute(
        sa.text(
            f"""
            UPDATE {TABLE}
            SET tenant_id = (
                SELECT parent.tenant_id
                FROM {PARENT} AS parent
                WHERE parent.id = {TABLE}.{PARENT_KEY}
            )
            WHERE tenant_id IS NULL
              AND EXISTS (
                SELECT 1 FROM {PARENT} AS parent
                WHERE parent.id = {TABLE}.{PARENT_KEY}
                  AND parent.tenant_id IS NOT NULL
              )
            """
        )
    )


def _align_mismatches_to_parent() -> None:
    op.execute(
        sa.text(
            f"""
            UPDATE {TABLE}
            SET tenant_id = (
                SELECT parent.tenant_id
                FROM {PARENT} AS parent
                WHERE parent.id = {TABLE}.{PARENT_KEY}
            )
            WHERE EXISTS (
                SELECT 1 FROM {PARENT} AS parent
                WHERE parent.id = {TABLE}.{PARENT_KEY}
                  AND parent.tenant_id IS NOT NULL
                  AND {TABLE}.tenant_id IS DISTINCT FROM parent.tenant_id
            )
            """
        )
    )


def _set_tenant_id_nullable(nullable: bool) -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=nullable)
    else:
        op.alter_column(TABLE, "tenant_id", existing_type=sa.Integer(), nullable=nullable)


def upgrade() -> None:
    if not _table_exists(TABLE) or not _has_column(TABLE, "tenant_id"):
        msg = f"Skipping {revision}: {TABLE}.tenant_id missing."
        logger.warning(msg); print(msg); return
    if _table_exists(PARENT) and _has_column(PARENT, "tenant_id"):
        _backfill_from_parent(); _align_mismatches_to_parent()
    remaining = _count_null_tenant_ids()
    if should_enforce_not_null(remaining):
        if _column_nullable(TABLE, "tenant_id") is False:
            msg = f"{TABLE}.tenant_id already NOT NULL; nothing to alter."
            logger.info(msg); print(msg); return
        _set_tenant_id_nullable(False)
        msg = f"Enforced NOT NULL on {TABLE}.tenant_id (remaining nulls=0)."
        logger.info(msg); print(msg); return
    msg = (
        f"FAIL-SAFE: leaving {TABLE}.tenant_id nullable — {remaining} row(s) still NULL "
        "after parent backfill; do not invent tenant_id=1."
    )
    logger.warning(msg); print(msg)


def downgrade() -> None:
    if not _table_exists(TABLE) or not _has_column(TABLE, "tenant_id"):
        return
    if _column_nullable(TABLE, "tenant_id") is False:
        _set_tenant_id_nullable(True)
