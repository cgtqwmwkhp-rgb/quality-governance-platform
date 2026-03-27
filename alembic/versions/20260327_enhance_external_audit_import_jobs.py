"""Enhance external audit import jobs with normalized review state.

Revision ID: 20260327_ext_audit_import_jobs
Revises: 20260327_documents_updated_by
Create Date: 2026-03-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260327_ext_audit_import_jobs"
down_revision: Union[str, None] = "20260327_documents_updated_by"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _has_table("external_audit_import_jobs"):
        return

    columns = [
        ("detected_scheme", sa.String(length=50), True),
        ("detected_scheme_confidence", sa.Float(), True),
        ("scheme_version", sa.String(length=100), True),
        ("issuer_name", sa.String(length=255), True),
        ("report_date", sa.DateTime(timezone=True), True),
        ("overall_score", sa.Float(), True),
        ("max_score", sa.Float(), True),
        ("score_percentage", sa.Float(), True),
        ("outcome_status", sa.String(length=50), True),
        ("source_sheet_count", sa.Integer(), True),
        ("has_tabular_data", sa.Boolean(), False),
        ("classification_basis_json", sa.JSON(), True),
        ("score_breakdown_json", sa.JSON(), True),
        ("evidence_preview_json", sa.JSON(), True),
        ("positive_summary_json", sa.JSON(), True),
        ("nonconformity_summary_json", sa.JSON(), True),
        ("improvement_summary_json", sa.JSON(), True),
        ("promotion_summary_json", sa.JSON(), True),
        ("processing_warnings_json", sa.JSON(), True),
    ]

    for column_name, column_type, nullable in columns:
        if not _has_column("external_audit_import_jobs", column_name):
            op.add_column(
                "external_audit_import_jobs",
                sa.Column(column_name, column_type, nullable=nullable, server_default=sa.text("false"))
                if column_name == "has_tabular_data"
                else sa.Column(column_name, column_type, nullable=nullable),
            )

    if _has_column("external_audit_import_jobs", "has_tabular_data"):
        op.execute("UPDATE external_audit_import_jobs SET has_tabular_data = false WHERE has_tabular_data IS NULL")
        op.alter_column("external_audit_import_jobs", "has_tabular_data", server_default=None)

    if not _has_index("external_audit_import_jobs", "ix_external_audit_import_jobs_detected_scheme"):
        op.create_index(
            "ix_external_audit_import_jobs_detected_scheme",
            "external_audit_import_jobs",
            ["detected_scheme"],
        )


def downgrade() -> None:
    if not _has_table("external_audit_import_jobs"):
        return

    if _has_index("external_audit_import_jobs", "ix_external_audit_import_jobs_detected_scheme"):
        op.drop_index("ix_external_audit_import_jobs_detected_scheme", table_name="external_audit_import_jobs")

    for column_name in [
        "processing_warnings_json",
        "promotion_summary_json",
        "improvement_summary_json",
        "nonconformity_summary_json",
        "positive_summary_json",
        "evidence_preview_json",
        "score_breakdown_json",
        "classification_basis_json",
        "has_tabular_data",
        "source_sheet_count",
        "outcome_status",
        "score_percentage",
        "max_score",
        "overall_score",
        "report_date",
        "issuer_name",
        "scheme_version",
        "detected_scheme_confidence",
        "detected_scheme",
    ]:
        if _has_column("external_audit_import_jobs", column_name):
            op.drop_column("external_audit_import_jobs", column_name)
