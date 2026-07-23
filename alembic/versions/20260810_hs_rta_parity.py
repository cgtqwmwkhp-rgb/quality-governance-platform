"""Add H&S parity fields to road traffic collisions.

Revision ID: 20260810_hs_rta_parity
Revises: 20260809_hs_kpi_periods
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_hs_rta_parity"
down_revision: Union[str, Sequence[str], None] = "20260809_hs_kpi_periods"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("road_traffic_collisions", sa.Column("collision_type", sa.String(length=100), nullable=True))
    op.add_column("road_traffic_collisions", sa.Column("vehicle_drivable", sa.Boolean(), nullable=True))
    op.add_column("road_traffic_collisions", sa.Column("is_lti", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("road_traffic_collisions", sa.Column("days_lost", sa.Integer(), nullable=True))
    op.add_column("road_traffic_collisions", sa.Column("is_riddor_reportable", sa.Boolean(), nullable=True))
    op.add_column("road_traffic_collisions", sa.Column("riddor_rationale", sa.Text(), nullable=True))


def downgrade() -> None:
    for column in ("riddor_rationale", "is_riddor_reportable", "days_lost", "is_lti", "vehicle_drivable", "collision_type"):
        op.drop_column("road_traffic_collisions", column)
