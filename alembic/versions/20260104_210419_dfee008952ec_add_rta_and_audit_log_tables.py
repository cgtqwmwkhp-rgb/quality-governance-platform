"""add_rta_and_audit_log_tables

Revision ID: dfee008952ec
Revises: bdb09892867a
Create Date: 2026-01-04 21:04:19.284092+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dfee008952ec'
down_revision: Union[str, None] = 'bdb09892867a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create rcastatus enum type for Postgres
    # Note: SQLite ignores this and uses the Enum column as a check constraint
    op.execute("CREATE TYPE rcastatus AS ENUM ('draft', 'in_review', 'approved')")

    # Create root_cause_analyses table
    op.create_table(
        'root_cause_analyses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('problem_statement', sa.Text(), nullable=False),
        sa.Column('root_cause', sa.Text(), nullable=True),
        sa.Column('corrective_actions', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'in_review', 'approved', name='rcastatus'), nullable=False),
        sa.Column('reference_number', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_root_cause_analyses_reference_number'), 'root_cause_analyses', ['reference_number'], unique=True)
    op.create_index(op.f('ix_root_cause_analyses_title'), 'root_cause_analyses', ['title'], unique=False)


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index(op.f('ix_root_cause_analyses_title'), table_name='root_cause_analyses')
    op.drop_index(op.f('ix_root_cause_analyses_reference_number'), table_name='root_cause_analyses')
    op.drop_table('root_cause_analyses')
    op.execute("DROP TYPE rcastatus")
