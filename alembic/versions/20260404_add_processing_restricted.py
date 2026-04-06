"""Add processing_restricted column to incidents, complaints, and near_misses.

Required for GDPR Article 18 (Right to Restriction of Processing).
The GDPRService.restrict_processing() method sets this flag to True
when a data subject requests processing restriction.

Revision ID: d4e5f6a7b8c9
Revises: c8d9e0f1a2b3
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("processing_restricted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "complaints",
        sa.Column("processing_restricted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "near_misses",
        sa.Column("processing_restricted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("near_misses", "processing_restricted")
    op.drop_column("complaints", "processing_restricted")
    op.drop_column("incidents", "processing_restricted")
