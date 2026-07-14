"""Add durable, chunked external-audit promotion state.

Revision ID: 20260714_e0_promote_async
Revises: 20260714_am_thread
Create Date: 2026-07-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_e0_promote_async"
down_revision: Union[str, Sequence[str], None] = "20260714_am_thread"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_column(table_name: str, column_name: str) -> bool:
    return _inspector().has_table(table_name) and column_name in {
        column["name"] for column in _inspector().get_columns(table_name)
    }


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def upgrade() -> None:
    if _inspector().has_table("external_audit_import_jobs"):
        columns = (
            ("promote_attempt", sa.Column("promote_attempt", sa.Integer(), nullable=False, server_default="0")),
            (
                "promote_lease_expires_at",
                sa.Column("promote_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
            ),
            ("promote_total", sa.Column("promote_total", sa.Integer(), nullable=True)),
            ("promote_succeeded", sa.Column("promote_succeeded", sa.Integer(), nullable=True, server_default="0")),
            ("promote_failed", sa.Column("promote_failed", sa.Integer(), nullable=True, server_default="0")),
            ("promote_progress_json", sa.Column("promote_progress_json", sa.JSON(), nullable=True)),
        )
        for name, column in columns:
            if not _has_column("external_audit_import_jobs", name):
                op.add_column("external_audit_import_jobs", column)

    if _inspector().has_table("external_audit_import_drafts"):
        if not _has_column("external_audit_import_drafts", "promoted_at"):
            op.add_column(
                "external_audit_import_drafts",
                sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
            )
        if not _has_column("external_audit_import_drafts", "promotion_error_code"):
            op.add_column(
                "external_audit_import_drafts",
                sa.Column("promotion_error_code", sa.String(length=64), nullable=True),
            )

    if _inspector().has_table("external_audit_records") and not _has_index(
        "external_audit_records", "uq_external_audit_records_import_job_id"
    ):
        # Preserve the newest canonical registry row before enforcing idempotency.
        # The predicate keeps historical rows with NULL import_job_id unconstrained.
        op.execute(sa.text("""
                DELETE FROM external_audit_records
                WHERE import_job_id IS NOT NULL
                  AND id NOT IN (
                      SELECT max_id FROM (
                          SELECT MAX(id) AS max_id
                          FROM external_audit_records
                          WHERE import_job_id IS NOT NULL
                          GROUP BY import_job_id
                      ) AS deduplicated
                  )
                """))
        op.create_index(
            "uq_external_audit_records_import_job_id",
            "external_audit_records",
            ["import_job_id"],
            unique=True,
            postgresql_where=sa.text("import_job_id IS NOT NULL"),
            sqlite_where=sa.text("import_job_id IS NOT NULL"),
        )


def downgrade() -> None:
    if _inspector().has_table("external_audit_records") and _has_index(
        "external_audit_records", "uq_external_audit_records_import_job_id"
    ):
        op.drop_index("uq_external_audit_records_import_job_id", table_name="external_audit_records")

    if _inspector().has_table("external_audit_import_drafts"):
        if _has_column("external_audit_import_drafts", "promotion_error_code"):
            op.drop_column("external_audit_import_drafts", "promotion_error_code")
        if _has_column("external_audit_import_drafts", "promoted_at"):
            op.drop_column("external_audit_import_drafts", "promoted_at")

    if _inspector().has_table("external_audit_import_jobs"):
        for column_name in (
            "promote_progress_json",
            "promote_failed",
            "promote_succeeded",
            "promote_total",
            "promote_lease_expires_at",
            "promote_attempt",
        ):
            if _has_column("external_audit_import_jobs", column_name):
                op.drop_column("external_audit_import_jobs", column_name)
