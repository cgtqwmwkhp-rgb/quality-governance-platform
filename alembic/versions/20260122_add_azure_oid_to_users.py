"""Add azure_oid column to users table for Azure AD identity linking.

Revision ID: 20260122_azure_oid
Revises: add_reporter_email_01
Create Date: 2026-01-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260122_azure_oid'
down_revision: Union[str, None] = 'add_reporter_email_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add azure_oid column to users table for Azure AD SSO integration.
    
    This column stores the Azure AD Object ID (oid claim) which uniquely
    identifies users across Azure AD tenants. Used for token exchange
    and SSO-based user lookup.
    """
    # Add azure_oid column - nullable to support existing users
    op.add_column(
        'users',
        sa.Column('azure_oid', sa.String(36), nullable=True)
    )
    
    # Create index for efficient lookup by azure_oid
    op.create_index(
        'ix_users_azure_oid',
        'users',
        ['azure_oid'],
        unique=False  # Not unique - allows null and edge cases
    )


def downgrade() -> None:
    """Remove azure_oid column from users table."""
    op.drop_index('ix_users_azure_oid', table_name='users')
    op.drop_column('users', 'azure_oid')
