"""Add workflow persistence tables.

Revision ID: 20260220_workflow_persist
Revises: 20260220_compliance_auto
Create Date: 2026-02-20 14:00:00.000000

Creates tables for:
- workflow_templates
- workflow_instances
- workflow_steps
- approval_requests
- escalation_rules
- escalation_logs
- user_delegations
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260220_workflow_persist"
down_revision: Union[str, None] = "20260220_compliance_auto"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("trigger_entity_type", sa.String(50), nullable=False),
        sa.Column("trigger_conditions", sa.JSON(), nullable=True),
        sa.Column("auto_trigger", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("sla_hours", sa.Integer(), nullable=True),
        sa.Column("warning_hours", sa.Integer(), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("escalation_rules", sa.JSON(), nullable=True),
        sa.Column("notifications", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "workflow_instances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("workflow_templates.id"), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("current_step", sa.Integer(), server_default=sa.text("0")),
        sa.Column("current_step_name", sa.String(255), nullable=True),
        sa.Column("priority", sa.String(20), server_default="normal"),
        sa.Column("initiated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sla_due_at", sa.DateTime(), nullable=True),
        sa.Column("sla_warning_at", sa.DateTime(), nullable=True),
        sa.Column("sla_breached", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_instances_template_id", "workflow_instances", ["template_id"])
    op.create_index("ix_workflow_instances_entity_type", "workflow_instances", ["entity_type"])
    op.create_index("ix_workflow_instances_entity_id", "workflow_instances", ["entity_id"])
    op.create_index("ix_workflow_instances_status", "workflow_instances", ["status"])

    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "instance_id",
            sa.Integer(),
            sa.ForeignKey("workflow_instances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(255), nullable=False),
        sa.Column("step_type", sa.String(50), nullable=False),
        sa.Column("approval_type", sa.String(50), nullable=True),
        sa.Column("required_approvers", sa.JSON(), nullable=True),
        sa.Column("actual_approvers", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("outcome", sa.String(50), nullable=True),
        sa.Column("outcome_reason", sa.Text(), nullable=True),
        sa.Column("outcome_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("outcome_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_steps_instance_id", "workflow_steps", ["instance_id"])

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "step_id",
            sa.Integer(),
            sa.ForeignKey("workflow_steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("approver_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("delegated_to", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("delegated_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("response", sa.String(50), nullable=True),
        sa.Column("response_notes", sa.Text(), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("reminder_sent_at", sa.DateTime(), nullable=True),
        sa.Column("reminder_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_requests_step_id", "approval_requests", ["step_id"])
    op.create_index("ix_approval_requests_approver_id", "approval_requests", ["approver_id"])

    op.create_table(
        "escalation_rules_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("workflow_templates.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("trigger", sa.String(50), nullable=False),
        sa.Column("trigger_value", sa.Integer(), nullable=False),
        sa.Column("trigger_unit", sa.String(20), server_default="hours"),
        sa.Column("conditions", sa.JSON(), nullable=True),
        sa.Column("escalate_to_role", sa.String(100), nullable=True),
        sa.Column("escalate_to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actions", sa.JSON(), nullable=True),
        sa.Column("change_priority_to", sa.String(20), nullable=True),
        sa.Column("send_notification", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("notification_template", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_escalation_rules_config_template_id", "escalation_rules_config", ["template_id"])

    op.create_table(
        "escalation_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instance_id", sa.Integer(), sa.ForeignKey("workflow_instances.id"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("escalation_rules_config.id"), nullable=True),
        sa.Column("trigger", sa.String(50), nullable=False),
        sa.Column("from_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("to_role", sa.String(100), nullable=True),
        sa.Column("previous_priority", sa.String(20), nullable=True),
        sa.Column("new_priority", sa.String(20), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("escalated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_escalation_logs_instance_id", "escalation_logs", ["instance_id"])

    op.create_table(
        "user_delegations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("delegate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=False),
        sa.Column("delegate_all", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("workflow_types", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_delegations_user_id", "user_delegations", ["user_id"])
    op.create_index("ix_user_delegations_delegate_id", "user_delegations", ["delegate_id"])


def downgrade() -> None:
    op.drop_table("user_delegations")
    op.drop_table("escalation_logs")
    op.drop_table("escalation_rules_config")
    op.drop_table("approval_requests")
    op.drop_table("workflow_steps")
    op.drop_table("workflow_instances")
    op.drop_table("workflow_templates")
