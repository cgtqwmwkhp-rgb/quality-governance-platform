"""Create assessment execution tables.

Revision ID: 20260302_assess
Revises: 20260302_asset_reg
Create Date: 2026-03-02 10:30:00.000000

Creates assessment_runs and assessment_responses tables for on-the-job
competency assessment.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260302_assess"
down_revision = "20260302_engineer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reference_number", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("audit_templates.id"), nullable=False, index=True),
        sa.Column("template_version", sa.Integer(), server_default="1"),
        sa.Column("engineer_id", sa.Integer(), sa.ForeignKey("engineers.id"), nullable=False, index=True),
        sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("asset_type_id", sa.Integer(), sa.ForeignKey("asset_types.id"), nullable=True, index=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft", index=True),
        sa.Column("scheduled_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(50), nullable=True),
        sa.Column("overall_notes", sa.Text(), nullable=True),
        sa.Column("debrief_notes", sa.Text(), nullable=True),
        sa.Column("debrief_signature", sa.Text(), nullable=True),
        sa.Column("debrief_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
    )

    op.create_table(
        "assessment_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("assessment_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("audit_questions.id"), nullable=False, index=True),
        sa.Column("verdict", sa.String(50), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("supervisor_notes", sa.Text(), nullable=True),
        sa.Column("photo_ids_json", sa.JSON(), nullable=True),
        sa.Column("voice_note_id", sa.String(36), nullable=True),
        sa.Column("engineer_signature", sa.Text(), nullable=True),
        sa.Column("engineer_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("assessment_responses")
    op.drop_table("assessment_runs")
