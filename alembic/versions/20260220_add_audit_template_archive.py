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
    is_sqlite = op.get_bind().dialect.name == "sqlite"

    op.add_column(
        "audit_templates",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "audit_templates",
        sa.Column(
            "archived_by_id",
            sa.Integer(),
            nullable=True,
        ),
    )
    if not is_sqlite:
        op.create_foreign_key(
            "fk_audit_templates_archived_by_id_users",
            "audit_templates",
            "users",
            ["archived_by_id"],
            ["id"],
        )
    op.create_index(
        "ix_audit_templates_archived_at",
        "audit_templates",
        ["archived_at"],
    )


def downgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"

    op.drop_index("ix_audit_templates_archived_at", table_name="audit_templates")
    if not is_sqlite:
        op.drop_constraint("fk_audit_templates_archived_by_id_users", "audit_templates", type_="foreignkey")
    op.drop_column("audit_templates", "archived_by_id")
    op.drop_column("audit_templates", "archived_at")
