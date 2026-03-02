"""Create induction/training execution tables.

Revision ID: 20260302_induct
Revises: 20260302_assess
Create Date: 2026-03-02 10:40:00.000000

Creates induction_runs and induction_responses tables for engineer
training and development sessions.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260302_induct"
down_revision = "20260302_assess"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "induction_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reference_number", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("audit_templates.id"), nullable=False, index=True),
        sa.Column("template_version", sa.Integer(), server_default="1"),
        sa.Column("engineer_id", sa.Integer(), sa.ForeignKey("engineers.id"), nullable=False, index=True),
        sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("asset_type_id", sa.Integer(), sa.ForeignKey("asset_types.id"), nullable=True, index=True),
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("stage", sa.String(50), nullable=False, server_default="stage_1_onsite"),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft", index=True),
        sa.Column("scheduled_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_items", sa.Integer(), server_default="0"),
        sa.Column("competent_count", sa.Integer(), server_default="0"),
        sa.Column("not_yet_competent_count", sa.Integer(), server_default="0"),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
    )

    op.create_table(
        "induction_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("induction_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("audit_questions.id"), nullable=False, index=True),
        sa.Column("shown_explained", sa.Boolean(), server_default="false"),
        sa.Column("understanding", sa.String(50), nullable=True),
        sa.Column("supervisor_notes", sa.Text(), nullable=True),
        sa.Column("engineer_signature", sa.Text(), nullable=True),
        sa.Column("engineer_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("induction_responses")
    op.drop_table("induction_runs")
