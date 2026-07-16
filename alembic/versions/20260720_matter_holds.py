"""Add tenant-scoped matter legal-hold SSOT.

Revision ID: 20260720_matter_holds
Revises: 20260720_gt_src_sync
Create Date: 2026-07-20

The generic matter_reference intentionally has no foreign key: QGP does not
yet have a canonical legal-matter model. Retention workers are not changed by
this migration and must explicitly consume active holds before any purge.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_matter_holds"
down_revision: Union[str, Sequence[str], None] = "20260720_gt_src_sync"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "matter_legal_holds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("matter_reference", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("released_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(trim(matter_reference)) > 0", name="ck_matter_legal_holds_matter_ref"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["released_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_matter_legal_holds_tenant_id", "matter_legal_holds", ["tenant_id"])
    op.create_index(
        "ix_matter_legal_holds_tenant_matter", "matter_legal_holds", ["tenant_id", "matter_reference"]
    )
    op.create_index("ix_matter_legal_holds_tenant_status", "matter_legal_holds", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_matter_legal_holds_tenant_status", table_name="matter_legal_holds")
    op.drop_index("ix_matter_legal_holds_tenant_matter", table_name="matter_legal_holds")
    op.drop_index("ix_matter_legal_holds_tenant_id", table_name="matter_legal_holds")
    op.drop_table("matter_legal_holds")
