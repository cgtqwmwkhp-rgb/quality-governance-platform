"""H&S: lessons_learnt on Incident, NearMiss, RTA, Complaint.

Revision ID: 20260814_hs_lessons
Revises: 20260813_hs_hipo_rta
Create Date: 2026-08-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_hs_lessons"
down_revision: Union[str, Sequence[str], None] = "20260813_hs_hipo_rta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("incidents", sa.Column("lessons_learnt", sa.Text(), nullable=True))
    op.add_column("near_misses", sa.Column("lessons_learnt", sa.Text(), nullable=True))
    op.add_column("road_traffic_collisions", sa.Column("lessons_learnt", sa.Text(), nullable=True))
    op.add_column("complaints", sa.Column("lessons_learnt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("complaints", "lessons_learnt")
    op.drop_column("road_traffic_collisions", "lessons_learnt")
    op.drop_column("near_misses", "lessons_learnt")
    op.drop_column("incidents", "lessons_learnt")
