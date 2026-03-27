"""Add immutable reporter_submission snapshots to case tables.

Revision ID: 20260321_case_snapshots
Revises: 20260321_run_sheet
Create Date: 2026-03-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260321_case_snapshots"
down_revision: Union[str, None] = "20260321_run_sheet"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CASE_TABLES = ["incidents", "complaints", "road_traffic_collisions"]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table_name in CASE_TABLES:
        if not inspector.has_table(table_name):
            continue
        existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
        if "reporter_submission" not in existing_columns:
            op.add_column(table_name, sa.Column("reporter_submission", sa.JSON(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table_name in reversed(CASE_TABLES):
        if not inspector.has_table(table_name):
            continue
        existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
        if "reporter_submission" in existing_columns:
            op.drop_column(table_name, "reporter_submission")
