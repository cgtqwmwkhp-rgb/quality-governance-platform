"""Add soft-delete columns for case registers (PX-177).

Revision ID: 20260904_case_soft_del
Revises: 20260903_push_notif
Create Date: 2026-09-04

Adds ``deleted_at`` + ``deleted_by_id`` to incidents, complaints,
incident_actions, and complaint_actions so TEST-UAT residue and purged
debris can leave the live registers without hard-delete / FK breakage.

Idempotent: skips columns that already exist (create_all / partial adopt).
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260904_case_soft_del"
down_revision: Union[str, None] = "20260903_push_notif"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

TARGET_TABLES: tuple[str, ...] = (
    "incidents",
    "complaints",
    "incident_actions",
    "complaint_actions",
)


def _existing_columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _existing_indexes(table: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table) if idx.get("name")}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    added: list[str] = []
    skipped: list[str] = []

    for table in TARGET_TABLES:
        if not inspector.has_table(table):
            skipped.append(f"{table} (no such table)")
            continue
        present = _existing_columns(table)
        indexes = _existing_indexes(table)

        if "deleted_at" not in present:
            op.add_column(
                table,
                sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            )
            added.append(f"{table}.deleted_at")
        else:
            skipped.append(f"{table}.deleted_at (already present)")

        idx_name = f"ix_{table}_deleted_at"
        # Re-read after possible add; indexes set was captured earlier.
        if "deleted_at" in present or "deleted_at" in _existing_columns(table):
            if idx_name not in indexes and idx_name not in _existing_indexes(table):
                op.create_index(idx_name, table, ["deleted_at"])
                added.append(idx_name)
            else:
                skipped.append(f"{idx_name} (already present)")

        if "deleted_by_id" not in present:
            op.add_column(
                table,
                sa.Column(
                    "deleted_by_id",
                    sa.Integer(),
                    sa.ForeignKey("users.id", name=f"fk_{table}_deleted_by_id"),
                    nullable=True,
                ),
            )
            added.append(f"{table}.deleted_by_id")
        else:
            skipped.append(f"{table}.deleted_by_id (already present)")

    logger.info(
        "%s: added [%s]; skipped [%s].",
        revision,
        ", ".join(added) or "none",
        ", ".join(skipped) or "none",
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in TARGET_TABLES:
        if not inspector.has_table(table):
            continue
        present = _existing_columns(table)
        indexes = _existing_indexes(table)
        idx_name = f"ix_{table}_deleted_at"
        if idx_name in indexes:
            op.drop_index(idx_name, table_name=table)
        if "deleted_by_id" in present:
            op.drop_column(table, "deleted_by_id")
        if "deleted_at" in present:
            op.drop_column(table, "deleted_at")
