"""R6: partner API tokens (scoped bearer credentials).

Revision ID: 20260717_partner_api_tokens
Revises: 20260717_ocr_artifacts
Create Date: 2026-07-17

Chained after R5 OCR artifacts (#1016) ``20260717_ocr_artifacts``.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260717_partner_api_tokens"
down_revision: Union[str, Sequence[str], None] = "20260717_ocr_artifacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "partner_api_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_partner_api_tokens_tenant_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_partner_api_tokens_tenant_id", "partner_api_tokens", ["tenant_id"])
    op.create_index(
        "ix_partner_api_tokens_tenant_active",
        "partner_api_tokens",
        ["tenant_id", "is_active"],
    )
    op.create_index("ix_partner_api_tokens_prefix", "partner_api_tokens", ["token_prefix"])


def downgrade() -> None:
    op.drop_index("ix_partner_api_tokens_prefix", table_name="partner_api_tokens")
    op.drop_index("ix_partner_api_tokens_tenant_active", table_name="partner_api_tokens")
    op.drop_index("ix_partner_api_tokens_tenant_id", table_name="partner_api_tokens")
    op.drop_table("partner_api_tokens")
