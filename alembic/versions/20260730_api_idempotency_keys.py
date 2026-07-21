"""Create api_idempotency_keys for durable Idempotency-Key creates (PX-001).

Revision ID: 20260730_api_idem
Revises: 20260719_gov_lib_w3_review
Create Date: 2026-07-30
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_api_idem"
down_revision: Union[str, Sequence[str], None] = "20260719_gov_lib_w3_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_idempotency_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "scope",
            "idempotency_key",
            name="uq_api_idempotency_tenant_scope_key",
        ),
    )
    op.create_index("ix_api_idempotency_keys_tenant_id", "api_idempotency_keys", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_api_idempotency_keys_tenant_id", table_name="api_idempotency_keys")
    op.drop_table("api_idempotency_keys")
