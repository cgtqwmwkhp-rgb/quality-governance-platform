"""Add workflow engine tables.

Revision ID: 20260121_workflow_engine
Revises: 20260121_near_miss_rta
Create Date: 2026-01-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260121_workflow_engine'
down_revision = '20260121_near_miss_rta'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Workflow Rules table
    op.create_table(
        'workflow_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rule_type', sa.String(50), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('trigger_event', sa.String(50), nullable=False),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('delay_hours', sa.Float(), nullable=True),
        sa.Column('delay_from_field', sa.String(100), nullable=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('action_config', sa.JSON(), nullable=False),
        sa.Column('priority', sa.Integer(), default=100),
        sa.Column('stop_processing', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('contract', sa.String(100), nullable=True),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workflow_rules_name', 'workflow_rules', ['name'])
    op.create_index('ix_workflow_rules_entity_type', 'workflow_rules', ['entity_type'])
    op.create_index('ix_workflow_rules_is_active', 'workflow_rules', ['is_active'])

    # Rule Executions table
    op.create_table(
        'rule_executions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rule_id', sa.Integer(), sa.ForeignKey('workflow_rules.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('trigger_event', sa.String(50), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('success', sa.Boolean(), default=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('action_taken', sa.Text(), nullable=True),
        sa.Column('action_result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rule_executions_rule_id', 'rule_executions', ['rule_id'])
    op.create_index('ix_rule_executions_entity_type', 'rule_executions', ['entity_type'])
    op.create_index('ix_rule_executions_entity_id', 'rule_executions', ['entity_id'])
    op.create_index('ix_rule_executions_executed_at', 'rule_executions', ['executed_at'])

    # SLA Configurations table
    op.create_table(
        'sla_configurations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('priority', sa.String(50), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('contract', sa.String(100), nullable=True),
        sa.Column('acknowledgment_hours', sa.Float(), nullable=True),
        sa.Column('response_hours', sa.Float(), nullable=True),
        sa.Column('resolution_hours', sa.Float(), nullable=False),
        sa.Column('warning_threshold_percent', sa.Integer(), default=75),
        sa.Column('business_hours_only', sa.Boolean(), default=True),
        sa.Column('business_start_hour', sa.Integer(), default=9),
        sa.Column('business_end_hour', sa.Integer(), default=17),
        sa.Column('exclude_weekends', sa.Boolean(), default=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('match_priority', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sla_configurations_entity_type', 'sla_configurations', ['entity_type'])

    # SLA Tracking table
    op.create_table(
        'sla_tracking',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('sla_config_id', sa.Integer(), sa.ForeignKey('sla_configurations.id'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledgment_due', sa.DateTime(timezone=True), nullable=True),
        sa.Column('response_due', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_due', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledgment_met', sa.Boolean(), nullable=True),
        sa.Column('response_met', sa.Boolean(), nullable=True),
        sa.Column('resolution_met', sa.Boolean(), nullable=True),
        sa.Column('warning_sent', sa.Boolean(), default=False),
        sa.Column('breach_sent', sa.Boolean(), default=False),
        sa.Column('is_breached', sa.Boolean(), default=False),
        sa.Column('is_paused', sa.Boolean(), default=False),
        sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_paused_hours', sa.Float(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sla_tracking_entity_type', 'sla_tracking', ['entity_type'])
    op.create_index('ix_sla_tracking_entity_id', 'sla_tracking', ['entity_id'])
    op.create_index('ix_sla_tracking_is_breached', 'sla_tracking', ['is_breached'])

    # Escalation Levels table
    op.create_table(
        'escalation_levels',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('escalate_to_role', sa.String(100), nullable=True),
        sa.Column('escalate_to_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('notification_template', sa.String(100), nullable=True),
        sa.Column('notify_original_assignee', sa.Boolean(), default=True),
        sa.Column('notify_reporter', sa.Boolean(), default=False),
        sa.Column('hours_after_previous', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_escalation_levels_entity_type', 'escalation_levels', ['entity_type'])
    op.create_index('ix_escalation_levels_level', 'escalation_levels', ['level'])

    # Add escalation_level column to main entity tables
    op.add_column('incidents', sa.Column('escalation_level', sa.Integer(), default=0, nullable=True))
    op.add_column('complaints', sa.Column('escalation_level', sa.Integer(), default=0, nullable=True))
    op.add_column('near_misses', sa.Column('escalation_level', sa.Integer(), default=0, nullable=True))
    op.add_column('rtas', sa.Column('escalation_level', sa.Integer(), default=0, nullable=True))


def downgrade() -> None:
    # Remove escalation_level columns
    op.drop_column('incidents', 'escalation_level')
    op.drop_column('complaints', 'escalation_level')
    op.drop_column('near_misses', 'escalation_level')
    op.drop_column('rtas', 'escalation_level')

    # Drop tables
    op.drop_table('escalation_levels')
    op.drop_table('sla_tracking')
    op.drop_table('sla_configurations')
    op.drop_table('rule_executions')
    op.drop_table('workflow_rules')
