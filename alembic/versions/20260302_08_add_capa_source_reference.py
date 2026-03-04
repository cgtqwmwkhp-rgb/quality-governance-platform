"""Add source_reference column to capa_actions for WDP run linking.

Revision ID: 20260302_capa_src_ref
Revises: 20260302_loler
Create Date: 2026-03-02 12:00:00.000000

Stores assessment_run_id and induction_run_id (UUID strings) for CAPAs
auto-generated from workforce development outcomes.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260302_capa_src_ref"
down_revision = "20260302_loler"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "capa_actions",
        sa.Column("source_reference", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_capa_actions_source_reference",
        "capa_actions",
        ["source_reference"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_capa_actions_source_reference", table_name="capa_actions")
    op.drop_column("capa_actions", "source_reference")
