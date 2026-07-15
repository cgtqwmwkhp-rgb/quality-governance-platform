"""Wave5: partner webhook subscriptions + delivery log scaffold.

Revision ID: 20260716_partner_webhooks
Revises: 20260715_audit_db_integrity
Create Date: 2026-07-16

Rebase note: if Wave2a (#1009) lands on main first with
``20260716_capa_investigation_source``, rebase this migration to chain after
that revision instead of ``20260715_audit_db_integrity``.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_partner_webhooks"
down_revision: Union[str, Sequence[str], None] = "20260715_audit_db_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("secret", sa.String(length=255), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_webhook_subscriptions_tenant_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_subscriptions_tenant_id", "webhook_subscriptions", ["tenant_id"])
    op.create_index(
        "ix_webhook_subscriptions_tenant_active",
        "webhook_subscriptions",
        ["tenant_id", "is_active"],
    )

    op.create_table(
        "webhook_delivery_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("signature", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["webhook_subscriptions.id"],
            name="fk_webhook_delivery_logs_subscription_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_webhook_delivery_logs_tenant_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_delivery_logs_tenant_id", "webhook_delivery_logs", ["tenant_id"])
    op.create_index(
        "ix_webhook_delivery_logs_tenant_created",
        "webhook_delivery_logs",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_webhook_delivery_logs_subscription",
        "webhook_delivery_logs",
        ["subscription_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_delivery_logs_subscription", table_name="webhook_delivery_logs")
    op.drop_index("ix_webhook_delivery_logs_tenant_created", table_name="webhook_delivery_logs")
    op.drop_index("ix_webhook_delivery_logs_tenant_id", table_name="webhook_delivery_logs")
    op.drop_table("webhook_delivery_logs")
    op.drop_index("ix_webhook_subscriptions_tenant_active", table_name="webhook_subscriptions")
    op.drop_index("ix_webhook_subscriptions_tenant_id", table_name="webhook_subscriptions")
    op.drop_table("webhook_subscriptions")
