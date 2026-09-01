"""PAMS competence snapshot cache (CB-PR1).

Revision ID: 20260901_pams_comp
Revises: 20261118_eng_roster_arch

Read-only mirror of ``vw_plantex_engineercompetence``. Snapshot-swap so a
revoked skill disappears. Pointer flip happens after rows are intact.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260901_pams_comp"
down_revision: Union[str, Sequence[str], None] = "20261118_eng_roster_arch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if not _has_table("pams_competence_snapshots"):
        op.create_table(
            "pams_competence_snapshots",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="loading"),
            sa.Column("source_name", sa.String(length=80), nullable=False),
            sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_pams_competence_snapshots_tenant_id", "pams_competence_snapshots", ["tenant_id"])

    if not _has_table("pams_competence_rows"):
        op.create_table(
            "pams_competence_rows",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("snapshot_id", sa.Integer(), nullable=False),
            sa.Column("pams_technician_id", sa.Integer(), nullable=True),
            sa.Column("engineer_id", sa.Integer(), nullable=True),
            sa.Column("engineer_name", sa.String(length=255), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("depot", sa.String(length=32), nullable=True),
            sa.Column("characteristic_key", sa.String(length=80), nullable=False),
            sa.Column("thorough_exam", sa.Boolean(), nullable=True),
            sa.Column("raw_data", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(
                ["snapshot_id"],
                ["pams_competence_snapshots.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_pams_competence_rows_snapshot_id", "pams_competence_rows", ["snapshot_id"])
        op.create_index(
            "ix_pams_competence_rows_pams_technician_id",
            "pams_competence_rows",
            ["pams_technician_id"],
        )
        op.create_index("ix_pams_competence_rows_engineer_id", "pams_competence_rows", ["engineer_id"])
        op.create_index(
            "ix_pams_competence_rows_characteristic_key",
            "pams_competence_rows",
            ["characteristic_key"],
        )

    if not _has_table("pams_competence_current"):
        op.create_table(
            "pams_competence_current",
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("snapshot_id", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["snapshot_id"],
                ["pams_competence_snapshots.id"],
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("tenant_id"),
        )


def downgrade() -> None:
    if _has_table("pams_competence_current"):
        op.drop_table("pams_competence_current")
    if _has_table("pams_competence_rows"):
        op.drop_table("pams_competence_rows")
    if _has_table("pams_competence_snapshots"):
        op.drop_table("pams_competence_snapshots")
