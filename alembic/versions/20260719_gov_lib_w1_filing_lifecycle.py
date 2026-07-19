"""Governance Library Wave W1: filing rules + lifecycle columns + download audit.

Revision ID: 20260719_gov_lib_w1_filing
Revises: 20260719_gov_lib_w0_taxonomy_pel
Create Date: 2026-07-19

Adds governance filing metadata on `documents` and a library-specific access
log for signed-url download events (controlled-document access logs remain
on `document_access_logs`).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260719_gov_lib_w1_filing"
down_revision: Union[str, Sequence[str], None] = "20260719_gov_lib_w0_taxonomy_pel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return column_name in {col["name"] for col in _inspector().get_columns(table_name)}


def upgrade() -> None:
    if not _column_exists("documents", "access_level"):
        op.add_column("documents", sa.Column("access_level", sa.String(length=20), nullable=True))
    if not _column_exists("documents", "is_statutory"):
        op.add_column(
            "documents",
            sa.Column("is_statutory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if not _column_exists("documents", "retention_until"):
        op.add_column("documents", sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists("documents", "duplicate_warning"):
        op.add_column(
            "documents",
            sa.Column("duplicate_warning", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if not _column_exists("documents", "duplicate_warning_detail"):
        op.add_column("documents", sa.Column("duplicate_warning_detail", sa.JSON(), nullable=True))

    if not _table_exists("library_document_access_logs"):
        op.create_table(
            "library_document_access_logs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("user_name", sa.String(length=255), nullable=False),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("action_details", sa.Text(), nullable=True),
            sa.Column(
                "timestamp",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_library_document_access_logs_tenant_id",
            "library_document_access_logs",
            ["tenant_id"],
        )
        op.create_index(
            "ix_library_document_access_logs_document_id",
            "library_document_access_logs",
            ["document_id"],
        )
        op.create_index(
            "ix_library_document_access_logs_timestamp",
            "library_document_access_logs",
            ["timestamp"],
        )


def downgrade() -> None:
    if _table_exists("library_document_access_logs"):
        op.drop_index("ix_library_document_access_logs_timestamp", table_name="library_document_access_logs")
        op.drop_index("ix_library_document_access_logs_document_id", table_name="library_document_access_logs")
        op.drop_index("ix_library_document_access_logs_tenant_id", table_name="library_document_access_logs")
        op.drop_table("library_document_access_logs")

    for column in (
        "duplicate_warning_detail",
        "duplicate_warning",
        "retention_until",
        "is_statutory",
        "access_level",
    ):
        if _column_exists("documents", column):
            op.drop_column("documents", column)
