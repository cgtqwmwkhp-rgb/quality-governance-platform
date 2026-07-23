"""Add manual annual hours override for H&S reporting periods.

Revision ID: 20260811_hs_manual_hours
Revises: 20260810_hs_rta_parity
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_hs_manual_hours"
down_revision: Union[str, Sequence[str], None] = "20260810_hs_rta_parity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hs_reporting_periods",
        sa.Column("manual_hours", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("hs_reporting_periods", "manual_hours")
