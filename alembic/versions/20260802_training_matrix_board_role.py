"""Add durable per-person training board role override.

Revision ID: 20260802_tm_role
Revises: 20260801_train_notify
Create Date: 2026-08-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260802_tm_role"
down_revision: Union[str, Sequence[str], None] = "20260801_train_notify"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "ck_training_matrix_people_board_role_override"
_CONSTRAINT_SQL = (
    "board_role_override IS NULL OR board_role_override IN "
    "('Engineer', 'Workshop', 'Office', 'Management')"
)


def upgrade() -> None:
    op.add_column(
        "training_matrix_people",
        sa.Column("board_role_override", sa.String(length=40), nullable=True),
    )
    op.create_check_constraint(_CONSTRAINT, "training_matrix_people", _CONSTRAINT_SQL)


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "training_matrix_people", type_="check")
    op.drop_column("training_matrix_people", "board_role_override")
