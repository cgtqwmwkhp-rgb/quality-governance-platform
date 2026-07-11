"""Create controlled_documents + controlled_document_versions if missing.

Revision ID: 20260711_ctl_docs_create
Revises: 20260711_rls_docs_exp
Create Date: 2026-07-11

Path-to-10 S14: schema truth for document-control core tables so alembic check
can unfilter them. Idempotent — skips when tables already exist (e.g. prod
created outside Alembic).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260711_ctl_docs_create"
down_revision: Union[str, Sequence[str], None] = "20260711_rls_docs_exp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def upgrade() -> None:
    if not _table_exists("controlled_documents"):
        op.create_table(
            "controlled_documents",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("document_number", sa.String(length=50), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("document_type", sa.String(length=50), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=False),
            sa.Column("subcategory", sa.String(length=100), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("current_version", sa.String(length=20), nullable=False, server_default="1.0"),
            sa.Column("major_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("minor_version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
            sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("author_id", sa.Integer(), nullable=True),
            sa.Column("author_name", sa.String(length=255), nullable=True),
            sa.Column("owner_id", sa.Integer(), nullable=True),
            sa.Column("owner_name", sa.String(length=255), nullable=True),
            sa.Column("department", sa.String(length=100), nullable=True),
            sa.Column("approver_id", sa.Integer(), nullable=True),
            sa.Column("approver_name", sa.String(length=255), nullable=True),
            sa.Column("approved_date", sa.DateTime(), nullable=True),
            sa.Column("effective_date", sa.DateTime(), nullable=True),
            sa.Column("expiry_date", sa.DateTime(), nullable=True),
            sa.Column("review_frequency_months", sa.Integer(), nullable=False, server_default="12"),
            sa.Column("next_review_date", sa.DateTime(), nullable=True),
            sa.Column("last_review_date", sa.DateTime(), nullable=True),
            sa.Column("file_name", sa.String(length=500), nullable=True),
            sa.Column("file_path", sa.String(length=1000), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column("file_type", sa.String(length=50), nullable=True),
            sa.Column("checksum", sa.String(length=64), nullable=True),
            sa.Column("relevant_standards", sa.JSON(), nullable=True),
            sa.Column("relevant_clauses", sa.JSON(), nullable=True),
            sa.Column("regulatory_requirements", sa.JSON(), nullable=True),
            sa.Column("distribution_list", sa.JSON(), nullable=True),
            sa.Column("access_level", sa.String(length=50), nullable=False, server_default="internal"),
            sa.Column("is_confidential", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("training_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("linked_training_id", sa.Integer(), nullable=True),
            sa.Column("retention_period_years", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("disposal_method", sa.String(length=100), nullable=True),
            sa.Column("obsolete_date", sa.DateTime(), nullable=True),
            sa.Column("superseded_by", sa.Integer(), nullable=True),
            sa.Column("obsolete_reason", sa.Text(), nullable=True),
            sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint("major_version >= 1", name="ck_controlled_docs_major_version_positive"),
            sa.CheckConstraint("minor_version >= 0", name="ck_controlled_docs_minor_version_nonneg"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["approver_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["superseded_by"], ["controlled_documents.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("document_number"),
        )
        op.create_index("ix_controlled_documents_document_number", "controlled_documents", ["document_number"])
        op.create_index("ix_controlled_documents_document_type", "controlled_documents", ["document_type"])
        op.create_index("ix_controlled_documents_status", "controlled_documents", ["status"])
        op.create_index("ix_controlled_documents_tenant_id", "controlled_documents", ["tenant_id"])

    if not _table_exists("controlled_document_versions"):
        op.create_table(
            "controlled_document_versions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("version_number", sa.String(length=20), nullable=False),
            sa.Column("major_version", sa.Integer(), nullable=False),
            sa.Column("minor_version", sa.Integer(), nullable=False),
            sa.Column("change_summary", sa.Text(), nullable=False),
            sa.Column("change_reason", sa.Text(), nullable=True),
            sa.Column("change_type", sa.String(length=50), nullable=False, server_default="revision"),
            sa.Column("file_name", sa.String(length=500), nullable=True),
            sa.Column("file_path", sa.String(length=1000), nullable=True),
            sa.Column("file_content", sa.LargeBinary(), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column("checksum", sa.String(length=64), nullable=True),
            sa.Column("diff_from_previous", sa.Text(), nullable=True),
            sa.Column("sections_changed", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("created_by_name", sa.String(length=255), nullable=True),
            sa.Column("approved_by_id", sa.Integer(), nullable=True),
            sa.Column("approved_by_name", sa.String(length=255), nullable=True),
            sa.Column("approved_date", sa.DateTime(), nullable=True),
            sa.Column("effective_date", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["document_id"], ["controlled_documents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_controlled_document_versions_document_id",
            "controlled_document_versions",
            ["document_id"],
        )
        op.create_index(
            "ix_controlled_document_versions_tenant_id",
            "controlled_document_versions",
            ["tenant_id"],
        )


def downgrade() -> None:
    if _table_exists("controlled_document_versions"):
        op.drop_table("controlled_document_versions")
    if _table_exists("controlled_documents"):
        op.drop_table("controlled_documents")
