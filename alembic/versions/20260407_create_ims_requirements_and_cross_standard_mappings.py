"""Create ims_requirements and cross_standard_mappings core tables when missing.

These ORM-backed tables are required by:
- GET /api/v1/compliance/standards (IMS counts + canonical enrichment)
- GET /api/v1/cross-standard-mappings

Earlier migrations only altered cross_standard_mappings when the table already existed;
fresh databases promoted from migrations never received CREATE TABLE for these IMS tables,
which surfaces as ProgrammingError in production.

Revision ID: f6e5d4c3b2a1
Revises: e4f5a6b7c8d9
Create Date: 2026-04-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6e5d4c3b2a1"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if not _table_exists("ims_requirements"):
        op.create_table(
            "ims_requirements",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=True),
            sa.Column("clause_number", sa.String(length=20), nullable=False),
            sa.Column("clause_title", sa.String(length=255), nullable=False),
            sa.Column("clause_text", sa.Text(), nullable=False),
            sa.Column("standard", sa.String(length=50), nullable=False),
            sa.Column("parent_clause", sa.String(length=20), nullable=True),
            sa.Column("level", sa.Integer(), server_default="1", nullable=False),
            sa.Column("annex_sl_element", sa.String(length=50), nullable=True),
            sa.Column("is_common_requirement", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("keywords", sa.JSON(), nullable=True),
            sa.Column("is_applicable", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("exclusion_justification", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ims_requirements_tenant_id", "ims_requirements", ["tenant_id"], unique=False)
        op.create_index("ix_ims_requirements_clause_number", "ims_requirements", ["clause_number"], unique=False)
        op.create_index("ix_ims_requirements_standard", "ims_requirements", ["standard"], unique=False)

    if not _table_exists("cross_standard_mappings"):
        op.create_table(
            "cross_standard_mappings",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=True),
            sa.Column("primary_clause_id", sa.Integer(), nullable=True),
            sa.Column("primary_requirement_id", sa.Integer(), nullable=False),
            sa.Column("primary_standard", sa.String(length=50), nullable=False),
            sa.Column("primary_clause", sa.String(length=20), nullable=False),
            sa.Column("mapped_clause_id", sa.Integer(), nullable=True),
            sa.Column("mapped_requirement_id", sa.Integer(), nullable=False),
            sa.Column("mapped_standard", sa.String(length=50), nullable=False),
            sa.Column("mapped_clause", sa.String(length=20), nullable=False),
            sa.Column("mapping_type", sa.String(length=50), server_default="equivalent", nullable=False),
            sa.Column("mapping_strength", sa.Integer(), server_default="100", nullable=False),
            sa.Column("mapping_notes", sa.Text(), nullable=True),
            sa.Column("annex_sl_element", sa.String(length=50), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["mapped_clause_id"], ["clauses.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["mapped_requirement_id"], ["ims_requirements.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["primary_clause_id"], ["clauses.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["primary_requirement_id"], ["ims_requirements.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_cross_standard_mappings_tenant_id", "cross_standard_mappings", ["tenant_id"], unique=False
        )
        if not is_sqlite:
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_cross_standard_mappings_primary_clause_id "
                "ON cross_standard_mappings(primary_clause_id)"
            )
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_cross_standard_mappings_mapped_clause_id "
                "ON cross_standard_mappings(mapped_clause_id)"
            )


def downgrade() -> None:
    if _table_exists("cross_standard_mappings"):
        op.drop_index("ix_cross_standard_mappings_tenant_id", table_name="cross_standard_mappings")
        bind = op.get_bind()
        if bind.dialect.name != "sqlite":
            op.execute("DROP INDEX IF EXISTS ix_cross_standard_mappings_primary_clause_id")
            op.execute("DROP INDEX IF EXISTS ix_cross_standard_mappings_mapped_clause_id")
        op.drop_table("cross_standard_mappings")

    if _table_exists("ims_requirements"):
        op.drop_index("ix_ims_requirements_standard", table_name="ims_requirements")
        op.drop_index("ix_ims_requirements_clause_number", table_name="ims_requirements")
        op.drop_index("ix_ims_requirements_tenant_id", table_name="ims_requirements")
        op.drop_table("ims_requirements")
