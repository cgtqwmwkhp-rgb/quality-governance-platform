"""Migrate legacy risks data into enterprise risk register (risks_v2).

Revision ID: 20260220_risks_merge
Revises: 20260220_enterprise_rr
Create Date: 2026-02-20 15:00:00.000000

Consolidates the Library Risks module into the Enterprise Risk Register
by migrating any existing data from the `risks` table into `risks_v2`.
The legacy `risks` table is preserved (not dropped) so existing backend
routes continue to function during the transition period.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260220_risks_merge"
down_revision: Union[str, None] = "20260220_enterprise_rr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TREATMENT_MAP = {
    "accept": "tolerate",
    "mitigate": "treat",
    "transfer": "transfer",
    "avoid": "terminate",
}


def upgrade() -> None:
    conn = op.get_bind()

    rows = conn.execute(
        sa.text(
            "SELECT id, reference_number, title, description, category, "
            "subcategory, risk_source, risk_event, risk_consequence, "
            "likelihood, impact, risk_score, "
            "owner_id, department, "
            "review_frequency_months, next_review_date, "
            "treatment_strategy, treatment_plan, "
            "status, "
            "linked_audit_ids_json, linked_incident_ids_json, "
            "created_by_id, created_at, updated_at "
            "FROM risks WHERE is_active = true"
        )
    ).fetchall()

    if not rows:
        return

    for row in rows:
        ref = row.reference_number or f"LEGACY-{row.id}"
        treatment = TREATMENT_MAP.get(row.treatment_strategy or "", "treat")
        review_days = (row.review_frequency_months or 12) * 30
        context_parts = []
        if row.risk_event:
            context_parts.append(f"Event: {row.risk_event}")
        if row.risk_consequence:
            context_parts.append(f"Consequence: {row.risk_consequence}")
        context = "; ".join(context_parts) if context_parts else None

        existing = conn.execute(
            sa.text("SELECT id FROM risks_v2 WHERE reference = :ref"),
            {"ref": ref},
        ).fetchone()
        if existing:
            continue

        conn.execute(
            sa.text(
                "INSERT INTO risks_v2 ("
                "  reference, title, description, category, subcategory, "
                "  source, context, department, "
                "  inherent_likelihood, inherent_impact, inherent_score, "
                "  residual_likelihood, residual_impact, residual_score, "
                "  treatment_strategy, treatment_plan, "
                "  risk_owner_id, "
                "  status, review_frequency_days, next_review_date, "
                "  linked_audits, linked_incidents, "
                "  created_by, created_at, updated_at"
                ") VALUES ("
                "  :ref, :title, :desc, :cat, :subcat, "
                "  :source, :context, :dept, "
                "  :lh, :im, :score, "
                "  :lh, :im, :score, "
                "  :treatment, :plan, "
                "  :owner, "
                "  :status, :rev_days, :next_rev, "
                "  :audits, :incidents, "
                "  :created_by, :created_at, :updated_at"
                ")"
            ),
            {
                "ref": ref,
                "title": row.title,
                "desc": row.description,
                "cat": row.category or "operational",
                "subcat": row.subcategory,
                "source": row.risk_source,
                "context": context,
                "dept": row.department,
                "lh": row.likelihood or 3,
                "im": row.impact or 3,
                "score": row.risk_score or 9,
                "treatment": treatment,
                "plan": row.treatment_plan,
                "owner": row.owner_id,
                "status": row.status or "identified",
                "rev_days": review_days,
                "next_rev": row.next_review_date,
                "audits": row.linked_audit_ids_json,
                "incidents": row.linked_incident_ids_json,
                "created_by": row.created_by_id,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM risks_v2 WHERE reference LIKE 'LEGACY-%' OR reference LIKE 'RISK-%'"))
