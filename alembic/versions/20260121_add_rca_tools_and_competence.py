"""Add RCA tools and auditor competence tables.

Revision ID: 20260121_rca_competence
Revises: 20260121_policy_ack
Create Date: 2026-01-21

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260121_rca_competence'
down_revision = '20260121_policy_ack'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # RCA TOOLS TABLES
    # ==========================================================================
    
    # 5-Whys Analysis table
    op.create_table(
        'five_whys_analyses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('investigation_id', sa.Integer(), sa.ForeignKey('investigation_runs.id', ondelete='CASCADE'), nullable=True),
        sa.Column('entity_type', sa.String(50), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('problem_statement', sa.Text(), nullable=False),
        sa.Column('whys', sa.JSON(), nullable=False),
        sa.Column('root_causes', sa.JSON(), nullable=True),
        sa.Column('primary_root_cause', sa.Text(), nullable=True),
        sa.Column('contributing_factors', sa.JSON(), nullable=True),
        sa.Column('proposed_actions', sa.JSON(), nullable=True),
        sa.Column('completed', sa.Boolean(), default=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed', sa.Boolean(), default=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('review_comments', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_five_whys_investigation_id', 'five_whys_analyses', ['investigation_id'])
    op.create_index('ix_five_whys_entity', 'five_whys_analyses', ['entity_type', 'entity_id'])

    # Fishbone Diagrams table
    op.create_table(
        'fishbone_diagrams',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('investigation_id', sa.Integer(), sa.ForeignKey('investigation_runs.id', ondelete='CASCADE'), nullable=True),
        sa.Column('entity_type', sa.String(50), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('effect_statement', sa.Text(), nullable=False),
        sa.Column('causes', sa.JSON(), nullable=False),
        sa.Column('primary_causes', sa.JSON(), nullable=True),
        sa.Column('root_cause', sa.Text(), nullable=True),
        sa.Column('root_cause_category', sa.String(50), nullable=True),
        sa.Column('proposed_actions', sa.JSON(), nullable=True),
        sa.Column('completed', sa.Boolean(), default=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed', sa.Boolean(), default=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_fishbone_investigation_id', 'fishbone_diagrams', ['investigation_id'])
    op.create_index('ix_fishbone_entity', 'fishbone_diagrams', ['entity_type', 'entity_id'])

    # Barrier Analysis table
    op.create_table(
        'barrier_analyses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('investigation_id', sa.Integer(), sa.ForeignKey('investigation_runs.id', ondelete='CASCADE'), nullable=True),
        sa.Column('entity_type', sa.String(50), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('hazard_description', sa.Text(), nullable=False),
        sa.Column('target_description', sa.Text(), nullable=False),
        sa.Column('barriers', sa.JSON(), nullable=False),
        sa.Column('barriers_that_worked', sa.JSON(), nullable=True),
        sa.Column('barriers_that_failed', sa.JSON(), nullable=True),
        sa.Column('missing_barriers', sa.JSON(), nullable=True),
        sa.Column('recommended_new_barriers', sa.JSON(), nullable=True),
        sa.Column('recommended_improvements', sa.JSON(), nullable=True),
        sa.Column('completed', sa.Boolean(), default=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_barrier_investigation_id', 'barrier_analyses', ['investigation_id'])

    # CAPA Items table
    op.create_table(
        'capa_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('five_whys_id', sa.Integer(), sa.ForeignKey('five_whys_analyses.id', ondelete='SET NULL'), nullable=True),
        sa.Column('fishbone_id', sa.Integer(), sa.ForeignKey('fishbone_diagrams.id', ondelete='SET NULL'), nullable=True),
        sa.Column('barrier_analysis_id', sa.Integer(), sa.ForeignKey('barrier_analyses.id', ondelete='SET NULL'), nullable=True),
        sa.Column('investigation_id', sa.Integer(), sa.ForeignKey('investigation_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('root_cause_addressed', sa.Text(), nullable=True),
        sa.Column('assigned_to_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), default='open'),
        sa.Column('priority', sa.String(20), default='medium'),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verification_required', sa.Boolean(), default=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('verification_notes', sa.Text(), nullable=True),
        sa.Column('effectiveness_review_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_effective', sa.Boolean(), nullable=True),
        sa.Column('effectiveness_notes', sa.Text(), nullable=True),
        sa.Column('evidence_attachments', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_capa_investigation_id', 'capa_items', ['investigation_id'])
    op.create_index('ix_capa_status', 'capa_items', ['status'])
    op.create_index('ix_capa_due_date', 'capa_items', ['due_date'])

    # ==========================================================================
    # AUDITOR COMPETENCE TABLES
    # ==========================================================================

    # Auditor Profiles table
    op.create_table(
        'auditor_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('employee_id', sa.String(50), nullable=True),
        sa.Column('job_title', sa.String(100), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('competence_level', sa.String(50), default='trainee'),
        sa.Column('years_audit_experience', sa.Float(), nullable=True),
        sa.Column('total_audits_conducted', sa.Integer(), default=0),
        sa.Column('total_audits_as_lead', sa.Integer(), default=0),
        sa.Column('specializations', sa.JSON(), nullable=True),
        sa.Column('industry_experience', sa.JSON(), nullable=True),
        sa.Column('languages', sa.JSON(), nullable=True),
        sa.Column('is_available', sa.Boolean(), default=True),
        sa.Column('availability_notes', sa.Text(), nullable=True),
        sa.Column('last_competence_assessment', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_assessment_due', sa.DateTime(timezone=True), nullable=True),
        sa.Column('competence_score', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index('ix_auditor_profiles_user_id', 'auditor_profiles', ['user_id'])

    # Auditor Certifications table
    op.create_table(
        'auditor_certifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('auditor_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('certification_name', sa.String(200), nullable=False),
        sa.Column('certification_body', sa.String(200), nullable=False),
        sa.Column('certification_number', sa.String(100), nullable=True),
        sa.Column('standard_code', sa.String(50), nullable=True),
        sa.Column('certification_level', sa.String(50), nullable=True),
        sa.Column('issued_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expiry_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('cpd_hours_required', sa.Integer(), nullable=True),
        sa.Column('cpd_hours_completed', sa.Integer(), default=0),
        sa.Column('certificate_url', sa.String(500), nullable=True),
        sa.Column('verification_url', sa.String(500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_auditor_certs_profile_id', 'auditor_certifications', ['profile_id'])

    # Auditor Training table
    op.create_table(
        'auditor_training',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('auditor_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('training_name', sa.String(200), nullable=False),
        sa.Column('training_provider', sa.String(200), nullable=True),
        sa.Column('training_type', sa.String(50), default='course'),
        sa.Column('topic', sa.String(100), nullable=True),
        sa.Column('standard_code', sa.String(50), nullable=True),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_hours', sa.Float(), nullable=True),
        sa.Column('cpd_hours_earned', sa.Float(), nullable=True),
        sa.Column('completed', sa.Boolean(), default=False),
        sa.Column('completion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assessment_passed', sa.Boolean(), nullable=True),
        sa.Column('assessment_score', sa.Float(), nullable=True),
        sa.Column('certificate_issued', sa.Boolean(), default=False),
        sa.Column('certificate_url', sa.String(500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_auditor_training_profile_id', 'auditor_training', ['profile_id'])

    # Competency Areas table
    op.create_table(
        'competency_areas',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('applicable_standards', sa.JSON(), nullable=True),
        sa.Column('proficiency_scale', sa.JSON(), nullable=False),
        sa.Column('required_levels', sa.JSON(), nullable=False),
        sa.Column('weight', sa.Float(), default=1.0),
        sa.Column('assessment_criteria', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('ix_competency_areas_code', 'competency_areas', ['code'])

    # Auditor Competencies table
    op.create_table(
        'auditor_competencies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('auditor_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('competency_area_id', sa.Integer(), sa.ForeignKey('competency_areas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('current_level', sa.Integer(), nullable=False),
        sa.Column('target_level', sa.Integer(), nullable=True),
        sa.Column('evidence_summary', sa.Text(), nullable=True),
        sa.Column('evidence_links', sa.JSON(), nullable=True),
        sa.Column('last_assessed', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assessed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('assessment_method', sa.String(50), nullable=True),
        sa.Column('development_plan', sa.Text(), nullable=True),
        sa.Column('development_actions', sa.JSON(), nullable=True),
        sa.Column('has_gap', sa.Boolean(), default=False),
        sa.Column('gap_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_auditor_comp_profile_id', 'auditor_competencies', ['profile_id'])
    op.create_index('ix_auditor_comp_area_id', 'auditor_competencies', ['competency_area_id'])

    # Audit Assignment Criteria table
    op.create_table(
        'audit_assignment_criteria',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('audit_type', sa.String(100), nullable=False),
        sa.Column('required_certifications', sa.JSON(), nullable=True),
        sa.Column('required_competencies', sa.JSON(), nullable=True),
        sa.Column('minimum_auditor_level', sa.String(50), default='auditor'),
        sa.Column('minimum_audits_conducted', sa.Integer(), default=0),
        sa.Column('minimum_years_experience', sa.Float(), default=0),
        sa.Column('required_industry_experience', sa.JSON(), nullable=True),
        sa.Column('additional_requirements', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_criteria_type', 'audit_assignment_criteria', ['audit_type'])


def downgrade() -> None:
    # Drop Auditor Competence tables
    op.drop_table('audit_assignment_criteria')
    op.drop_table('auditor_competencies')
    op.drop_table('competency_areas')
    op.drop_table('auditor_training')
    op.drop_table('auditor_certifications')
    op.drop_table('auditor_profiles')
    
    # Drop RCA Tools tables
    op.drop_table('capa_items')
    op.drop_table('barrier_analyses')
    op.drop_table('fishbone_diagrams')
    op.drop_table('five_whys_analyses')
