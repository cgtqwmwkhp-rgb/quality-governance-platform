"""Add audit metadata columns to external_audit_import_jobs.

Revision ID: 20260710_audit_meta
Revises: 20260710_doc_ctl_tenant
Create Date: 2026-07-10

Adds nullable AI-extracted metadata columns so review UI and APIs can
surface organization, auditor, scope, certificate, and next-audit date.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_audit_meta"
down_revision: Union[str, None] = "20260710_doc_ctl_tenant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
