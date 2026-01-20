"""Add UVDB Achilles Verify B2 tables

Revision ID: add_uvdb_achilles
Revises: add_iso27001_isms
Create Date: 2026-01-20 12:00:00.000000

UVDB = Utilities Vendor Database
Supply chain qualification audit for UK utilities sector
Protocol: UVDB-QS-003 - Verify B2 Audit Protocol V11.2
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_uvdb_achilles'
down_revision = 'add_iso27001_isms'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # UVDB Sections
    op.create_table(
        'uvdb_section',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('section_number', sa.String(10), nullable=False, unique=True),
        sa.Column('section_title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('max_score', sa.Integer(), nullable=False, default=0),
        sa.Column('iso_9001_mapping', sa.String(50), nullable=True),
        sa.Column('iso_14001_mapping', sa.String(50), nullable=True),
        sa.Column('iso_45001_mapping', sa.String(50), nullable=True),
        sa.Column('iso_27001_mapping', sa.String(50), nullable=True),
        sa.Column('is_mse_only', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_site_applicable', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # UVDB Questions
    op.create_table(
        'uvdb_question',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('section_id', sa.Integer(), nullable=False),
        sa.Column('question_number', sa.String(20), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('sub_questions', postgresql.JSONB(), nullable=True),
        sa.Column('max_score', sa.Integer(), nullable=False, default=3),
        sa.Column('scoring_criteria', postgresql.JSONB(), nullable=True),
        sa.Column('evidence_requirements', postgresql.JSONB(), nullable=True),
        sa.Column('document_types', postgresql.JSONB(), nullable=True),
        sa.Column('mse_applicable', sa.Boolean(), nullable=False, default=True),
        sa.Column('site_applicable', sa.Boolean(), nullable=False, default=True),
        sa.Column('iso_clause_mapping', postgresql.JSONB(), nullable=True),
        sa.Column('auditor_guidance', sa.Text(), nullable=True),
        sa.Column('positive_indicators', postgresql.JSONB(), nullable=True),
        sa.Column('negative_indicators', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['section_id'], ['uvdb_section.id'], ondelete='CASCADE'),
    )

    # UVDB Audits
    op.create_table(
        'uvdb_audit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('audit_reference', sa.String(50), nullable=False, unique=True),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('company_id', sa.String(50), nullable=True),
        sa.Column('supplier_registration', sa.String(100), nullable=True),
        sa.Column('audit_type', sa.String(50), nullable=False),
        sa.Column('audit_scope', sa.Text(), nullable=True),
        sa.Column('audit_date', sa.DateTime(), nullable=True),
        sa.Column('next_audit_due', sa.DateTime(), nullable=True),
        sa.Column('declaration_date', sa.DateTime(), nullable=True),
        sa.Column('expiry_date', sa.DateTime(), nullable=True),
        sa.Column('lead_auditor', sa.String(255), nullable=True),
        sa.Column('auditor_organization', sa.String(255), nullable=True),
        sa.Column('total_score', sa.Float(), nullable=True),
        sa.Column('max_possible_score', sa.Float(), nullable=True),
        sa.Column('percentage_score', sa.Float(), nullable=True),
        sa.Column('section_scores', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, default='scheduled'),
        sa.Column('findings_count', sa.Integer(), nullable=False, default=0),
        sa.Column('major_findings', sa.Integer(), nullable=False, default=0),
        sa.Column('minor_findings', sa.Integer(), nullable=False, default=0),
        sa.Column('observations', sa.Integer(), nullable=False, default=0),
        sa.Column('iso_9001_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('iso_14001_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('iso_45001_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('iso_27001_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('ukas_accredited', sa.Boolean(), nullable=False, default=False),
        sa.Column('cdm_compliant', sa.Boolean(), nullable=False, default=False),
        sa.Column('fors_accredited', sa.Boolean(), nullable=False, default=False),
        sa.Column('fors_level', sa.String(20), nullable=True),
        sa.Column('audit_notes', sa.Text(), nullable=True),
        sa.Column('improvement_actions', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_uvdb_audit_company', 'company_name'),
        sa.Index('ix_uvdb_audit_status', 'status'),
    )

    # UVDB Audit Responses
    op.create_table(
        'uvdb_audit_response',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('audit_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('mse_response', sa.Integer(), nullable=True),
        sa.Column('site_response', sa.Integer(), nullable=True),
        sa.Column('sub_question_responses', postgresql.JSONB(), nullable=True),
        sa.Column('evidence_provided', sa.Text(), nullable=True),
        sa.Column('documents_presented', postgresql.JSONB(), nullable=True),
        sa.Column('finding_type', sa.String(30), nullable=True),
        sa.Column('finding_description', sa.Text(), nullable=True),
        sa.Column('auditor_notes', sa.Text(), nullable=True),
        sa.Column('positive_elements', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['audit_id'], ['uvdb_audit.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['uvdb_question.id'], ondelete='CASCADE'),
    )

    # UVDB KPI Records
    op.create_table(
        'uvdb_kpi_record',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('audit_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=True),
        sa.Column('period_end', sa.DateTime(), nullable=True),
        sa.Column('total_man_hours', sa.Integer(), nullable=True),
        sa.Column('fatalities', sa.Integer(), nullable=False, default=0),
        sa.Column('riddor_reportable', sa.Integer(), nullable=False, default=0),
        sa.Column('lost_time_incidents_1_7_days', sa.Integer(), nullable=False, default=0),
        sa.Column('medical_treatment_incidents', sa.Integer(), nullable=False, default=0),
        sa.Column('first_aid_incidents', sa.Integer(), nullable=False, default=0),
        sa.Column('dangerous_occurrences', sa.Integer(), nullable=False, default=0),
        sa.Column('near_misses', sa.Integer(), nullable=False, default=0),
        sa.Column('hse_improvement_notices', sa.Integer(), nullable=False, default=0),
        sa.Column('hse_prohibition_notices', sa.Integer(), nullable=False, default=0),
        sa.Column('hse_prosecutions', sa.Integer(), nullable=False, default=0),
        sa.Column('env_minor_incidents', sa.Integer(), nullable=False, default=0),
        sa.Column('env_reportable_incidents', sa.Integer(), nullable=False, default=0),
        sa.Column('env_enforcement_actions', sa.Integer(), nullable=False, default=0),
        sa.Column('ltifr', sa.Float(), nullable=True),
        sa.Column('trifr', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['audit_id'], ['uvdb_audit.id'], ondelete='CASCADE'),
        sa.Index('ix_uvdb_kpi_year', 'year'),
    )

    # UVDB ISO Cross-Mapping
    op.create_table(
        'uvdb_iso_cross_mapping',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uvdb_question_id', sa.Integer(), nullable=False),
        sa.Column('iso_standard', sa.String(20), nullable=False),
        sa.Column('iso_clause', sa.String(20), nullable=False),
        sa.Column('iso_clause_title', sa.String(255), nullable=True),
        sa.Column('mapping_type', sa.String(20), nullable=False, default='direct'),
        sa.Column('mapping_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['uvdb_question_id'], ['uvdb_question.id'], ondelete='CASCADE'),
        sa.Index('ix_uvdb_iso_mapping_standard', 'iso_standard'),
    )


def downgrade() -> None:
    op.drop_table('uvdb_iso_cross_mapping')
    op.drop_table('uvdb_kpi_record')
    op.drop_table('uvdb_audit_response')
    op.drop_table('uvdb_audit')
    op.drop_table('uvdb_question')
    op.drop_table('uvdb_section')
