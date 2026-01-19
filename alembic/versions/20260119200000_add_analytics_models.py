"""Add analytics models

Revision ID: 20260119200000
Revises: 20260119150000
Create Date: 2026-01-19 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260119200000'
down_revision = '20260118220000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Dashboards table
    op.create_table(
        'dashboards',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('is_shared', sa.Boolean(), default=False),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column('layout', sa.JSON(), nullable=True),
        sa.Column('default_filters', sa.JSON(), nullable=True),
        sa.Column('default_time_range', sa.String(50), default='last_30_days'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Dashboard widgets table
    op.create_table(
        'dashboard_widgets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dashboard_id', sa.Integer(), nullable=False),
        sa.Column('widget_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('data_source', sa.String(50), nullable=False),
        sa.Column('metric', sa.String(100), nullable=False),
        sa.Column('aggregation', sa.String(50), default='count'),
        sa.Column('group_by', sa.String(100), nullable=True),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('chart_options', sa.JSON(), nullable=True),
        sa.Column('colors', sa.JSON(), nullable=True),
        sa.Column('grid_x', sa.Integer(), default=0),
        sa.Column('grid_y', sa.Integer(), default=0),
        sa.Column('grid_w', sa.Integer(), default=4),
        sa.Column('grid_h', sa.Integer(), default=3),
        sa.Column('drill_down_enabled', sa.Boolean(), default=True),
        sa.Column('drill_down_config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['dashboard_id'], ['dashboards.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_dashboard_widgets_dashboard_id', 'dashboard_widgets', ['dashboard_id'])

    # Saved reports table
    op.create_table(
        'saved_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('dashboard_id', sa.Integer(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('is_scheduled', sa.Boolean(), default=False),
        sa.Column('schedule_cron', sa.String(100), nullable=True),
        sa.Column('schedule_timezone', sa.String(50), default='UTC'),
        sa.Column('recipients', sa.JSON(), nullable=True),
        sa.Column('send_email', sa.Boolean(), default=True),
        sa.Column('output_format', sa.String(20), default='pdf'),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_run_status', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.ForeignKeyConstraint(['dashboard_id'], ['dashboards.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Benchmark data table
    op.create_table(
        'benchmark_data',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('metric', sa.String(100), nullable=False),
        sa.Column('industry', sa.String(100), nullable=False),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('company_size', sa.String(50), nullable=True),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('percentile_25', sa.Float(), nullable=True),
        sa.Column('percentile_50', sa.Float(), nullable=True),
        sa.Column('percentile_75', sa.Float(), nullable=True),
        sa.Column('percentile_90', sa.Float(), nullable=True),
        sa.Column('sample_size', sa.Integer(), nullable=True),
        sa.Column('data_year', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(255), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_benchmark_data_category', 'benchmark_data', ['category'])
    op.create_index('ix_benchmark_data_metric', 'benchmark_data', ['metric'])
    op.create_index('ix_benchmark_data_industry', 'benchmark_data', ['industry'])

    # Cost records table
    op.create_table(
        'cost_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.String(36), nullable=False),
        sa.Column('cost_category', sa.String(100), nullable=False),
        sa.Column('cost_type', sa.String(100), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(3), default='GBP'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('invoice_reference', sa.String(100), nullable=True),
        sa.Column('is_direct_cost', sa.Boolean(), default=True),
        sa.Column('is_recurring', sa.Boolean(), default=False),
        sa.Column('cost_date', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cost_records_entity_type', 'cost_records', ['entity_type'])
    op.create_index('ix_cost_records_entity_id', 'cost_records', ['entity_id'])

    # ROI investments table
    op.create_table(
        'roi_investments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('investment_amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(3), default='GBP'),
        sa.Column('investment_date', sa.DateTime(), nullable=False),
        sa.Column('expected_annual_savings', sa.Float(), nullable=True),
        sa.Column('expected_incident_reduction', sa.Float(), nullable=True),
        sa.Column('payback_period_months', sa.Integer(), nullable=True),
        sa.Column('actual_savings_to_date', sa.Float(), default=0),
        sa.Column('actual_incidents_prevented', sa.Integer(), default=0),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('roi_investments')
    op.drop_index('ix_cost_records_entity_id', 'cost_records')
    op.drop_index('ix_cost_records_entity_type', 'cost_records')
    op.drop_table('cost_records')
    op.drop_index('ix_benchmark_data_industry', 'benchmark_data')
    op.drop_index('ix_benchmark_data_metric', 'benchmark_data')
    op.drop_index('ix_benchmark_data_category', 'benchmark_data')
    op.drop_table('benchmark_data')
    op.drop_table('saved_reports')
    op.drop_index('ix_dashboard_widgets_dashboard_id', 'dashboard_widgets')
    op.drop_table('dashboard_widgets')
    op.drop_table('dashboards')
