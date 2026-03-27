"""Add missing updated_by_id to documents.

Revision ID: 20260327_documents_updated_by
Revises: 20260326_align_kri_tables
Create Date: 2026-03-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260327_documents_updated_by"
down_revision: Union[str, None] = "20260326_align_kri_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("documents", "updated_by_id"):
        op.add_column("documents", sa.Column("updated_by_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    if _has_column("documents", "updated_by_id"):
        op.drop_column("documents", "updated_by_id")
