"""Seed default tenant when tenants table is empty.

Production databases created via schema-only migrations have no tenant rows,
which blocks every feature that requires tenant context (e.g. external audit
imports).  This data migration inserts a sensible default only when the table
is empty, so it is safe to run on databases that already have tenants.

Revision ID: b7e8f9a0c1d2
Revises: a3f1b2c4d5e6
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa

revision = "b7e8f9a0c1d2"
down_revision = "a3f1b2c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    count = conn.execute(sa.text("SELECT COUNT(*) FROM tenants")).scalar()
    if count == 0:
        conn.execute(
            sa.text(
                """
                INSERT INTO tenants (
                    name, slug, admin_email, is_active,
                    subscription_tier, primary_color, secondary_color,
                    accent_color, theme_mode, country, max_users,
                    max_storage_gb, created_at, updated_at
                ) VALUES (
                    'Default Organisation', 'default', 'admin@qgp.local', true,
                    'enterprise', '#3B82F6', '#10B981',
                    '#8B5CF6', 'dark', 'United Kingdom', 50,
                    10, NOW(), NOW()
                )
                """
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM tenants WHERE slug = 'default'"))
