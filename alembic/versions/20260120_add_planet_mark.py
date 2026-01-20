"""Add Planet Mark Carbon Management tables

Revision ID: pm_carbon_001
Revises: uvdb_achilles_001
Create Date: 2026-01-20 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'pm_carbon_001'
down_revision: Union[str, None] = 'uvdb_achilles_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Carbon Reporting Year
    op.create_table(
        'carbon_reporting_year',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year_label', sa.String(20), nullable=False),
        sa.Column('year_number', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('organization_name', sa.String(255), nullable=True, default='Plantexpand Limited'),
        sa.Column('reporting_boundary', sa.Text(), nullable=True),
        sa.Column('sites_included', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('average_fte', sa.Float(), nullable=False, default=0),
        sa.Column('is_baseline_year', sa.Boolean(), default=False),
        sa.Column('baseline_year_id', sa.Integer(), sa.ForeignKey('carbon_reporting_year.id'), nullable=True),
        sa.Column('scope_1_total', sa.Float(), default=0),
        sa.Column('scope_2_location', sa.Float(), default=0),
        sa.Column('scope_2_market', sa.Float(), default=0),
        sa.Column('scope_3_total', sa.Float(), default=0),
        sa.Column('total_emissions', sa.Float(), default=0),
        sa.Column('emissions_per_fte', sa.Float(), default=0),
        sa.Column('scope_1_data_quality', sa.Integer(), default=0),
        sa.Column('scope_2_data_quality', sa.Integer(), default=0),
        sa.Column('scope_3_data_quality', sa.Integer(), default=0),
        sa.Column('overall_data_quality', sa.Integer(), default=0),
        sa.Column('certification_status', sa.String(30), default='draft'),
        sa.Column('certificate_number', sa.String(100), nullable=True),
        sa.Column('certification_date', sa.DateTime(), nullable=True),
        sa.Column('expiry_date', sa.DateTime(), nullable=True),
        sa.Column('assessor_name', sa.String(255), nullable=True),
        sa.Column('assessment_notes', sa.Text(), nullable=True),
        sa.Column('reduction_target_percent', sa.Float(), default=5.0),
        sa.Column('target_emissions_per_fte', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Emission Source
    op.create_table(
        'emission_source',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reporting_year_id', sa.Integer(), sa.ForeignKey('carbon_reporting_year.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_name', sa.String(255), nullable=False),
        sa.Column('source_category', sa.String(100), nullable=False),
        sa.Column('scope', sa.String(20), nullable=False),
        sa.Column('scope_3_category', sa.String(20), nullable=True),
        sa.Column('activity_type', sa.String(100), nullable=False),
        sa.Column('activity_value', sa.Float(), nullable=False),
        sa.Column('activity_unit', sa.String(50), nullable=False),
        sa.Column('emission_factor', sa.Float(), nullable=False),
        sa.Column('emission_factor_unit', sa.String(100), nullable=False),
        sa.Column('emission_factor_source', sa.String(255), nullable=True),
        sa.Column('co2e_tonnes', sa.Float(), nullable=False),
        sa.Column('co2_tonnes', sa.Float(), nullable=True),
        sa.Column('ch4_tonnes', sa.Float(), nullable=True),
        sa.Column('n2o_tonnes', sa.Float(), nullable=True),
        sa.Column('data_quality_level', sa.String(30), nullable=False, default='estimated'),
        sa.Column('data_quality_score', sa.Integer(), default=2),
        sa.Column('data_source', sa.String(255), nullable=True),
        sa.Column('data_notes', sa.Text(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('verified_by', sa.String(255), nullable=True),
        sa.Column('verified_date', sa.DateTime(), nullable=True),
        sa.Column('sub_sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Scope 3 Category Data
    op.create_table(
        'scope3_category_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reporting_year_id', sa.Integer(), sa.ForeignKey('carbon_reporting_year.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category_number', sa.Integer(), nullable=False),
        sa.Column('category_name', sa.String(100), nullable=False),
        sa.Column('category_description', sa.Text(), nullable=True),
        sa.Column('is_relevant', sa.Boolean(), default=True),
        sa.Column('is_measured', sa.Boolean(), default=False),
        sa.Column('exclusion_reason', sa.Text(), nullable=True),
        sa.Column('total_co2e', sa.Float(), default=0),
        sa.Column('percentage_of_scope3', sa.Float(), default=0),
        sa.Column('data_quality_score', sa.Integer(), default=0),
        sa.Column('calculation_method', sa.String(100), nullable=True),
        sa.Column('data_sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('supplier_data_coverage', sa.Float(), nullable=True),
        sa.Column('improvement_priority', sa.String(20), nullable=True),
        sa.Column('improvement_actions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Improvement Actions
    op.create_table(
        'carbon_improvement_action',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reporting_year_id', sa.Integer(), sa.ForeignKey('carbon_reporting_year.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_id', sa.String(20), nullable=False),
        sa.Column('action_title', sa.String(255), nullable=False),
        sa.Column('specific', sa.Text(), nullable=False),
        sa.Column('measurable', sa.Text(), nullable=False),
        sa.Column('achievable_owner', sa.String(255), nullable=False),
        sa.Column('relevant', sa.Text(), nullable=True),
        sa.Column('time_bound', sa.DateTime(), nullable=False),
        sa.Column('scheduled_month', sa.String(20), nullable=True),
        sa.Column('quarter', sa.String(10), nullable=True),
        sa.Column('target_scope', sa.String(20), nullable=True),
        sa.Column('target_source', sa.String(100), nullable=True),
        sa.Column('expected_reduction_pct', sa.Float(), nullable=True),
        sa.Column('expected_reduction_tco2e', sa.Float(), nullable=True),
        sa.Column('status', sa.String(30), default='planned'),
        sa.Column('progress_percent', sa.Integer(), default=0),
        sa.Column('actual_completion_date', sa.DateTime(), nullable=True),
        sa.Column('evidence_required', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('evidence_provided', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('actual_reduction_achieved', sa.Float(), nullable=True),
        sa.Column('lessons_learned', sa.Text(), nullable=True),
        sa.Column('reminder_sent', sa.Boolean(), default=False),
        sa.Column('overdue_notified', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Data Quality Assessment
    op.create_table(
        'data_quality_assessment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reporting_year_id', sa.Integer(), sa.ForeignKey('carbon_reporting_year.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scope', sa.String(20), nullable=False),
        sa.Column('completeness_score', sa.Integer(), default=0),
        sa.Column('accuracy_score', sa.Integer(), default=0),
        sa.Column('consistency_score', sa.Integer(), default=0),
        sa.Column('transparency_score', sa.Integer(), default=0),
        sa.Column('total_score', sa.Integer(), default=0),
        sa.Column('completeness_notes', sa.Text(), nullable=True),
        sa.Column('accuracy_notes', sa.Text(), nullable=True),
        sa.Column('consistency_notes', sa.Text(), nullable=True),
        sa.Column('transparency_notes', sa.Text(), nullable=True),
        sa.Column('sources_assessed', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('actual_data_percent', sa.Float(), default=0),
        sa.Column('estimated_data_percent', sa.Float(), default=0),
        sa.Column('improvement_recommendations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('priority_actions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('target_score', sa.Integer(), nullable=True),
        sa.Column('assessed_date', sa.DateTime(), nullable=True),
        sa.Column('assessed_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Carbon Evidence
    op.create_table(
        'carbon_evidence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reporting_year_id', sa.Integer(), sa.ForeignKey('carbon_reporting_year.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_name', sa.String(255), nullable=False),
        sa.Column('document_type', sa.String(100), nullable=False),
        sa.Column('evidence_category', sa.String(50), nullable=False),
        sa.Column('linked_source_id', sa.Integer(), nullable=True),
        sa.Column('linked_action_id', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_size_kb', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('period_covered', sa.String(100), nullable=True),
        sa.Column('value_documented', sa.Float(), nullable=True),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('verified_by', sa.String(255), nullable=True),
        sa.Column('verified_date', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('uploaded_by', sa.String(255), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Fleet Emission Record
    op.create_table(
        'fleet_emission_record',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reporting_year_id', sa.Integer(), sa.ForeignKey('carbon_reporting_year.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vehicle_registration', sa.String(20), nullable=False),
        sa.Column('vehicle_type', sa.String(100), nullable=True),
        sa.Column('fuel_type', sa.String(50), nullable=False),
        sa.Column('month', sa.String(10), nullable=False),
        sa.Column('fuel_litres', sa.Float(), nullable=False),
        sa.Column('fuel_cost', sa.Float(), nullable=True),
        sa.Column('mileage', sa.Float(), nullable=True),
        sa.Column('litres_per_100km', sa.Float(), nullable=True),
        sa.Column('co2e_kg', sa.Float(), nullable=False),
        sa.Column('data_source', sa.String(50), nullable=False),
        sa.Column('fuel_card_provider', sa.String(100), nullable=True),
        sa.Column('driver_name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Utility Meter Reading
    op.create_table(
        'utility_meter_reading',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reporting_year_id', sa.Integer(), sa.ForeignKey('carbon_reporting_year.id', ondelete='CASCADE'), nullable=False),
        sa.Column('meter_reference', sa.String(100), nullable=False),
        sa.Column('utility_type', sa.String(50), nullable=False),
        sa.Column('site_name', sa.String(255), nullable=False),
        sa.Column('reading_date', sa.DateTime(), nullable=False),
        sa.Column('reading_value', sa.Float(), nullable=False),
        sa.Column('reading_unit', sa.String(20), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=True),
        sa.Column('period_end', sa.DateTime(), nullable=True),
        sa.Column('consumption', sa.Float(), nullable=True),
        sa.Column('reading_type', sa.String(30), nullable=False),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('supplier_name', sa.String(255), nullable=True),
        sa.Column('tariff_type', sa.String(100), nullable=True),
        sa.Column('is_renewable', sa.Boolean(), default=False),
        sa.Column('rego_certificate', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Supplier Emission Data
    op.create_table(
        'supplier_emission_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reporting_year_id', sa.Integer(), sa.ForeignKey('carbon_reporting_year.id', ondelete='CASCADE'), nullable=False),
        sa.Column('supplier_name', sa.String(255), nullable=False),
        sa.Column('supplier_category', sa.String(100), nullable=False),
        sa.Column('scope3_category', sa.Integer(), nullable=False),
        sa.Column('annual_spend', sa.Float(), nullable=False),
        sa.Column('spend_currency', sa.String(10), default='GBP'),
        sa.Column('supplier_reported_co2e', sa.Float(), nullable=True),
        sa.Column('emission_intensity', sa.Float(), nullable=True),
        sa.Column('spend_based_co2e', sa.Float(), nullable=True),
        sa.Column('emission_factor_used', sa.Float(), nullable=True),
        sa.Column('data_type', sa.String(30), nullable=False),
        sa.Column('has_responded_to_survey', sa.Boolean(), default=False),
        sa.Column('engagement_status', sa.String(50), nullable=True),
        sa.Column('last_contact_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Planet Mark ISO 14001 Cross-Mapping
    op.create_table(
        'planet_mark_iso14001_mapping',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pm_requirement', sa.String(255), nullable=False),
        sa.Column('pm_category', sa.String(100), nullable=False),
        sa.Column('iso14001_clause', sa.String(20), nullable=False),
        sa.Column('iso14001_title', sa.String(255), nullable=False),
        sa.Column('mapping_type', sa.String(20), nullable=False),
        sa.Column('alignment_notes', sa.Text(), nullable=True),
        sa.Column('shared_evidence_types', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_emission_source_scope', 'emission_source', ['scope'])
    op.create_index('ix_emission_source_year', 'emission_source', ['reporting_year_id'])
    op.create_index('ix_fleet_emission_vehicle', 'fleet_emission_record', ['vehicle_registration'])
    op.create_index('ix_fleet_emission_month', 'fleet_emission_record', ['month'])


def downgrade() -> None:
    op.drop_index('ix_fleet_emission_month')
    op.drop_index('ix_fleet_emission_vehicle')
    op.drop_index('ix_emission_source_year')
    op.drop_index('ix_emission_source_scope')
    op.drop_table('planet_mark_iso14001_mapping')
    op.drop_table('supplier_emission_data')
    op.drop_table('utility_meter_reading')
    op.drop_table('fleet_emission_record')
    op.drop_table('carbon_evidence')
    op.drop_table('data_quality_assessment')
    op.drop_table('carbon_improvement_action')
    op.drop_table('scope3_category_data')
    op.drop_table('emission_source')
    op.drop_table('carbon_reporting_year')
