"""Additive marker so Atlas roster archive survives hourly PAMS sync.

Revision ID: 20261118_eng_roster_arch
Revises: 20261117_reg_ssot_d2_waste

PAMS ``sync_pams_technicians`` rewrites ``engineers.is_active`` from
``active_technician`` every hour. Archiving a person who is still active in
PAMS would otherwise revert within 60 minutes. ``roster_archived_at`` is the
durable QGP-side marker: when set, sync forces ``is_active = False``.
Nullable, no backfill. Chains off current ``main`` head — not a branch of
``20261114_cmp_fb_kind``.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261118_eng_roster_arch"
down_revision: Union[str, Sequence[str], None] = "20261117_reg_ssot_d2_waste"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "engineers",
        sa.Column("roster_archived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("engineers", "roster_archived_at")
