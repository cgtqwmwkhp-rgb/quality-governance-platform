"""Additive version-control columns for document_versions + controlled_document_versions.

Revision ID: 20260713_doc_ver_ctrl
Revises: 20260713_op_assess
Create Date: 2026-07-13

CUJ document version control:
- status / is_immutable / published_* on library document_versions
- is_immutable on controlled_document_versions
- Backfill existing rows as draft (mutable) unless status already published-like
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_doc_ver_ctrl"
down_revision: Union[str, Sequence[str], None] = "20260713_op_assess"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in _inspector().get_columns(table_name)}


def upgrade() -> None:
    if _table_exists("document_versions"):
        if not _has_column("document_versions", "change_type"):
            op.add_column(
                "document_versions",
                sa.Column("change_type", sa.String(length=50), nullable=False, server_default="revision"),
            )
        if not _has_column("document_versions", "status"):
            op.add_column(
                "document_versions",
                sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
            )
            op.create_index("ix_document_versions_status", "document_versions", ["status"])
        if not _has_column("document_versions", "is_immutable"):
            op.add_column(
                "document_versions",
                sa.Column("is_immutable", sa.Boolean(), nullable=False, server_default=sa.false()),
            )
        if not _has_column("document_versions", "published_at"):
            op.add_column(
                "document_versions",
                sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            )
        if not _has_column("document_versions", "published_by_id"):
            op.add_column(
                "document_versions",
                sa.Column("published_by_id", sa.Integer(), nullable=True),
            )
            op.create_foreign_key(
                "fk_document_versions_published_by_id",
                "document_versions",
                "users",
                ["published_by_id"],
                ["id"],
            )

    if _table_exists("controlled_document_versions"):
        if not _has_column("controlled_document_versions", "is_immutable"):
            op.add_column(
                "controlled_document_versions",
                sa.Column("is_immutable", sa.Boolean(), nullable=False, server_default=sa.false()),
            )
            op.execute(
                sa.text(
                    """
                    UPDATE controlled_document_versions
                    SET is_immutable = TRUE
                    WHERE lower(status) IN (
                        'published', 'superseded', 'approved', 'effective', 'active', 'obsolete'
                    )
                    """
                )
            )


def downgrade() -> None:
    if _table_exists("controlled_document_versions") and _has_column(
        "controlled_document_versions", "is_immutable"
    ):
        op.drop_column("controlled_document_versions", "is_immutable")

    if _table_exists("document_versions"):
        if _has_column("document_versions", "published_by_id"):
            op.drop_constraint("fk_document_versions_published_by_id", "document_versions", type_="foreignkey")
            op.drop_column("document_versions", "published_by_id")
        if _has_column("document_versions", "published_at"):
            op.drop_column("document_versions", "published_at")
        if _has_column("document_versions", "is_immutable"):
            op.drop_column("document_versions", "is_immutable")
        if _has_column("document_versions", "status"):
            op.drop_index("ix_document_versions_status", table_name="document_versions")
            op.drop_column("document_versions", "status")
        if _has_column("document_versions", "change_type"):
            op.drop_column("document_versions", "change_type")
