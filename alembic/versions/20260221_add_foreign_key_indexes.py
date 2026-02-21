"""Add indexes on foreign key columns for join performance.

Revision ID: 20260221_fk_indexes
Revises: 20260221_integrity
Create Date: 2026-02-21

Foreign keys without indexes cause slow joins and cascading deletes.
This migration covers FK columns on the high-traffic tables: incidents,
risks, audits, and complaints (plus their child tables).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260221_fk_indexes"
down_revision: Union[str, None] = "20260221_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK_INDEXES: list[tuple[str, str]] = [
    # incidents
    ("incidents", "reporter_id"),
    ("incidents", "investigator_id"),
    ("incidents", "closed_by_id"),
    ("incidents", "sif_assessed_by_id"),
    # incident_actions
    ("incident_actions", "incident_id"),
    ("incident_actions", "owner_id"),
    ("incident_actions", "verified_by_id"),
    # risks
    ("risks", "owner_id"),
    ("risks", "created_by_id"),
    # risk_mitigations
    ("risk_mitigations", "risk_id"),
    ("risk_mitigations", "owner_id"),
    # risk_assessments
    ("risk_assessments", "risk_id"),
    ("risk_assessments", "assessed_by_id"),
    # audit_templates
    ("audit_templates", "created_by_id"),
    ("audit_templates", "archived_by_id"),
    # audit_sections
    ("audit_sections", "template_id"),
    # audit_questions
    ("audit_questions", "template_id"),
    ("audit_questions", "section_id"),
    # audit_runs
    ("audit_runs", "template_id"),
    ("audit_runs", "assigned_to_id"),
    ("audit_runs", "created_by_id"),
    # audit_responses
    ("audit_responses", "run_id"),
    ("audit_responses", "question_id"),
    # audit_findings
    ("audit_findings", "run_id"),
    ("audit_findings", "question_id"),
    ("audit_findings", "created_by_id"),
    # complaints
    ("complaints", "owner_id"),
    ("complaints", "closed_by_id"),
    # complaint_actions
    ("complaint_actions", "complaint_id"),
    ("complaint_actions", "owner_id"),
    ("complaint_actions", "verified_by_id"),
]

_COL_EXISTS = sa.text(
    "SELECT EXISTS ("
    "  SELECT 1 FROM information_schema.columns"
    "  WHERE table_name = :t AND column_name = :c"
    ")"
)


def upgrade() -> None:
    conn = op.get_bind()
    for table, column in _FK_INDEXES:
        if conn.execute(_COL_EXISTS, {"t": table, "c": column}).scalar():
            idx_name = f"ix_{table}_{column}"
            op.execute(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({column})"
            )


def downgrade() -> None:
    conn = op.get_bind()
    for table, column in reversed(_FK_INDEXES):
        idx_name = f"ix_{table}_{column}"
        result = conn.execute(
            sa.text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM pg_indexes"
                "  WHERE indexname = :idx"
                ")"
            ),
            {"idx": idx_name},
        )
        if result.scalar():
            op.drop_index(idx_name, table_name=table)
