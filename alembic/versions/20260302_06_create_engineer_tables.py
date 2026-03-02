"""Create engineer and competency tables for Workforce Development Platform.

Revision ID: 20260302_engineer
Revises: 20260302_induct
Create Date: 2026-03-02 10:50:00.000000

Creates engineers, competency_records, competency_requirements, and
onboarding_checklists tables for field engineer competency tracking.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "20260302_engineer"
down_revision = "20260302_asset_reg"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # engineers
    op.create_table(
        "engineers",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("external_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("employee_number", sa.String(50), nullable=True),
        sa.Column("job_title", sa.String(100), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("site", sa.String(200), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("specialisations_json", JSON, nullable=True),
        sa.Column("certifications_json", JSON, nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_engineers_employee_number", "engineers", ["employee_number"])
    op.create_index("ix_engineers_external_id", "engineers", ["external_id"])
    op.create_index("ix_engineers_tenant_id", "engineers", ["tenant_id"])
    op.create_index("ix_engineers_user_id", "engineers", ["user_id"])
    op.create_unique_constraint("uq_engineers_external_id", "engineers", ["external_id"])

    # competency_records
    op.create_table(
        "competency_records",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("engineer_id", sa.Integer(), sa.ForeignKey("engineers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_type_id", sa.Integer(), sa.ForeignKey("asset_types.id"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("audit_templates.id"), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_run_id", sa.String(36), nullable=False),
        sa.Column("state", sa.String(50), nullable=False, server_default="not_assessed"),
        sa.Column("outcome", sa.String(50), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assessed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_competency_records_engineer_id", "competency_records", ["engineer_id"])
    op.create_index("ix_competency_records_asset_type_id", "competency_records", ["asset_type_id"])
    op.create_index("ix_competency_records_source_run_id", "competency_records", ["source_run_id"])
    op.create_index("ix_competency_records_state", "competency_records", ["state"])
    op.create_index("ix_competency_records_tenant_id", "competency_records", ["tenant_id"])

    # competency_requirements
    op.create_table(
        "competency_requirements",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("asset_type_id", sa.Integer(), sa.ForeignKey("asset_types.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("audit_templates.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), server_default="true"),
        sa.Column("reassessment_interval_days", sa.Integer(), server_default="365"),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_competency_requirements_asset_type_id", "competency_requirements", ["asset_type_id"])
    op.create_index("ix_competency_requirements_tenant_id", "competency_requirements", ["tenant_id"])

    # onboarding_checklists
    op.create_table(
        "onboarding_checklists",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("engineer_id", sa.Integer(), sa.ForeignKey("engineers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("competency_requirements.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_run_id", sa.String(36), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_onboarding_checklists_engineer_id", "onboarding_checklists", ["engineer_id"])
    op.create_index("ix_onboarding_checklists_status", "onboarding_checklists", ["status"])
    op.create_index("ix_onboarding_checklists_requirement_id", "onboarding_checklists", ["requirement_id"])
    op.create_index("ix_onboarding_checklists_tenant_id", "onboarding_checklists", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("onboarding_checklists")
    op.drop_table("competency_requirements")
    op.drop_table("competency_records")
    op.drop_table("engineers")
