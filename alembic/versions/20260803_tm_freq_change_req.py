"""Training matrix frequency change requests (dual-control).

Revision ID: 20260803_tm_freq_cr
Revises: 20260802_tm_role
Create Date: 2026-08-03
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_tm_freq_cr"
down_revision: Union[str, Sequence[str], None] = "20260802_tm_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "training_matrix_frequency_change_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("proposed_cells", sa.JSON(), nullable=False),
        sa.Column("cell_count", sa.Integer(), nullable=False),
        sa.Column("proposed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["proposed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tm_freq_cr_tenant_id",
        "training_matrix_frequency_change_requests",
        ["tenant_id"],
    )
    op.create_index(
        "ix_tm_freq_cr_status",
        "training_matrix_frequency_change_requests",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_tm_freq_cr_status", table_name="training_matrix_frequency_change_requests")
    op.drop_index("ix_tm_freq_cr_tenant_id", table_name="training_matrix_frequency_change_requests")
    op.drop_table("training_matrix_frequency_change_requests")
