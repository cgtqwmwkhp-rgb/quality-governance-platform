"""Add CAPASource.investigation enum value.

Revision ID: 20260716_capa_inv_src
Revises: 20260715_audit_db_integrity
Create Date: 2026-07-16

Adds 'investigation' to the PostgreSQL capasource enum (idempotent).
Note: ALTER TYPE ADD VALUE is irreversible in PostgreSQL.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260716_capa_inv_src"
down_revision: Union[str, Sequence[str], None] = "20260715_audit_db_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    result = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'capasource'")).fetchone()
    if result:
        try:
            op.execute("ALTER TYPE capasource ADD VALUE IF NOT EXISTS 'investigation'")
        except Exception:
            pass


def downgrade() -> None:
    pass  # ALTER TYPE ADD VALUE cannot be reversed
