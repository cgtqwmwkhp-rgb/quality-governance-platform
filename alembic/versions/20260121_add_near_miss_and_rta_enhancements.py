"""Add Near Miss table and RTA enhancements.

Revision ID: 20260121_near_miss_rta
Revises: 20260120_add_form_config_tables
Create Date: 2026-01-21

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '20260121_near_miss_rta'
down_revision = '20260120_form_config'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create Near Misses table
    op.create_table(
        'near_misses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('reference_number', sa.String(50), nullable=False, unique=True, index=True),
        
        # Reporter information
        sa.Column('reporter_name', sa.String(200), nullable=False),
        sa.Column('reporter_email', sa.String(255), nullable=True),
        sa.Column('reporter_phone', sa.String(50), nullable=True),
        sa.Column('reporter_role', sa.String(100), nullable=True),
        sa.Column('was_involved', sa.Boolean(), default=True),
        
        # Contract/Location
        sa.Column('contract', sa.String(100), nullable=False),
        sa.Column('contract_other', sa.String(200), nullable=True),
        sa.Column('location', sa.Text(), nullable=False),
        sa.Column('location_coordinates', sa.String(100), nullable=True),
        
        # Event details
        sa.Column('event_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_time', sa.String(10), nullable=True),
        
        # Description
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('potential_consequences', sa.Text(), nullable=True),
        sa.Column('preventive_action_suggested', sa.Text(), nullable=True),
        
        # People involved
        sa.Column('persons_involved', sa.Text(), nullable=True),
        sa.Column('witnesses_present', sa.Boolean(), default=False),
        sa.Column('witness_names', sa.Text(), nullable=True),
        
        # Asset information
        sa.Column('asset_number', sa.String(100), nullable=True),
        sa.Column('asset_type', sa.String(100), nullable=True),
        
        # Risk assessment
        sa.Column('risk_category', sa.String(50), nullable=True),
        sa.Column('potential_severity', sa.String(20), nullable=True),
        
        # Attachments
        sa.Column('attachments', sa.Text(), nullable=True),
        
        # Status workflow
        sa.Column('status', sa.String(50), default='REPORTED', nullable=False),
        sa.Column('priority', sa.String(20), default='MEDIUM', nullable=False),
        
        # Assignment
        sa.Column('assigned_to_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        
        # Resolution
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('corrective_actions_taken', sa.Text(), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        
        # Audit fields
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Add indexes for common queries
    op.create_index('ix_near_misses_status', 'near_misses', ['status'])
    op.create_index('ix_near_misses_contract', 'near_misses', ['contract'])
    op.create_index('ix_near_misses_event_date', 'near_misses', ['event_date'])
    
    # Add RTA enhancements
    op.add_column('road_traffic_collisions', sa.Column('vehicles_involved_count', sa.Integer(), default=2, nullable=False, server_default='2'))
    op.add_column('road_traffic_collisions', sa.Column('cctv_available', sa.Boolean(), default=False, nullable=False, server_default='false'))
    op.add_column('road_traffic_collisions', sa.Column('cctv_location', sa.String(300), nullable=True))
    op.add_column('road_traffic_collisions', sa.Column('dashcam_footage_available', sa.Boolean(), default=False, nullable=False, server_default='false'))
    op.add_column('road_traffic_collisions', sa.Column('footage_secured', sa.Boolean(), default=False, nullable=False, server_default='false'))
    op.add_column('road_traffic_collisions', sa.Column('footage_notes', sa.Text(), nullable=True))
    op.add_column('road_traffic_collisions', sa.Column('witnesses_structured', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove RTA enhancements
    op.drop_column('road_traffic_collisions', 'witnesses_structured')
    op.drop_column('road_traffic_collisions', 'footage_notes')
    op.drop_column('road_traffic_collisions', 'footage_secured')
    op.drop_column('road_traffic_collisions', 'dashcam_footage_available')
    op.drop_column('road_traffic_collisions', 'cctv_location')
    op.drop_column('road_traffic_collisions', 'cctv_available')
    op.drop_column('road_traffic_collisions', 'vehicles_involved_count')
    
    # Drop indexes
    op.drop_index('ix_near_misses_event_date', table_name='near_misses')
    op.drop_index('ix_near_misses_contract', table_name='near_misses')
    op.drop_index('ix_near_misses_status', table_name='near_misses')
    
    # Drop Near Misses table
    op.drop_table('near_misses')
