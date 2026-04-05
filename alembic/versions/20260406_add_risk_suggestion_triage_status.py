"""Add suggestion_triage_status for import-sourced enterprise risks.

Revision ID: b1c2d3e4f5a6
Revises: a8b9c0d1e2f3
Create Date: 2026-04-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "risks_v2",
        sa.Column("suggestion_triage_status", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_risks_v2_suggestion_triage_status",
        "risks_v2",
        ["suggestion_triage_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_risks_v2_suggestion_triage_status", table_name="risks_v2")
    op.drop_column("risks_v2", "suggestion_triage_status")
