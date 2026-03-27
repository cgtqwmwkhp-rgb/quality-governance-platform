"""Add Asset Registry tables for Workforce Development Platform.

Revision ID: 20260302_asset_reg
Revises: 20260302_capa_enum
Create Date: 2026-03-02 10:20:00.000000

Creates asset_types, assets, and template_asset_types tables for
equipment tracking and audit template tagging.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260302_asset_reg"
down_revision = "20260302_capa_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # asset_types
    op.create_table(
        "asset_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "category",
            sa.String(50),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_types_category", "asset_types", ["category"])
    op.create_index("ix_asset_types_name", "asset_types", ["name"])
    op.create_index("ix_asset_types_tenant_id", "asset_types", ["tenant_id"])

    # assets
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(36), nullable=False),
        sa.Column("asset_type_id", sa.Integer(), nullable=False),
        sa.Column("asset_number", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("make", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("year_of_manufacture", sa.Integer(), nullable=True),
        sa.Column("safe_working_load", sa.Float(), nullable=True),
        sa.Column("swl_unit", sa.String(20), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("last_service_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_service_due", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_loler_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_loler_due", sa.DateTime(timezone=True), nullable=True),
        sa.Column("site", sa.String(200), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("qr_code_data", sa.String(500), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["asset_type_id"], ["asset_types.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_assets_asset_number", "assets", ["asset_number"])
    op.create_index("ix_assets_asset_type_id", "assets", ["asset_type_id"])
    op.create_index("ix_assets_external_id", "assets", ["external_id"])
    op.create_index("ix_assets_status", "assets", ["status"])
    op.create_index("ix_assets_tenant_id", "assets", ["tenant_id"])

    # template_asset_types (junction)
    op.create_table(
        "template_asset_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("asset_type_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["asset_type_id"], ["asset_types.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["audit_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "asset_type_id", name="uq_template_asset_type"),
    )
    op.create_index("ix_template_asset_types_asset_type_id", "template_asset_types", ["asset_type_id"])
    op.create_index("ix_template_asset_types_template_id", "template_asset_types", ["template_id"])
    op.create_index("ix_template_asset_types_tenant_id", "template_asset_types", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("template_asset_types")
    op.drop_table("assets")
    op.drop_table("asset_types")
