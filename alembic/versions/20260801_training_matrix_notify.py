"""Track last manager email notification per training matrix person.

Revision ID: 20260801_train_notify
Revises: 20260731_train_mtx
Create Date: 2026-08-01
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260801_train_notify"
down_revision: Union[str, Sequence[str], None] = "20260731_train_mtx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "training_matrix_people",
        sa.Column("last_training_notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("training_matrix_people", "last_training_notified_at")
