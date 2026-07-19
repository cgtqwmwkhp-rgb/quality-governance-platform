"""Add competence_asset_type_id to document_campaigns (O-12).

Revision ID: 20260729_campaign_comp_gate
Revises: 20260728_campaign_sig_disp
Create Date: 2026-07-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_campaign_comp_gate"
down_revision: Union[str, Sequence[str], None] = "20260728_campaign_sig_disp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_campaigns",
        sa.Column("competence_asset_type_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_campaigns_competence_asset_type_id",
        "document_campaigns",
        "asset_types",
        ["competence_asset_type_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_document_campaigns_competence_asset_type",
        "document_campaigns",
        ["competence_asset_type_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_campaigns_competence_asset_type", table_name="document_campaigns")
    op.drop_constraint(
        "fk_document_campaigns_competence_asset_type_id",
        "document_campaigns",
        type_="foreignkey",
    )
    op.drop_column("document_campaigns", "competence_asset_type_id")
