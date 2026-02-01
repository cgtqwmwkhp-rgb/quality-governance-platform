"""Add external_ref field to complaints for idempotency.

Revision ID: 20260201_external_ref
Revises: 20260131_add_investigation_actions
Create Date: 2026-02-01

This migration adds the external_ref field to the complaints table to support
idempotent imports from ETL/external systems. The field is:
- Optional (nullable=True)
- Unique when not null (enables duplicate detection)
- Indexed for fast lookups
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260201_external_ref"
down_revision = "20260131_inv_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add external_ref column to complaints table."""
    op.add_column(
        "complaints",
        sa.Column("external_ref", sa.String(length=100), nullable=True),
    )
    # Create unique index on external_ref (where not null)
    op.create_index(
        "ix_complaints_external_ref",
        "complaints",
        ["external_ref"],
        unique=True,
    )


def downgrade() -> None:
    """Remove external_ref column from complaints table."""
    op.drop_index("ix_complaints_external_ref", table_name="complaints")
    op.drop_column("complaints", "external_ref")
