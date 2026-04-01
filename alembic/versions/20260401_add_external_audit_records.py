"""Add external_audit_records table for unified cross-scheme audit registry.

Revision ID: a3f1b2c4d5e6
Revises: (auto-detected)
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa

revision = "a3f1b2c4d5e6"
down_revision = "20260330_ext_audit_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_audit_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("scheme", sa.String(50), nullable=False),
        sa.Column("scheme_version", sa.String(50), nullable=True),
        sa.Column("scheme_label", sa.String(200), nullable=True),
        sa.Column("audit_run_id", sa.Integer(), sa.ForeignKey("audit_runs.id"), nullable=True),
        sa.Column(
            "import_job_id",
            sa.Integer(),
            sa.ForeignKey("external_audit_import_jobs.id"),
            nullable=True,
        ),
        sa.Column("issuer_name", sa.String(200), nullable=True),
        sa.Column("company_name", sa.String(200), nullable=True),
        sa.Column("report_date", sa.DateTime(), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("max_score", sa.Float(), nullable=True),
        sa.Column("score_percentage", sa.Float(), nullable=True),
        sa.Column("section_scores", sa.JSON(), nullable=True),
        sa.Column("outcome_status", sa.String(50), nullable=True),
        sa.Column("findings_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("major_findings", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("minor_findings", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("observations", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("analysis_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="completed"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_audit_records_tenant_id", "external_audit_records", ["tenant_id"])
    op.create_index("ix_external_audit_records_scheme", "external_audit_records", ["scheme"])
    op.create_index("ix_external_audit_records_audit_run_id", "external_audit_records", ["audit_run_id"])
    op.create_index("ix_external_audit_records_import_job_id", "external_audit_records", ["import_job_id"])
    op.create_index(
        "ix_external_audit_records_tenant_scheme",
        "external_audit_records",
        ["tenant_id", "scheme"],
    )


def downgrade() -> None:
    op.drop_table("external_audit_records")
