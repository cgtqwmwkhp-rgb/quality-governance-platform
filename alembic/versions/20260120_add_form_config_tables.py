"""Add form configuration tables for admin form builder.

Revision ID: 20260120_form_config
Revises: 20260120_tier2_ai_copilot_signatures
Create Date: 2026-01-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260120_form_config'
down_revision = '20260120_tier2_ai_copilot_signatures'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Form Templates table
    op.create_table(
        'form_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False, index=True),
        sa.Column('slug', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('form_type', sa.String(50), nullable=False, server_default='custom'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column('allow_drafts', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('allow_attachments', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('require_signature', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('auto_assign_reference', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('reference_prefix', sa.String(10), nullable=True),
        sa.Column('notify_on_submit', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notification_emails', sa.Text(), nullable=True),
        sa.Column('workflow_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Form Steps table
    op.create_table(
        'form_steps',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('form_templates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('show_condition', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_form_steps_template_id', 'form_steps', ['template_id'])

    # Form Fields table
    op.create_table(
        'form_fields',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('step_id', sa.Integer(), sa.ForeignKey('form_steps.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('label', sa.String(200), nullable=False),
        sa.Column('field_type', sa.String(50), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('placeholder', sa.String(300), nullable=True),
        sa.Column('help_text', sa.Text(), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('min_length', sa.Integer(), nullable=True),
        sa.Column('max_length', sa.Integer(), nullable=True),
        sa.Column('min_value', sa.Integer(), nullable=True),
        sa.Column('max_value', sa.Integer(), nullable=True),
        sa.Column('pattern', sa.String(500), nullable=True),
        sa.Column('default_value', sa.Text(), nullable=True),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('show_condition', sa.JSON(), nullable=True),
        sa.Column('width', sa.String(20), nullable=False, server_default='full'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_form_fields_step_id', 'form_fields', ['step_id'])

    # Contracts table
    op.create_table(
        'contracts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False, index=True),
        sa.Column('code', sa.String(50), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('client_name', sa.String(200), nullable=True),
        sa.Column('client_contact', sa.String(200), nullable=True),
        sa.Column('client_email', sa.String(200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # System Settings table
    op.create_table(
        'system_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('category', sa.String(50), nullable=False, server_default='general'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('value_type', sa.String(20), nullable=False, server_default='string'),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_editable', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Lookup Options table
    op.create_table(
        'lookup_options',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('category', sa.String(50), nullable=False, index=True),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('label', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('lookup_options.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Seed default contracts
    op.execute("""
        INSERT INTO contracts (name, code, client_name, display_order) VALUES
        ('UKPN', 'ukpn', 'UK Power Networks', 1),
        ('Openreach', 'openreach', 'BT Group', 2),
        ('Thames Water', 'thames-water', 'Thames Water Utilities', 3),
        ('Plantexpand Ltd', 'plantexpand', 'Internal', 4),
        ('Cadent', 'cadent', 'Cadent Gas', 5),
        ('SGN', 'sgn', 'Southern Gas Networks', 6),
        ('Southern Water', 'southern-water', 'Southern Water Services', 7),
        ('Zenith', 'zenith', 'Zenith Vehicle Solutions', 8),
        ('Novuna', 'novuna', 'Scottish Power', 9),
        ('Enterprise', 'enterprise', 'Enterprise Fleet Management', 10)
    """)

    # Seed default lookup options for roles
    op.execute("""
        INSERT INTO lookup_options (category, code, label, display_order) VALUES
        ('roles', 'mobile-engineer', 'Mobile Engineer', 1),
        ('roles', 'workshop-pehq', 'Workshop (PE HQ)', 2),
        ('roles', 'workshop-fixed', 'Vehicle Workshop (Fixed Customer Site)', 3),
        ('roles', 'office', 'Office Based Employee', 4),
        ('roles', 'trainee', 'Trainee/Apprentice', 5),
        ('roles', 'non-pe', 'Non-Plantexpand Employee', 6),
        ('roles', 'other', 'Other', 7)
    """)

    # Seed default lookup options for medical assistance
    op.execute("""
        INSERT INTO lookup_options (category, code, label, display_order) VALUES
        ('medical_assistance', 'none', 'No assistance needed', 1),
        ('medical_assistance', 'self', 'Self application', 2),
        ('medical_assistance', 'first-aider', 'First aider on site', 3),
        ('medical_assistance', 'ambulance', 'Ambulance / A&E', 4),
        ('medical_assistance', 'gp', 'GP / Hospital', 5)
    """)

    # Seed default system settings
    op.execute("""
        INSERT INTO system_settings (key, value, category, description, value_type, is_public) VALUES
        ('company_name', 'Plantexpand Ltd', 'branding', 'Company name displayed in the system', 'string', true),
        ('support_email', 'support@plantexpand.com', 'contact', 'Support email address', 'string', true),
        ('support_phone', '+44 1onal 234 567', 'contact', 'Support phone number', 'string', true),
        ('incident_notification_emails', 'safety@plantexpand.com', 'notifications', 'Emails notified on incident submission', 'string', false),
        ('auto_assign_incidents', 'true', 'workflow', 'Auto-assign incidents to safety team', 'boolean', false)
    """)


def downgrade() -> None:
    op.drop_table('lookup_options')
    op.drop_table('system_settings')
    op.drop_table('contracts')
    op.drop_table('form_fields')
    op.drop_table('form_steps')
    op.drop_table('form_templates')
