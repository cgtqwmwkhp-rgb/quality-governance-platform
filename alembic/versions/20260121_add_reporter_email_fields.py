"""Add reporter_email fields for portal tracking.

Revision ID: add_reporter_email_01
Revises: 
Create Date: 2026-01-21 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_reporter_email_01'
down_revision: Union[str, None] = '20260121_rca_competence'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add reporter_email and reporter_name fields for portal user tracking."""
    
    # Add reporter_email and reporter_name to incidents table
    op.add_column('incidents', sa.Column('reporter_email', sa.String(255), nullable=True))
    op.add_column('incidents', sa.Column('reporter_name', sa.String(255), nullable=True))
    op.create_index('ix_incidents_reporter_email', 'incidents', ['reporter_email'])
    
    # Add reporter_email, reporter_name, and driver_email to road_traffic_collisions table
    op.add_column('road_traffic_collisions', sa.Column('reporter_email', sa.String(255), nullable=True))
    op.add_column('road_traffic_collisions', sa.Column('reporter_name', sa.String(255), nullable=True))
    op.add_column('road_traffic_collisions', sa.Column('driver_email', sa.String(255), nullable=True))
    op.create_index('ix_road_traffic_collisions_reporter_email', 'road_traffic_collisions', ['reporter_email'])
    op.create_index('ix_road_traffic_collisions_driver_email', 'road_traffic_collisions', ['driver_email'])


def downgrade() -> None:
    """Remove reporter_email and reporter_name fields."""
    
    # Remove from road_traffic_collisions
    op.drop_index('ix_road_traffic_collisions_driver_email', table_name='road_traffic_collisions')
    op.drop_index('ix_road_traffic_collisions_reporter_email', table_name='road_traffic_collisions')
    op.drop_column('road_traffic_collisions', 'driver_email')
    op.drop_column('road_traffic_collisions', 'reporter_name')
    op.drop_column('road_traffic_collisions', 'reporter_email')
    
    # Remove from incidents
    op.drop_index('ix_incidents_reporter_email', table_name='incidents')
    op.drop_column('incidents', 'reporter_name')
    op.drop_column('incidents', 'reporter_email')
