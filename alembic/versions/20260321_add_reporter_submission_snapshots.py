"""Add immutable reporter_submission snapshots to case tables.

Revision ID: 20260321_case_snapshots
Revises: 20260321_run_sheet
Create Date: 2026-03-21
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260321_case_snapshots"
down_revision: Union[str, None] = "20260321_run_sheet"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE incidents "
        "ADD COLUMN IF NOT EXISTS reporter_submission JSONB"
    )
    op.execute(
        "ALTER TABLE complaints "
        "ADD COLUMN IF NOT EXISTS reporter_submission JSONB"
    )
    op.execute(
        "ALTER TABLE road_traffic_collisions "
        "ADD COLUMN IF NOT EXISTS reporter_submission JSONB"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE road_traffic_collisions DROP COLUMN IF EXISTS reporter_submission")
    op.execute("ALTER TABLE complaints DROP COLUMN IF EXISTS reporter_submission")
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS reporter_submission")
