"""Add rta_running_sheet_entries table for timestamped RTA narrative log.

Revision ID: 20260321_run_sheet
Revises: 20260320_veh_reg
Create Date: 2026-03-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260321_run_sheet"
down_revision: Union[str, None] = "20260320_drivers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS rta_running_sheet_entries (
        id              SERIAL PRIMARY KEY,
        rta_id          INTEGER NOT NULL REFERENCES road_traffic_collisions(id) ON DELETE CASCADE,
        content         TEXT NOT NULL,
        entry_type      VARCHAR(50) NOT NULL DEFAULT 'note',
        author_id       INTEGER REFERENCES users(id),
        author_email    VARCHAR(255),
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS ix_rta_running_sheet_rta_id ON rta_running_sheet_entries(rta_id);
    CREATE INDEX IF NOT EXISTS ix_rta_running_sheet_created ON rta_running_sheet_entries(created_at);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rta_running_sheet_entries;")
