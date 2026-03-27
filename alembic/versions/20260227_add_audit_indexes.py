"""Add performance indexes to audit tables.

Revision ID: 20260227_audit_idx
Revises: 20260222_soft_delete
Create Date: 2026-02-27 10:00:00.000000

Adds indexes on columns used in WHERE, ORDER BY, and JOIN clauses
across audit_sections, audit_questions, audit_runs, audit_responses,
audit_findings, and audit_templates tables.
"""

from alembic import op
from sqlalchemy import inspect, text

revision = "20260227_audit_idx"
down_revision = "20260222_soft_delete"
branch_labels = None
depends_on = None


def _index_exists(conn, index_name: str) -> bool:
    inspector = inspect(conn)
    for table_name in inspector.get_table_names():
        if any(index["name"] == index_name for index in inspector.get_indexes(table_name)):
            return True
    return False


def _table_exists(conn, table_name: str) -> bool:
    return inspect(conn).has_table(table_name)


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return column_name in {column["name"] for column in inspect(conn).get_columns(table_name)}


def _has_duplicates(conn, table: str, columns: list[str]) -> bool:
    col_str = ", ".join(f'"{c}"' for c in columns)
    result = conn.execute(
        text(f"SELECT 1 FROM \"{table}\" GROUP BY {col_str} HAVING COUNT(*) > 1 LIMIT 1")
    )
    return result.scalar() is not None


def _safe_create_index(conn, idx_name: str, table: str, columns: list[str], unique: bool = False):
    if not _table_exists(conn, table):
        return
    for col in columns:
        if not _column_exists(conn, table, col):
            return
    if _index_exists(conn, idx_name):
        return
    if unique and _has_duplicates(conn, table, columns):
        col_str = ", ".join(f'"{c}"' for c in columns)
        conn.execute(text(f'CREATE INDEX "{idx_name}" ON "{table}" ({col_str})'))
        return
    unique_str = "UNIQUE " if unique else ""
    col_str = ", ".join(f'"{c}"' for c in columns)
    conn.execute(text(f'CREATE {unique_str}INDEX "{idx_name}" ON "{table}" ({col_str})'))


def upgrade() -> None:
    conn = op.get_bind()

    _safe_create_index(conn, "ix_audit_sections_template_id", "audit_sections", ["template_id"])

    _safe_create_index(conn, "ix_audit_questions_template_id", "audit_questions", ["template_id"])
    _safe_create_index(conn, "ix_audit_questions_section_id", "audit_questions", ["section_id"])
    _safe_create_index(conn, "ix_audit_questions_template_active", "audit_questions", ["template_id", "is_active"])

    _safe_create_index(conn, "ix_audit_runs_template_id", "audit_runs", ["template_id"])
    _safe_create_index(conn, "ix_audit_runs_status", "audit_runs", ["status"])
    _safe_create_index(conn, "ix_audit_runs_assigned_to_id", "audit_runs", ["assigned_to_id"])
    _safe_create_index(conn, "ix_audit_runs_created_at_desc", "audit_runs", ["created_at"])

    _safe_create_index(conn, "ix_audit_responses_run_id", "audit_responses", ["run_id"])
    _safe_create_index(conn, "uq_audit_responses_run_question", "audit_responses", ["run_id", "question_id"], unique=True)

    _safe_create_index(conn, "ix_audit_findings_run_id", "audit_findings", ["run_id"])
    _safe_create_index(conn, "ix_audit_findings_status", "audit_findings", ["status"])
    _safe_create_index(conn, "ix_audit_findings_created_at_desc", "audit_findings", ["created_at"])

    _safe_create_index(conn, "ix_audit_templates_is_published", "audit_templates", ["is_published"])
    _safe_create_index(conn, "ix_audit_templates_is_active", "audit_templates", ["is_active"])


def downgrade() -> None:
    conn = op.get_bind()
    for idx_name in [
        "ix_audit_templates_is_active",
        "ix_audit_templates_is_published",
        "ix_audit_findings_created_at_desc",
        "ix_audit_findings_status",
        "ix_audit_findings_run_id",
        "uq_audit_responses_run_question",
        "ix_audit_responses_run_id",
        "ix_audit_runs_created_at_desc",
        "ix_audit_runs_assigned_to_id",
        "ix_audit_runs_status",
        "ix_audit_runs_template_id",
        "ix_audit_questions_template_active",
        "ix_audit_questions_section_id",
        "ix_audit_questions_template_id",
        "ix_audit_sections_template_id",
    ]:
        if _index_exists(conn, idx_name):
            conn.execute(text(f'DROP INDEX IF EXISTS "{idx_name}"'))
