"""Create external audit import tables when missing.

Revision ID: 20260330_create_ext_audit_import_tables
Revises: 20260327_ext_audit_import_jobs
Create Date: 2026-03-30
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260330_create_ext_audit_import_tables"
down_revision: Union[str, None] = "20260327_ext_audit_import_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_timestamp_default() -> sa.TextClause:
    return sa.text("CURRENT_TIMESTAMP")


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _has_unique_constraint(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(constraint["name"] == constraint_name for constraint in inspector.get_unique_constraints(table_name))


def _ensure_jobs_table() -> None:
    if not _has_table("external_audit_import_jobs"):
        op.create_table(
            "external_audit_import_jobs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(
                "audit_run_id",
                sa.Integer(),
                sa.ForeignKey("audit_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "source_document_asset_id",
                sa.Integer(),
                sa.ForeignKey("evidence_assets.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
            sa.Column("provider_name", sa.String(length=100), nullable=True),
            sa.Column("provider_model", sa.String(length=100), nullable=True),
            sa.Column("source_filename", sa.String(length=255), nullable=True),
            sa.Column("source_content_type", sa.String(length=100), nullable=True),
            sa.Column("source_checksum_sha256", sa.String(length=64), nullable=False),
            sa.Column("idempotency_key", sa.String(length=255), nullable=False),
            sa.Column("extraction_method", sa.String(length=50), nullable=True),
            sa.Column("extraction_text_preview", sa.Text(), nullable=True),
            sa.Column("page_count", sa.Integer(), nullable=True),
            sa.Column("page_texts_json", sa.JSON(), nullable=True),
            sa.Column("provenance_json", sa.JSON(), nullable=True),
            sa.Column("analysis_summary", sa.Text(), nullable=True),
            sa.Column("error_code", sa.String(length=100), nullable=True),
            sa.Column("error_detail", sa.Text(), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("detected_scheme", sa.String(length=50), nullable=True),
            sa.Column("detected_scheme_confidence", sa.Float(), nullable=True),
            sa.Column("scheme_version", sa.String(length=100), nullable=True),
            sa.Column("issuer_name", sa.String(length=255), nullable=True),
            sa.Column("report_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("overall_score", sa.Float(), nullable=True),
            sa.Column("max_score", sa.Float(), nullable=True),
            sa.Column("score_percentage", sa.Float(), nullable=True),
            sa.Column("outcome_status", sa.String(length=50), nullable=True),
            sa.Column("source_sheet_count", sa.Integer(), nullable=True),
            sa.Column("has_tabular_data", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("classification_basis_json", sa.JSON(), nullable=True),
            sa.Column("score_breakdown_json", sa.JSON(), nullable=True),
            sa.Column("evidence_preview_json", sa.JSON(), nullable=True),
            sa.Column("positive_summary_json", sa.JSON(), nullable=True),
            sa.Column("nonconformity_summary_json", sa.JSON(), nullable=True),
            sa.Column("improvement_summary_json", sa.JSON(), nullable=True),
            sa.Column("promotion_summary_json", sa.JSON(), nullable=True),
            sa.Column("processing_warnings_json", sa.JSON(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()
            ),
            sa.Column("reference_number", sa.String(length=20), nullable=False),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_id", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_unique_constraint("external_audit_import_jobs", "uq_external_audit_import_job_idempotency"):
        op.create_unique_constraint(
            "uq_external_audit_import_job_idempotency",
            "external_audit_import_jobs",
            ["audit_run_id", "source_document_asset_id", "source_checksum_sha256"],
        )

    index_specs = (
        ("ix_external_audit_import_jobs_audit_run_id", ["audit_run_id"], False),
        ("ix_external_audit_import_jobs_source_document_asset_id", ["source_document_asset_id"], False),
        ("ix_external_audit_import_jobs_tenant_id", ["tenant_id"], False),
        ("ix_external_audit_import_jobs_status", ["status"], False),
        ("ix_external_audit_import_jobs_source_checksum_sha256", ["source_checksum_sha256"], False),
        ("ix_external_audit_import_jobs_idempotency_key", ["idempotency_key"], True),
        ("ix_external_audit_import_jobs_reference_number", ["reference_number"], True),
        ("ix_external_audit_import_jobs_created_at", ["created_at"], False),
        ("ix_external_audit_import_jobs_detected_scheme", ["detected_scheme"], False),
        ("ix_external_audit_import_jobs_tenant_status", ["tenant_id", "status"], False),
    )
    for index_name, columns, unique in index_specs:
        if not _has_index("external_audit_import_jobs", index_name):
            op.create_index(index_name, "external_audit_import_jobs", columns, unique=unique)


def _ensure_drafts_table() -> None:
    if not _has_table("external_audit_import_drafts"):
        op.create_table(
            "external_audit_import_drafts",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(
                "import_job_id",
                sa.Integer(),
                sa.ForeignKey("external_audit_import_jobs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "audit_run_id",
                sa.Integer(),
                sa.ForeignKey("audit_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("severity", sa.String(length=50), nullable=False, server_default="medium"),
            sa.Column("finding_type", sa.String(length=50), nullable=False, server_default="nonconformity"),
            sa.Column("confidence_score", sa.Float(), nullable=True),
            sa.Column("competence_verdict", sa.String(length=50), nullable=True),
            sa.Column("source_pages_json", sa.JSON(), nullable=True),
            sa.Column("evidence_snippets_json", sa.JSON(), nullable=True),
            sa.Column("mapped_frameworks_json", sa.JSON(), nullable=True),
            sa.Column("mapped_standards_json", sa.JSON(), nullable=True),
            sa.Column("provenance_json", sa.JSON(), nullable=True),
            sa.Column("suggested_action_title", sa.String(length=300), nullable=True),
            sa.Column("suggested_action_description", sa.Text(), nullable=True),
            sa.Column("suggested_risk_title", sa.String(length=300), nullable=True),
            sa.Column("review_notes", sa.Text(), nullable=True),
            sa.Column("promoted_finding_id", sa.Integer(), sa.ForeignKey("audit_findings.id"), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()
            ),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_id", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    index_specs = (
        ("ix_external_audit_import_drafts_import_job_id", ["import_job_id"], False),
        ("ix_external_audit_import_drafts_audit_run_id", ["audit_run_id"], False),
        ("ix_external_audit_import_drafts_tenant_id", ["tenant_id"], False),
        ("ix_external_audit_import_drafts_status", ["status"], False),
        ("ix_external_audit_import_drafts_promoted_finding_id", ["promoted_finding_id"], False),
        ("ix_external_audit_import_drafts_created_at", ["created_at"], False),
        ("ix_external_audit_import_drafts_job_status", ["import_job_id", "status"], False),
    )
    for index_name, columns, unique in index_specs:
        if not _has_index("external_audit_import_drafts", index_name):
            op.create_index(index_name, "external_audit_import_drafts", columns, unique=unique)


def upgrade() -> None:
    _ensure_jobs_table()
    _ensure_drafts_table()


def downgrade() -> None:
    # This recovery migration is intentionally non-destructive on downgrade.
    # The tables may have been created manually or by prior hotfixes in some
    # environments, so dropping them here would risk deleting live audit data.
    return
