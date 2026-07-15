"""Add CAPASource near_miss + rta enum values.

Revision ID: 20260718_capa_nm_rta
Revises: 20260718_failed_tasks
Create Date: 2026-07-18

Idempotent ALTER TYPE ADD VALUE for first-class near-miss / RTA CAPA sources.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260718_capa_nm_rta"
down_revision: Union[str, Sequence[str], None] = "20260718_failed_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    result = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'capasource'")).fetchone()
    if result:
        try:
            op.execute("ALTER TYPE capasource ADD VALUE IF NOT EXISTS 'near_miss'")
            op.execute("ALTER TYPE capasource ADD VALUE IF NOT EXISTS 'rta'")
        except Exception:
            pass


def downgrade() -> None:
    pass  # ALTER TYPE ADD VALUE cannot be reversed
