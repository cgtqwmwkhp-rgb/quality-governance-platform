"""Add incident injury classification columns for H&S Excel parity.

Revision ID: 20260808_hs_injury
Revises: 20260807_ces_loc_brand
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260808_hs_injury"
down_revision: Union[str, Sequence[str], None] = "20260807_ces_loc_brand"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("is_injury", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "incidents",
        sa.Column("body_parts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("is_lti", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "incidents",
        sa.Column("days_lost", sa.Integer(), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("is_minor_injury", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("incidents", "is_minor_injury")
    op.drop_column("incidents", "days_lost")
    op.drop_column("incidents", "is_lti")
    op.drop_column("incidents", "body_parts")
    op.drop_column("incidents", "is_injury")
