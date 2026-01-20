"""Tier 1 Enterprise Features Migration

Add tables for:
- Multi-tenancy (tenants, tenant_users, invitations)
- Advanced permissions (ABAC policies, roles, field-level permissions)
- Immutable audit trail (hash chain logging)
- Real-time collaboration (documents, sessions, comments)

Revision ID: tier1_enterprise_v1
Revises: previous_migration
Create Date: 2026-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'tier1_enterprise_v1'
down_revision = None  # Set to actual previous revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # Multi-Tenancy Tables
    # =========================================================================
    
    op.create_table(
        'tenants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('domain', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('subscription_tier', sa.String(50), default='standard'),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('favicon_url', sa.String(500), nullable=True),
        sa.Column('primary_color', sa.String(7), default='#3B82F6'),
        sa.Column('secondary_color', sa.String(7), default='#10B981'),
        sa.Column('accent_color', sa.String(7), default='#8B5CF6'),
        sa.Column('theme_mode', sa.String(20), default='dark'),
        sa.Column('custom_css', sa.Text(), nullable=True),
        sa.Column('admin_email', sa.String(255), nullable=False),
        sa.Column('support_email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('address_line1', sa.String(255), nullable=True),
        sa.Column('address_line2', sa.String(255), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('postal_code', sa.String(20), nullable=True),
        sa.Column('country', sa.String(100), default='United Kingdom'),
        sa.Column('settings', sa.JSON(), default=dict),
        sa.Column('features_enabled', sa.JSON(), default=dict),
        sa.Column('max_users', sa.Integer(), default=50),
        sa.Column('max_storage_gb', sa.Integer(), default=10),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('trial_ends_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
        sa.UniqueConstraint('domain'),
    )
    op.create_index('ix_tenants_slug', 'tenants', ['slug'])
    
    op.create_table(
        'tenant_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(50), default='user'),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_primary', sa.Boolean(), default=False),
        sa.Column('custom_permissions', sa.JSON(), default=dict),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    
    op.create_table(
        'tenant_invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), default='user'),
        sa.Column('token', sa.String(255), nullable=False),
        sa.Column('invited_by_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['invited_by_id'], ['users.id']),
    )
    
    # =========================================================================
    # ABAC Permission Tables
    # =========================================================================
    
    op.create_table(
        'permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('allowed_fields', sa.JSON(), nullable=True),
        sa.Column('restricted_fields', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_system', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('ix_permissions_code', 'permissions', ['code'])
    
    op.create_table(
        'abac_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('code', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_role_id', sa.Integer(), nullable=True),
        sa.Column('hierarchy_level', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_system', sa.Boolean(), default=False),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['parent_role_id'], ['abac_roles.id']),
    )
    
    op.create_table(
        'abac_role_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['role_id'], ['abac_roles.id']),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id']),
    )
    
    op.create_table(
        'abac_user_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('scope', sa.JSON(), nullable=True),
        sa.Column('valid_from', sa.DateTime(), nullable=False),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('granted_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['granted_by_id'], ['users.id']),
    )
    op.create_index('ix_abac_user_roles_user', 'abac_user_roles', ['user_id'])
    op.create_index('ix_abac_user_roles_tenant', 'abac_user_roles', ['tenant_id'])
    
    op.create_table(
        'abac_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('effect', sa.String(10), default='allow'),
        sa.Column('priority', sa.Integer(), default=0),
        sa.Column('subject_conditions', sa.JSON(), default=dict),
        sa.Column('resource_conditions', sa.JSON(), default=dict),
        sa.Column('environment_conditions', sa.JSON(), default=dict),
        sa.Column('allowed_fields', sa.JSON(), nullable=True),
        sa.Column('denied_fields', sa.JSON(), nullable=True),
        sa.Column('obligations', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
    )
    op.create_index('ix_abac_policy_resource', 'abac_policies', ['resource_type', 'action'])
    
    op.create_table(
        'field_level_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('access_level', sa.String(20), default='read'),
        sa.Column('role_codes', sa.JSON(), nullable=True),
        sa.Column('user_attributes', sa.JSON(), nullable=True),
        sa.Column('mask_type', sa.String(50), nullable=True),
        sa.Column('mask_pattern', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
    )
    
    op.create_table(
        'permission_audits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('decision', sa.String(10), nullable=False),
        sa.Column('matched_policy_id', sa.Integer(), nullable=True),
        sa.Column('subject_attributes', sa.JSON(), default=dict),
        sa.Column('resource_attributes', sa.JSON(), default=dict),
        sa.Column('environment_attributes', sa.JSON(), default=dict),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['matched_policy_id'], ['abac_policies.id']),
    )
    
    # =========================================================================
    # Audit Log Tables (Blockchain-style)
    # =========================================================================
    
    op.create_table(
        'audit_log_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('entry_hash', sa.String(64), nullable=False),
        sa.Column('previous_hash', sa.String(64), nullable=False),
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('entity_id', sa.String(100), nullable=False),
        sa.Column('entity_name', sa.String(255), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('action_category', sa.String(50), default='data'),
        sa.Column('old_values', sa.JSON(), nullable=True),
        sa.Column('new_values', sa.JSON(), nullable=True),
        sa.Column('changed_fields', sa.JSON(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('user_email', sa.String(255), nullable=True),
        sa.Column('user_name', sa.String(255), nullable=True),
        sa.Column('user_role', sa.String(50), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('geo_country', sa.String(100), nullable=True),
        sa.Column('geo_city', sa.String(100), nullable=True),
        sa.Column('entry_metadata', sa.JSON(), default=dict),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('is_sensitive', sa.Boolean(), default=False),
        sa.Column('retention_days', sa.Integer(), default=2555),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entry_hash'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index('ix_audit_log_entity', 'audit_log_entries', ['entity_type', 'entity_id'])
    op.create_index('ix_audit_log_user', 'audit_log_entries', ['user_id', 'timestamp'])
    op.create_index('ix_audit_log_tenant', 'audit_log_entries', ['tenant_id', 'timestamp'])
    op.create_index('ix_audit_log_action', 'audit_log_entries', ['action', 'timestamp'])
    
    op.create_table(
        'audit_log_verifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('start_sequence', sa.Integer(), nullable=False),
        sa.Column('end_sequence', sa.Integer(), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False),
        sa.Column('entries_verified', sa.Integer(), nullable=False),
        sa.Column('invalid_entries', sa.JSON(), nullable=True),
        sa.Column('merkle_root', sa.String(64), nullable=True),
        sa.Column('verified_by_id', sa.Integer(), nullable=True),
        sa.Column('verification_method', sa.String(50), default='hash_chain'),
        sa.Column('verified_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['verified_by_id'], ['users.id']),
    )
    
    op.create_table(
        'audit_log_exports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('export_format', sa.String(20), nullable=False),
        sa.Column('export_type', sa.String(50), nullable=False),
        sa.Column('filters', sa.JSON(), default=dict),
        sa.Column('date_from', sa.DateTime(), nullable=True),
        sa.Column('date_to', sa.DateTime(), nullable=True),
        sa.Column('entries_exported', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_hash', sa.String(64), nullable=True),
        sa.Column('exported_by_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.Column('exported_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['exported_by_id'], ['users.id']),
    )
    
    # =========================================================================
    # Collaboration Tables
    # =========================================================================
    
    op.create_table(
        'collaborative_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('entity_id', sa.String(100), nullable=False),
        sa.Column('field_name', sa.String(100), default='content'),
        sa.Column('yjs_state', sa.LargeBinary(), nullable=True),
        sa.Column('yjs_state_vector', sa.LargeBinary(), nullable=True),
        sa.Column('version', sa.Integer(), default=0),
        sa.Column('last_snapshot', sa.LargeBinary(), nullable=True),
        sa.Column('last_snapshot_at', sa.DateTime(), nullable=True),
        sa.Column('is_locked', sa.Boolean(), default=False),
        sa.Column('locked_by_id', sa.Integer(), nullable=True),
        sa.Column('locked_at', sa.DateTime(), nullable=True),
        sa.Column('lock_reason', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['locked_by_id'], ['users.id']),
    )
    op.create_index('ix_collab_doc_entity', 'collaborative_documents', ['entity_type', 'entity_id'])
    
    op.create_table(
        'collaborative_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(100), nullable=False),
        sa.Column('user_name', sa.String(255), nullable=False),
        sa.Column('user_email', sa.String(255), nullable=False),
        sa.Column('user_avatar', sa.String(500), nullable=True),
        sa.Column('user_color', sa.String(7), default='#3B82F6'),
        sa.Column('cursor_position', sa.JSON(), nullable=True),
        sa.Column('selection_range', sa.JSON(), nullable=True),
        sa.Column('current_field', sa.String(100), nullable=True),
        sa.Column('is_editing', sa.Boolean(), default=False),
        sa.Column('is_typing', sa.Boolean(), default=False),
        sa.Column('connection_id', sa.String(100), nullable=True),
        sa.Column('client_version', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('left_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id'),
        sa.ForeignKeyConstraint(['document_id'], ['collaborative_documents.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index('ix_collab_session_active', 'collaborative_sessions', ['is_active', 'last_seen_at'])
    
    op.create_table(
        'collaborative_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('change_type', sa.String(50), nullable=False),
        sa.Column('change_data', sa.JSON(), nullable=False),
        sa.Column('path', sa.String(500), nullable=True),
        sa.Column('offset', sa.Integer(), nullable=True),
        sa.Column('length', sa.Integer(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['collaborative_documents.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index('ix_collab_change_doc', 'collaborative_changes', ['document_id', 'created_at'])
    
    op.create_table(
        'document_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('entity_id', sa.String(100), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('thread_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_html', sa.Text(), nullable=True),
        sa.Column('anchor_path', sa.String(500), nullable=True),
        sa.Column('anchor_offset', sa.Integer(), nullable=True),
        sa.Column('anchor_length', sa.Integer(), nullable=True),
        sa.Column('quoted_text', sa.Text(), nullable=True),
        sa.Column('mentions', sa.JSON(), nullable=True),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('author_name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(20), default='open'),
        sa.Column('resolved_by_id', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('reactions', sa.JSON(), default=dict),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), default=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['parent_id'], ['document_comments.id']),
        sa.ForeignKeyConstraint(['author_id'], ['users.id']),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id']),
    )
    
    op.create_table(
        'user_presence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), default='online'),
        sa.Column('custom_status', sa.String(255), nullable=True),
        sa.Column('current_page', sa.String(255), nullable=True),
        sa.Column('current_entity_type', sa.String(100), nullable=True),
        sa.Column('current_entity_id', sa.String(100), nullable=True),
        sa.Column('device_type', sa.String(50), nullable=True),
        sa.Column('browser', sa.String(100), nullable=True),
        sa.Column('connection_count', sa.Integer(), default=1),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('went_away_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('user_presence')
    op.drop_table('document_comments')
    op.drop_table('collaborative_changes')
    op.drop_table('collaborative_sessions')
    op.drop_table('collaborative_documents')
    op.drop_table('audit_log_exports')
    op.drop_table('audit_log_verifications')
    op.drop_table('audit_log_entries')
    op.drop_table('permission_audits')
    op.drop_table('field_level_permissions')
    op.drop_table('abac_policies')
    op.drop_table('abac_user_roles')
    op.drop_table('abac_role_permissions')
    op.drop_table('abac_roles')
    op.drop_table('permissions')
    op.drop_table('tenant_invitations')
    op.drop_table('tenant_users')
    op.drop_table('tenants')
