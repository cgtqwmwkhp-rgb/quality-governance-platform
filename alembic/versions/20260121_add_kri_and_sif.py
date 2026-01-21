"""Add KRI tables and SIF classification fields.

Revision ID: 20260121_kri_sif
Revises: 20260121_workflow_engine
Create Date: 2026-01-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260121_kri_sif'
down_revision = '20260121_workflow_engine'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Key Risk Indicators table
    op.create_table(
        'key_risk_indicators',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('unit', sa.String(50), nullable=False),
        sa.Column('measurement_frequency', sa.String(50), default='monthly'),
        sa.Column('data_source', sa.String(100), nullable=False),
        sa.Column('calculation_method', sa.Text(), nullable=True),
        sa.Column('auto_calculate', sa.Boolean(), default=True),
        sa.Column('lower_is_better', sa.Boolean(), default=True),
        sa.Column('green_threshold', sa.Float(), nullable=False),
        sa.Column('amber_threshold', sa.Float(), nullable=False),
        sa.Column('red_threshold', sa.Float(), nullable=False),
        sa.Column('current_value', sa.Float(), nullable=True),
        sa.Column('current_status', sa.String(20), nullable=True),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trend_direction', sa.String(20), nullable=True),
        sa.Column('linked_risk_ids', sa.JSON(), nullable=True),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('ix_key_risk_indicators_code', 'key_risk_indicators', ['code'])
    op.create_index('ix_key_risk_indicators_name', 'key_risk_indicators', ['name'])
    op.create_index('ix_key_risk_indicators_category', 'key_risk_indicators', ['category'])

    # KRI Measurements table
    op.create_table(
        'kri_measurements',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('kri_id', sa.Integer(), sa.ForeignKey('key_risk_indicators.id', ondelete='CASCADE'), nullable=False),
        sa.Column('measurement_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('source_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_kri_measurements_kri_id', 'kri_measurements', ['kri_id'])
    op.create_index('ix_kri_measurements_date', 'kri_measurements', ['measurement_date'])

    # KRI Alerts table
    op.create_table(
        'kri_alerts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('kri_id', sa.Integer(), sa.ForeignKey('key_risk_indicators.id', ondelete='CASCADE'), nullable=False),
        sa.Column('alert_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('trigger_value', sa.Float(), nullable=False),
        sa.Column('previous_value', sa.Float(), nullable=True),
        sa.Column('threshold_breached', sa.Float(), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_acknowledged', sa.Boolean(), default=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('acknowledgment_notes', sa.Text(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), default=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_kri_alerts_kri_id', 'kri_alerts', ['kri_id'])

    # Risk Score History table
    op.create_table(
        'risk_score_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('risk_id', sa.Integer(), sa.ForeignKey('risks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('likelihood', sa.Integer(), nullable=False),
        sa.Column('impact', sa.Integer(), nullable=False),
        sa.Column('risk_score', sa.Integer(), nullable=False),
        sa.Column('risk_level', sa.String(50), nullable=False),
        sa.Column('trigger_type', sa.String(50), nullable=False),
        sa.Column('trigger_entity_type', sa.String(50), nullable=True),
        sa.Column('trigger_entity_id', sa.Integer(), nullable=True),
        sa.Column('previous_score', sa.Integer(), nullable=True),
        sa.Column('score_change', sa.Integer(), nullable=True),
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_risk_score_history_risk_id', 'risk_score_history', ['risk_id'])
    op.create_index('ix_risk_score_history_recorded_at', 'risk_score_history', ['recorded_at'])

    # Add SIF/pSIF classification fields to incidents table (if table exists)
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'incidents' in existing_tables:
        op.add_column('incidents', sa.Column('is_sif', sa.Boolean(), default=False, nullable=True))
        op.add_column('incidents', sa.Column('is_psif', sa.Boolean(), default=False, nullable=True))
        op.add_column('incidents', sa.Column('sif_classification', sa.String(50), nullable=True))
        op.add_column('incidents', sa.Column('sif_assessment_date', sa.DateTime(timezone=True), nullable=True))
        op.add_column('incidents', sa.Column('sif_assessed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
        op.add_column('incidents', sa.Column('sif_rationale', sa.Text(), nullable=True))
        op.add_column('incidents', sa.Column('life_altering_potential', sa.Boolean(), default=False, nullable=True))
        op.add_column('incidents', sa.Column('precursor_events', sa.JSON(), nullable=True))
        op.add_column('incidents', sa.Column('control_failures', sa.JSON(), nullable=True))
    
    # Add linked_risk_ids to near_misses if table exists
    if 'near_misses' in existing_tables:
        op.add_column('near_misses', sa.Column('linked_risk_ids', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove SIF fields from incidents (if table exists)
    from sqlalchemy import inspect
    
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'incidents' in existing_tables:
        for col in ['is_sif', 'is_psif', 'sif_classification', 'sif_assessment_date', 
                    'sif_assessed_by_id', 'sif_rationale', 'life_altering_potential',
                    'precursor_events', 'control_failures']:
            try:
                op.drop_column('incidents', col)
            except Exception:
                pass
    
    # Remove linked_risk_ids from near_misses (if table exists)
    if 'near_misses' in existing_tables:
        try:
            op.drop_column('near_misses', 'linked_risk_ids')
        except Exception:
            pass
    
    # Drop tables
    op.drop_table('risk_score_history')
    op.drop_table('kri_alerts')
    op.drop_table('kri_measurements')
    op.drop_table('key_risk_indicators')
