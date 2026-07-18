"""Add snooze_until to campaign_assignments (O-04 reminder snooze).

Revision ID: 20260727_campaign_snooze
Revises: 20260718_doc_campaign
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260727_campaign_snooze"
down_revision: Union[str, Sequence[str], None] = "20260718_doc_campaign"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaign_assignments",
        sa.Column("snooze_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_campaign_assignments_snooze_until",
        "campaign_assignments",
        ["snooze_until"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_assignments_snooze_until", table_name="campaign_assignments")
    op.drop_column("campaign_assignments", "snooze_until")
