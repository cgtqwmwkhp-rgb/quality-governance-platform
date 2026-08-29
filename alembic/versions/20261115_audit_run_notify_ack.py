"""AUD-DEV-2: audit_runs notified_at / acknowledged_at.

Revision ID: 20261115_aud_notify
Revises: 20261114_cmp_fb_kind

Own migration for the field closed-loop stamps. Does not fold into an
earlier audits revision. Nullable: historic runs were never notified or
acked through this path.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261115_aud_notify"
down_revision: Union[str, Sequence[str], None] = "20261114_cmp_fb_kind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audit_runs",
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "audit_runs",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audit_runs", "acknowledged_at")
    op.drop_column("audit_runs", "notified_at")
