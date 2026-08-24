"""Customer Feedback PR-1: complaints.feedback_kind discriminator.

Revision ID: 20261114_cmp_fb_kind
Revises: 20261113_standards_w6_edges

Additive only. Existing rows backfill to ``complaint`` via NOT NULL
server_default. Later kinds (compliment / suggestion / general) are allowed
by CHECK so PR-2 can write them; this revision has no write path for them.

Read-side honesty depends on this column existing before any non-complaint
row can be created: KPI / exec / copilot surfaces currently mean "all rows
in complaints" when they say complaints.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Revision id kept <= 32 chars for alembic_version.version_num VARCHAR(32).
revision: str = "20261114_cmp_fb_kind"
down_revision: Union[str, Sequence[str], None] = "20261113_standards_w6_edges"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "complaints",
        sa.Column(
            "feedback_kind",
            sa.String(length=20),
            nullable=False,
            server_default="complaint",
        ),
    )
    op.create_check_constraint(
        "ck_complaints_feedback_kind",
        "complaints",
        "feedback_kind IN ('complaint', 'compliment', 'suggestion', 'general')",
    )
    op.create_index(
        "ix_complaints_tenant_kind_received",
        "complaints",
        ["tenant_id", "feedback_kind", "received_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_complaints_tenant_kind_received", table_name="complaints")
    op.drop_constraint("ck_complaints_feedback_kind", "complaints", type_="check")
    op.drop_column("complaints", "feedback_kind")
