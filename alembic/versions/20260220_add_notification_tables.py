"""Add notification system tables.

Revision ID: 20260220_notifications
Revises: 20260220_risks_merge
Create Date: 2026-02-20 16:00:00.000000

Creates the notifications, notification_preferences, mentions, and
assignments tables required by the real-time notification system.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260220_notifications"
down_revision: Union[str, None] = "20260220_risks_merge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOTIFICATION_TYPE_VALUES = (
    "mention",
    "assignment",
    "reassignment",
    "incident_new",
    "incident_update",
    "incident_escalated",
    "action_assigned",
    "action_due_soon",
    "action_overdue",
    "action_completed",
    "audit_scheduled",
    "audit_started",
    "audit_completed",
    "audit_finding",
    "approval_requested",
    "approval_granted",
    "approval_rejected",
    "compliance_alert",
    "certificate_expiring",
    "certificate_expired",
    "sos_alert",
    "riddor_incident",
    "system_announcement",
    "report_ready",
)

NOTIFICATION_PRIORITY_VALUES = ("critical", "high", "medium", "low")


def upgrade() -> None:
    notification_type_enum = sa.Enum(*NOTIFICATION_TYPE_VALUES, name="notificationtype")
    notification_priority_enum = sa.Enum(*NOTIFICATION_PRIORITY_VALUES, name="notificationpriority")

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("type", notification_type_enum, nullable=False, index=True),
        sa.Column("priority", notification_priority_enum, nullable=False, server_default="medium"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), index=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_channels", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, index=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("email_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("sms_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("push_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("phone_number", sa.String(20), nullable=True),
        sa.Column("quiet_hours_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("quiet_hours_start", sa.String(5), nullable=True),
        sa.Column("quiet_hours_end", sa.String(5), nullable=True),
        sa.Column("category_preferences", sa.JSON(), nullable=True),
        sa.Column("email_digest_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("email_digest_frequency", sa.String(20), server_default="daily"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "mentions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("content_type", sa.String(50), nullable=False, index=True),
        sa.Column("content_id", sa.String(36), nullable=False, index=True),
        sa.Column("mentioned_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("mentioned_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("mention_text", sa.Text(), nullable=False),
        sa.Column("context_snippet", sa.Text(), nullable=True),
        sa.Column("start_position", sa.Integer(), nullable=True),
        sa.Column("end_position", sa.Integer(), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(50), nullable=False, index=True),
        sa.Column("entity_id", sa.String(36), nullable=False, index=True),
        sa.Column("assigned_to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("assigned_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("priority", sa.String(20), server_default="medium"),
        sa.Column("status", sa.String(20), server_default="pending", index=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("assignments")
    op.drop_table("mentions")
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
    sa.Enum(name="notificationtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notificationpriority").drop(op.get_bind(), checkfirst=True)
