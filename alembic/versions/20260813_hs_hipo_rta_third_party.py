"""H&S: NearMiss is_hipo + RTA third_party_injured.

Revision ID: 20260813_hs_hipo_rta
Revises: 20260812_hs_cme
Create Date: 2026-08-13
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_hs_hipo_rta"
down_revision: Union[str, Sequence[str], None] = "20260812_hs_cme"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "near_misses",
        sa.Column("is_hipo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "road_traffic_collisions",
        sa.Column("third_party_injured", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("road_traffic_collisions", "third_party_injured")
    op.drop_column("near_misses", "is_hipo")
