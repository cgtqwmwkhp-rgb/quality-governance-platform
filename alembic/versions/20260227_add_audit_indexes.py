"""Add performance indexes to audit tables.

Revision ID: 20260227_audit_idx
Revises: 20260202_fix_status
Create Date: 2026-02-27 10:00:00.000000

Adds indexes on columns used in WHERE, ORDER BY, and JOIN clauses
across audit_sections, audit_questions, audit_runs, audit_responses,
audit_findings, and audit_templates tables.
"""

from alembic import op

revision = "20260227_audit_idx"
down_revision = "20260202_fix_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # audit_sections: FK lookups
    op.create_index("ix_audit_sections_template_id", "audit_sections", ["template_id"])

    # audit_questions: FK lookups and filtered queries
    op.create_index("ix_audit_questions_template_id", "audit_questions", ["template_id"])
    op.create_index("ix_audit_questions_section_id", "audit_questions", ["section_id"])
    op.create_index(
        "ix_audit_questions_template_active",
        "audit_questions",
        ["template_id", "is_active"],
    )

    # audit_runs: filtered listing and ordering
    op.create_index("ix_audit_runs_template_id", "audit_runs", ["template_id"])
    op.create_index("ix_audit_runs_status", "audit_runs", ["status"])
    op.create_index("ix_audit_runs_assigned_to_id", "audit_runs", ["assigned_to_id"])
    op.create_index(
        "ix_audit_runs_created_at_desc",
        "audit_runs",
        ["created_at"],
    )

    # audit_responses: FK lookups and duplicate prevention
    op.create_index("ix_audit_responses_run_id", "audit_responses", ["run_id"])
    op.create_index(
        "uq_audit_responses_run_question",
        "audit_responses",
        ["run_id", "question_id"],
        unique=True,
    )

    # audit_findings: filtered listing and ordering
    op.create_index("ix_audit_findings_run_id", "audit_findings", ["run_id"])
    op.create_index("ix_audit_findings_status", "audit_findings", ["status"])
    op.create_index(
        "ix_audit_findings_created_at_desc",
        "audit_findings",
        ["created_at"],
    )

    # audit_templates: filtered listing
    op.create_index("ix_audit_templates_is_published", "audit_templates", ["is_published"])
    op.create_index("ix_audit_templates_is_active", "audit_templates", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_audit_templates_is_active", table_name="audit_templates")
    op.drop_index("ix_audit_templates_is_published", table_name="audit_templates")
    op.drop_index("ix_audit_findings_created_at_desc", table_name="audit_findings")
    op.drop_index("ix_audit_findings_status", table_name="audit_findings")
    op.drop_index("ix_audit_findings_run_id", table_name="audit_findings")
    op.drop_index("uq_audit_responses_run_question", table_name="audit_responses")
    op.drop_index("ix_audit_responses_run_id", table_name="audit_responses")
    op.drop_index("ix_audit_runs_created_at_desc", table_name="audit_runs")
    op.drop_index("ix_audit_runs_assigned_to_id", table_name="audit_runs")
    op.drop_index("ix_audit_runs_status", table_name="audit_runs")
    op.drop_index("ix_audit_runs_template_id", table_name="audit_runs")
    op.drop_index("ix_audit_questions_template_active", table_name="audit_questions")
    op.drop_index("ix_audit_questions_section_id", table_name="audit_questions")
    op.drop_index("ix_audit_questions_template_id", table_name="audit_questions")
    op.drop_index("ix_audit_sections_template_id", table_name="audit_sections")
