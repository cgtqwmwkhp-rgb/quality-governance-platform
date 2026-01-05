"""Add investigation templates and runs

Revision ID: ee405ad5e788
Revises: dfee008952ec
Create Date: 2026-01-05 20:56:47.834376+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee405ad5e788'
down_revision: Union[str, None] = 'dfee008952ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create investigation_templates table
    op.create_table(
        'investigation_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.String(length=50), nullable=False, server_default='1.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('structure', sa.JSON(), nullable=False),
        sa.Column('applicable_entity_types', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_investigation_templates_id'), 'investigation_templates', ['id'], unique=False)
    op.create_index(op.f('ix_investigation_templates_name'), 'investigation_templates', ['name'], unique=False)

    # Create investigation_runs table
    op.create_table(
        'investigation_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('assigned_entity_type', sa.Enum('ROAD_TRAFFIC_COLLISION', 'REPORTING_INCIDENT', 'COMPLAINT', name='assignedentitytype'), nullable=False),
        sa.Column('assigned_entity_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'IN_PROGRESS', 'UNDER_REVIEW', 'COMPLETED', 'CLOSED', name='investigationstatus'), nullable=False, server_default='DRAFT'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('assigned_to_user_id', sa.Integer(), nullable=True),
        sa.Column('reviewer_user_id', sa.Integer(), nullable=True),
        sa.Column('reference_number', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['investigation_templates.id'], ),
        sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewer_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference_number')
    )
    op.create_index(op.f('ix_investigation_runs_id'), 'investigation_runs', ['id'], unique=False)
    op.create_index(op.f('ix_investigation_runs_template_id'), 'investigation_runs', ['template_id'], unique=False)
    op.create_index(op.f('ix_investigation_runs_assigned_entity_type'), 'investigation_runs', ['assigned_entity_type'], unique=False)
    op.create_index(op.f('ix_investigation_runs_assigned_entity_id'), 'investigation_runs', ['assigned_entity_id'], unique=False)
    op.create_index(op.f('ix_investigation_runs_reference_number'), 'investigation_runs', ['reference_number'], unique=True)


def downgrade() -> None:
    """Downgrade database schema."""
    # Drop investigation_runs table
    op.drop_index(op.f('ix_investigation_runs_reference_number'), table_name='investigation_runs')
    op.drop_index(op.f('ix_investigation_runs_assigned_entity_id'), table_name='investigation_runs')
    op.drop_index(op.f('ix_investigation_runs_assigned_entity_type'), table_name='investigation_runs')
    op.drop_index(op.f('ix_investigation_runs_template_id'), table_name='investigation_runs')
    op.drop_index(op.f('ix_investigation_runs_id'), table_name='investigation_runs')
    op.drop_table('investigation_runs')

    # Drop investigation_templates table
    op.drop_index(op.f('ix_investigation_templates_name'), table_name='investigation_templates')
    op.drop_index(op.f('ix_investigation_templates_id'), table_name='investigation_templates')
    op.drop_table('investigation_templates')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS investigationstatus')
    op.execute('DROP TYPE IF EXISTS assignedentitytype')
