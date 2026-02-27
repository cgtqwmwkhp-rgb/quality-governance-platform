"""Restore missing soft-delete revision for migration chain continuity.

Revision ID: 20260222_soft_delete
Revises: 20260127_source_form
Create Date: 2026-02-22 10:00:00.000000

This migration is intentionally a no-op. It restores a revision identifier that
exists in deployed environments so Alembic can resolve and continue upgrades.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260222_soft_delete"
down_revision = "20260127_source_form"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op migration for chain continuity."""
    pass


def downgrade() -> None:
    """No-op downgrade for chain continuity."""
    pass
