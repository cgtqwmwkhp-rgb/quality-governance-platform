"""W2: investigation template/run structure normalization tables.

Revision ID: 20260717_inv_tmpl_normalize
Revises: 20260716_partner_webhooks
Create Date: 2026-07-17

Chained after Wave5 (#1013) ``20260716_partner_webhooks``.
Rebase note: if partner webhooks revision id differs on target branch, adjust
down_revision before merge.

Revision id kept ≤32 chars for alembic_version.version_num VARCHAR(32).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260717_inv_tmpl_normalize"
down_revision: Union[str, Sequence[str], None] = "20260716_partner_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investigation_template_sections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("section_key", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["investigation_templates.id"],
            name="fk_inv_template_sections_template_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_inv_template_sections_tenant_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "section_key", name="uq_inv_template_section_key"),
    )
    op.create_index("ix_inv_template_sections_tenant_id", "investigation_template_sections", ["tenant_id"])
    op.create_index("ix_inv_template_sections_template_id", "investigation_template_sections", ["template_id"])

    op.create_table(
        "investigation_template_fields",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("field_key", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("field_type", sa.String(length=50), nullable=False, server_default="text"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["investigation_template_sections.id"],
            name="fk_inv_template_fields_section_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["investigation_templates.id"],
            name="fk_inv_template_fields_template_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_inv_template_fields_tenant_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("section_id", "field_key", name="uq_inv_template_field_key"),
    )
    op.create_index("ix_inv_template_fields_tenant_id", "investigation_template_fields", ["tenant_id"])
    op.create_index("ix_inv_template_fields_template_id", "investigation_template_fields", ["template_id"])
    op.create_index("ix_inv_template_fields_section_id", "investigation_template_fields", ["section_id"])

    op.create_table(
        "investigation_run_field_responses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("template_field_id", sa.Integer(), nullable=False),
        sa.Column("section_key", sa.String(length=100), nullable=False),
        sa.Column("field_key", sa.String(length=100), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["investigation_runs.id"],
            name="fk_inv_run_field_responses_run_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_field_id"],
            ["investigation_template_fields.id"],
            name="fk_inv_run_field_responses_template_field_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_inv_run_field_responses_tenant_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "template_field_id", name="uq_inv_run_field_response"),
    )
    op.create_index("ix_inv_run_field_responses_tenant_id", "investigation_run_field_responses", ["tenant_id"])
    op.create_index("ix_inv_run_field_responses_run_id", "investigation_run_field_responses", ["run_id"])
    op.create_index(
        "ix_inv_run_field_responses_template_field_id",
        "investigation_run_field_responses",
        ["template_field_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_inv_run_field_responses_template_field_id", table_name="investigation_run_field_responses")
    op.drop_index("ix_inv_run_field_responses_run_id", table_name="investigation_run_field_responses")
    op.drop_index("ix_inv_run_field_responses_tenant_id", table_name="investigation_run_field_responses")
    op.drop_table("investigation_run_field_responses")

    op.drop_index("ix_inv_template_fields_section_id", table_name="investigation_template_fields")
    op.drop_index("ix_inv_template_fields_template_id", table_name="investigation_template_fields")
    op.drop_index("ix_inv_template_fields_tenant_id", table_name="investigation_template_fields")
    op.drop_table("investigation_template_fields")

    op.drop_index("ix_inv_template_sections_template_id", table_name="investigation_template_sections")
    op.drop_index("ix_inv_template_sections_tenant_id", table_name="investigation_template_sections")
    op.drop_table("investigation_template_sections")
