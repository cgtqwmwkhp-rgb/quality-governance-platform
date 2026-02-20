"""Add archive columns to audit_templates for two-stage soft delete.

Revision ID: 20260220_archive
Revises: 20260220_workflow_persist
Create Date: 2026-02-20
"""

import sqlalchemy as sa
from alembic import op

revision = "20260220_archive"
down_revision = "20260220_workflow_persist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_templates",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "audit_templates",
        sa.Column(
            "archived_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_audit_templates_archived_at",
        "audit_templates",
        ["archived_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_templates_archived_at", table_name="audit_templates")
    op.drop_column("audit_templates", "archived_by_id")
    op.drop_column("audit_templates", "archived_at")
