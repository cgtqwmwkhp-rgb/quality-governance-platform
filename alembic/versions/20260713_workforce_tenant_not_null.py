"""Fail-safe tenant_id NOT NULL for workforce spine tables.

Revision ID: 20260713_wf_tenant_nn
Revises: 20260713_wf_p0_spine
Create Date: 2026-07-13

Tables: engineers, competency_records, competency_requirements.

Backfill policy (never invent tenant_id=1):
- engineers ← users.tenant_id via engineers.user_id
- competency_records ← engineers.tenant_id via engineer_id
- competency_requirements ← no reliable parent; leave NULL if unset

Fail-safe: only SET NOT NULL when remaining NULL count is zero per table.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_wf_tenant_nn"
down_revision: Union[str, Sequence[str], None] = "20260713_wf_p0_spine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

TABLES = ("engineers", "competency_records", "competency_requirements")


def should_enforce_not_null(remaining_null_count: int) -> bool:
    """Return True only when every row has a tenant_id."""
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


def _count_null_tenant_ids(table_name: str) -> int:
    bind = op.get_bind()
    result = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table_name} WHERE tenant_id IS NULL"))
    return int(result.scalar() or 0)


def _set_tenant_id_nullable(table_name: str, nullable: bool) -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                "tenant_id",
                existing_type=sa.Integer(),
                nullable=nullable,
            )
    else:
        op.alter_column(
            table_name,
            "tenant_id",
            existing_type=sa.Integer(),
            nullable=nullable,
        )


def _backfill_engineers_from_users() -> None:
    if not _table_exists("engineers") or not _table_exists("users"):
        return
    if not _has_column("engineers", "user_id") or not _has_column("users", "tenant_id"):
        return
    op.execute(
        sa.text(
            """
            UPDATE engineers
            SET tenant_id = (
                SELECT users.tenant_id
                FROM users
                WHERE users.id = engineers.user_id
            )
            WHERE tenant_id IS NULL
              AND EXISTS (
                SELECT 1 FROM users
                WHERE users.id = engineers.user_id
                  AND users.tenant_id IS NOT NULL
              )
            """
        )
    )


def _backfill_competency_records_from_engineers() -> None:
    if not _table_exists("competency_records") or not _table_exists("engineers"):
        return
    op.execute(
        sa.text(
            """
            UPDATE competency_records
            SET tenant_id = (
                SELECT engineers.tenant_id
                FROM engineers
                WHERE engineers.id = competency_records.engineer_id
            )
            WHERE tenant_id IS NULL
              AND EXISTS (
                SELECT 1 FROM engineers
                WHERE engineers.id = competency_records.engineer_id
                  AND engineers.tenant_id IS NOT NULL
              )
            """
        )
    )


def _enforce_table(table_name: str) -> None:
    if not _table_exists(table_name) or not _has_column(table_name, "tenant_id"):
        msg = f"Skipping {table_name}: tenant_id missing"
        logger.warning(msg)
        print(msg)
        return

    remaining = _count_null_tenant_ids(table_name)
    if should_enforce_not_null(remaining):
        current_nullable = _column_nullable(table_name, "tenant_id")
        if current_nullable is False:
            msg = f"{table_name}.tenant_id already NOT NULL; nothing to alter."
            logger.info(msg)
            print(msg)
            return
        _set_tenant_id_nullable(table_name, False)
        msg = f"Enforced NOT NULL on {table_name}.tenant_id (remaining nulls=0)."
        logger.info(msg)
        print(msg)
        return

    msg = (
        f"FAIL-SAFE: leaving {table_name}.tenant_id nullable — "
        f"{remaining} row(s) still have tenant_id IS NULL after backfill. "
        "Do not invent tenant_id=1."
    )
    logger.warning(msg)
    print(msg)


def upgrade() -> None:
    _backfill_engineers_from_users()
    _backfill_competency_records_from_engineers()
    # competency_requirements: no invent; enforce only when already fully attributed
    for table_name in TABLES:
        _enforce_table(table_name)


def downgrade() -> None:
    for table_name in TABLES:
        if not _table_exists(table_name) or not _has_column(table_name, "tenant_id"):
            continue
        if _column_nullable(table_name, "tenant_id") is False:
            _set_tenant_id_nullable(table_name, True)
