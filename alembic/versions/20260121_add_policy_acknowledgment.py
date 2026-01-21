"""Add policy acknowledgment tables.

Revision ID: 20260121_policy_ack
Revises: 20260121_kri_sif
Create Date: 2026-01-21

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260121_policy_ack'
down_revision = '20260121_kri_sif'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Policy Acknowledgment Requirements table
    op.create_table(
        'policy_acknowledgment_requirements',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('policy_id', sa.Integer(), sa.ForeignKey('policies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('acknowledgment_type', sa.String(50), default='read_only'),
        sa.Column('required_for_all', sa.Boolean(), default=False),
        sa.Column('required_departments', sa.JSON(), nullable=True),
        sa.Column('required_roles', sa.JSON(), nullable=True),
        sa.Column('required_user_ids', sa.JSON(), nullable=True),
        sa.Column('due_within_days', sa.Integer(), default=30),
        sa.Column('reminder_days_before', sa.JSON(), nullable=True),
        sa.Column('re_acknowledge_on_update', sa.Boolean(), default=True),
        sa.Column('re_acknowledge_period_months', sa.Integer(), nullable=True),
        sa.Column('quiz_questions', sa.JSON(), nullable=True),
        sa.Column('quiz_passing_score', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_policy_ack_req_policy_id', 'policy_acknowledgment_requirements', ['policy_id'])

    # Policy Acknowledgments table
    op.create_table(
        'policy_acknowledgments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('requirement_id', sa.Integer(), sa.ForeignKey('policy_acknowledgment_requirements.id', ondelete='CASCADE'), nullable=False),
        sa.Column('policy_id', sa.Integer(), sa.ForeignKey('policies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('policy_version', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('time_spent_seconds', sa.Integer(), nullable=True),
        sa.Column('quiz_score', sa.Integer(), nullable=True),
        sa.Column('quiz_attempts', sa.Integer(), default=0),
        sa.Column('quiz_passed', sa.Boolean(), nullable=True),
        sa.Column('acceptance_statement', sa.Text(), nullable=True),
        sa.Column('signature_data', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('reminders_sent', sa.Integer(), default=0),
        sa.Column('last_reminder_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_policy_ack_requirement_id', 'policy_acknowledgments', ['requirement_id'])
    op.create_index('ix_policy_ack_policy_id', 'policy_acknowledgments', ['policy_id'])
    op.create_index('ix_policy_ack_user_id', 'policy_acknowledgments', ['user_id'])
    op.create_index('ix_policy_ack_due_date', 'policy_acknowledgments', ['due_date'])
    op.create_index('ix_policy_ack_status', 'policy_acknowledgments', ['status'])

    # Document Read Logs table
    op.create_table(
        'document_read_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_type', sa.String(50), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('document_version', sa.String(50), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('accessed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('scroll_percentage', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('device_type', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_doc_read_log_doc_type', 'document_read_logs', ['document_type'])
    op.create_index('ix_doc_read_log_doc_id', 'document_read_logs', ['document_id'])
    op.create_index('ix_doc_read_log_user_id', 'document_read_logs', ['user_id'])
    op.create_index('ix_doc_read_log_accessed_at', 'document_read_logs', ['accessed_at'])


def downgrade() -> None:
    op.drop_table('document_read_logs')
    op.drop_table('policy_acknowledgments')
    op.drop_table('policy_acknowledgment_requirements')
