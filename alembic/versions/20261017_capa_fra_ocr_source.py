"""Add CAPASource.fra_ocr enum value.

Revision ID: 20261017_capa_fra_ocr
Revises: 20261016_cs_fra_ocr_ev
Create Date: 2026-10-17

Adds ``fra_ocr`` to the PostgreSQL ``capasource`` enum so confirming an FRA OCR
draft can raise CAPAs for operator-checked priority actions
(``COMPLIANCE_SCHEDULE_FRA_OCR_ACTIONS_ENABLED``).

Idempotent ALTER TYPE ADD VALUE. Irreversible in PostgreSQL.
This revision only adds the label; it never binds it in the same transaction.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261017_capa_fra_ocr"
down_revision: Union[str, Sequence[str], None] = "20261016_cs_fra_ocr_ev"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    result = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'capasource'")).fetchone()
    if result:
        try:
            op.execute("ALTER TYPE capasource ADD VALUE IF NOT EXISTS 'fra_ocr'")
        except Exception:
            pass


def downgrade() -> None:
    pass  # ALTER TYPE ADD VALUE cannot be reversed
