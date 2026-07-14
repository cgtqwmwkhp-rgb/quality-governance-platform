"""Add nullable owner_id to incidents for supervisor triage.

Revision ID: 20260713_inc_owner
Revises: 20260713_op_assess
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_inc_owner"
down_revision: Union[str, Sequence[str], None] = "20260713_op_assess"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("incidents", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.create_index("ix_incidents_owner_id", "incidents", ["owner_id"])
    op.create_foreign_key(
        "fk_incidents_owner_id_users",
        "incidents",
        "users",
        ["owner_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_incidents_owner_id_users", "incidents", type_="foreignkey")
    op.drop_index("ix_incidents_owner_id", table_name="incidents")
    op.drop_column("incidents", "owner_id")
