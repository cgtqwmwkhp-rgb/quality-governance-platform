"""Governance Library Wave W3: review packs + regulatory findings.

Revision ID: 20260719_gov_lib_w3_review
Revises: 20260719_merge_gov_lib_cg
Create Date: 2026-07-19

Adds ``library_review_packs`` (90-day review windows) and
``regulatory_findings`` (horizon-scan results requiring human disposition).
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260719_gov_lib_w3_review"
down_revision: Union[str, Sequence[str], None] = "20260719_merge_gov_lib_cg"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(idx["name"] == index_name for idx in _inspector().get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("library_review_packs"):
        op.create_table(
            "library_review_packs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column("window_days", sa.Integer(), nullable=False, server_default="90"),
            sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("opened_by_id", sa.Integer(), nullable=True),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_by_id", sa.Integer(), nullable=True),
            sa.Column("internal_inputs", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["opened_by_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["closed_by_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_library_review_packs_tenant_id", "library_review_packs", ["tenant_id"])
        op.create_index("ix_library_review_packs_document_id", "library_review_packs", ["document_id"])
        op.create_index("ix_library_review_packs_status", "library_review_packs", ["status"])
        op.create_index("ix_library_review_packs_created_at", "library_review_packs", ["created_at"])

    if not _index_exists("library_review_packs", "uq_library_review_packs_one_open"):
        op.create_index(
            "uq_library_review_packs_one_open",
            "library_review_packs",
            ["tenant_id", "document_id"],
            unique=True,
            postgresql_where=sa.text("status = 'open'"),
        )

    if not _table_exists("regulatory_findings"):
        op.create_table(
            "regulatory_findings",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("pack_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=False),
            sa.Column("external_id", sa.String(length=255), nullable=True),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("source_url", sa.String(length=1000), nullable=True),
            sa.Column("raw_payload", sa.JSON(), nullable=True),
            sa.Column("disposition", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("dispositioned_by_id", sa.Integer(), nullable=True),
            sa.Column("dispositioned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("disposition_notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["pack_id"], ["library_review_packs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["dispositioned_by_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_regulatory_findings_tenant_id", "regulatory_findings", ["tenant_id"])
        op.create_index("ix_regulatory_findings_pack_id", "regulatory_findings", ["pack_id"])
        op.create_index("ix_regulatory_findings_disposition", "regulatory_findings", ["disposition"])
        op.create_index("ix_regulatory_findings_created_at", "regulatory_findings", ["created_at"])


def downgrade() -> None:
    if _table_exists("regulatory_findings"):
        op.drop_index("ix_regulatory_findings_created_at", table_name="regulatory_findings")
        op.drop_index("ix_regulatory_findings_disposition", table_name="regulatory_findings")
        op.drop_index("ix_regulatory_findings_pack_id", table_name="regulatory_findings")
        op.drop_index("ix_regulatory_findings_tenant_id", table_name="regulatory_findings")
        op.drop_table("regulatory_findings")

    if _index_exists("library_review_packs", "uq_library_review_packs_one_open"):
        op.drop_index("uq_library_review_packs_one_open", table_name="library_review_packs")

    if _table_exists("library_review_packs"):
        op.drop_index("ix_library_review_packs_created_at", table_name="library_review_packs")
        op.drop_index("ix_library_review_packs_status", table_name="library_review_packs")
        op.drop_index("ix_library_review_packs_document_id", table_name="library_review_packs")
        op.drop_index("ix_library_review_packs_tenant_id", table_name="library_review_packs")
        op.drop_table("library_review_packs")
