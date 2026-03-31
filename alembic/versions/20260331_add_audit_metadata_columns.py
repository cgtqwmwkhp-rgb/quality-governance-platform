"""Add audit metadata columns to external_audit_import_jobs.

Revision ID: a3b1c2d3e4f5
Revises: None (standalone)
"""

from alembic import op
import sqlalchemy as sa


revision = "a3b1c2d3e4f5"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("external_audit_import_jobs") as batch_op:
        batch_op.add_column(sa.Column("organization_name", sa.String(300), nullable=True))
        batch_op.add_column(sa.Column("auditor_name", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("audit_type", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("certificate_number", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("audit_scope", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("next_audit_date", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("external_audit_import_jobs") as batch_op:
        batch_op.drop_column("next_audit_date")
        batch_op.drop_column("audit_scope")
        batch_op.drop_column("certificate_number")
        batch_op.drop_column("audit_type")
        batch_op.drop_column("auditor_name")
        batch_op.drop_column("organization_name")
