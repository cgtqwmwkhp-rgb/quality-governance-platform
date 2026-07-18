"""Add signature_disposition to campaign_assignments (CUJ Wave 1).

Revision ID: 20260728_campaign_sig_disp
Revises: 20260727_campaign_snooze
Create Date: 2026-07-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_campaign_sig_disp"
down_revision: Union[str, Sequence[str], None] = "20260727_campaign_snooze"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaign_assignments",
        sa.Column("signature_disposition", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("campaign_assignments", "signature_disposition")
