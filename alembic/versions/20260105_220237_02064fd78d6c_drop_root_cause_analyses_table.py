"""drop_root_cause_analyses_table

Revision ID: 02064fd78d6c
Revises: ee405ad5e788
Create Date: 2026-01-05 22:02:37.781284+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02064fd78d6c'
down_revision: Union[str, None] = 'ee405ad5e788'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the root_cause_analyses table as RTA functionality is now part of Investigation system."""
    # Drop the table (CASCADE will drop dependent constraints)
    op.execute('DROP TABLE IF EXISTS root_cause_analyses CASCADE')


def downgrade() -> None:
    """Recreate the root_cause_analyses table if needed."""
    # Note: This is a breaking change, so downgrade recreates the table structure only
    # Data cannot be recovered after upgrade
    op.create_table(
        'root_cause_analyses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reference_number', sa.String(length=50), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('problem_statement', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('root_causes', sa.JSON(), nullable=True),
        sa.Column('corrective_actions', sa.JSON(), nullable=True),
        sa.Column('preventive_actions', sa.JSON(), nullable=True),
        sa.Column('timeline', sa.JSON(), nullable=True),
        sa.Column('team_members', sa.JSON(), nullable=True),
        sa.Column('attachments', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference_number')
    )
    op.create_index(op.f('ix_root_cause_analyses_incident_id'), 'root_cause_analyses', ['incident_id'], unique=False)
    op.create_index(op.f('ix_root_cause_analyses_reference_number'), 'root_cause_analyses', ['reference_number'], unique=False)
    op.create_index(op.f('ix_root_cause_analyses_status'), 'root_cause_analyses', ['status'], unique=False)
