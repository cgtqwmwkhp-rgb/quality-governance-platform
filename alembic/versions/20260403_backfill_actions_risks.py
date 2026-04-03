"""Backfill CAPA actions and Enterprise Risks for existing audit findings.

Findings promoted under the old logic had a narrow requires_action whitelist
and a severity gate that excluded 'low'.  This migration retroactively:

1. Sets corrective_action_required = true for all non-positive findings.
2. Creates CAPAAction rows for findings that lack one.
3. Creates EnterpriseRisk rows for findings that lack one.
4. Updates audit_findings.risk_ids_json with the new risk IDs.

Revision ID: c8d9e0f1a2b3
Revises: b7e8f9a0c1d2
Create Date: 2026-04-03
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from alembic import op
from sqlalchemy import text

revision = "c8d9e0f1a2b3"
down_revision = "b7e8f9a0c1d2"
branch_labels = None
depends_on = None

_POSITIVE_ONLY = ("positive_practice", "strength", "commendation")
_PRIORITY_MAP = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
_RISK_SCORES = {
    "critical": (4, 5),
    "high": (3, 4),
    "medium": (2, 3),
    "low": (1, 2),
}


def _next_capa_ref(conn, year: int, current_seq: int) -> tuple[str, int]:
    seq = current_seq + 1
    return f"CAPA-{year}-{seq:04d}", seq


def _next_risk_ref(conn, year: int, current_seq: int) -> tuple[str, int]:
    seq = current_seq + 1
    return f"RSK-{year}-{seq:04d}", seq


def upgrade() -> None:
    conn = op.get_bind()
    now_naive = datetime.utcnow().replace(microsecond=0)
    year = now_naive.year

    # ── Step 1: fix corrective_action_required ──────────────────────────
    conn.execute(
        text("""
            UPDATE audit_findings
            SET corrective_action_required = true,
                updated_at = :now
            WHERE corrective_action_required = false
              AND finding_type NOT IN ('positive_practice', 'strength', 'commendation')
        """),
        {"now": now_naive},
    )

    # ── Step 2: find findings needing CAPA actions ──────────────────────
    findings_for_capa = conn.execute(text("""
            SELECT af.id           AS finding_id,
                   af.run_id,
                   af.title        AS finding_title,
                   af.description  AS finding_desc,
                   af.severity,
                   af.corrective_action_due_date,
                   af.reference_number AS finding_ref,
                   af.tenant_id,
                   af.created_by_id,
                   ar.assigned_to_id,
                   ar.assurance_scheme,
                   ar.external_reference,
                   ar.reference_number AS run_ref
            FROM audit_findings af
            JOIN audit_runs ar ON ar.id = af.run_id
            WHERE af.corrective_action_required = true
              AND NOT EXISTS (
                  SELECT 1 FROM capa_actions ca
                  WHERE ca.source_type = 'audit_finding'
                    AND ca.source_id = af.id
              )
            ORDER BY af.id
        """)).fetchall()

    if findings_for_capa:
        max_capa_row = conn.execute(
            text("""
                SELECT COALESCE(MAX(
                    CAST(SUBSTRING(reference_number FROM '[0-9]+$') AS INTEGER)
                ), 0) AS max_seq
                FROM capa_actions
                WHERE reference_number LIKE :pattern
            """),
            {"pattern": f"CAPA-{year}-%"},
        ).fetchone()
        capa_seq = max_capa_row.max_seq if max_capa_row else 0

        for f in findings_for_capa:
            ref, capa_seq = _next_capa_ref(conn, year, capa_seq)
            priority = _PRIORITY_MAP.get(f.severity, "medium")
            title = (f"Action plan: {f.finding_title}" if f.finding_title else "Action plan")[:255]
            user_id = f.created_by_id or 1

            due_date = f.corrective_action_due_date
            if due_date and hasattr(due_date, "tzinfo") and due_date.tzinfo:
                due_date = due_date.replace(tzinfo=None)

            conn.execute(
                text("""
                    INSERT INTO capa_actions (
                        tenant_id, reference_number, title, description,
                        capa_type, status, priority,
                        source_type, source_id,
                        created_by_id, assigned_to_id,
                        due_date, iso_standard, clause_reference,
                        created_at, updated_at
                    ) VALUES (
                        :tenant_id, :ref, :title, :desc,
                        'corrective', 'open', :priority,
                        'audit_finding', :finding_id,
                        :created_by, :assigned_to,
                        :due_date, :iso_standard, :clause_ref,
                        :now, :now
                    )
                """),
                {
                    "tenant_id": f.tenant_id,
                    "ref": ref,
                    "title": title,
                    "desc": f.finding_desc or "",
                    "priority": priority,
                    "finding_id": f.finding_id,
                    "created_by": user_id,
                    "assigned_to": f.assigned_to_id,
                    "due_date": due_date,
                    "iso_standard": f.assurance_scheme,
                    "clause_ref": f.external_reference,
                    "now": now_naive,
                },
            )

    # ── Step 3: find findings needing Enterprise Risks ──────────────────
    findings_for_risk = conn.execute(text("""
            SELECT af.id           AS finding_id,
                   af.run_id,
                   af.title        AS finding_title,
                   af.description  AS finding_desc,
                   af.severity,
                   af.reference_number AS finding_ref,
                   af.tenant_id,
                   af.created_by_id,
                   af.risk_ids_json,
                   ar.assigned_to_id,
                   ar.assurance_scheme,
                   ar.reference_number AS run_ref,
                   ar.location
            FROM audit_findings af
            JOIN audit_runs ar ON ar.id = af.run_id
            WHERE af.severity IN ('critical', 'high', 'medium', 'low')
              AND NOT EXISTS (
                  SELECT 1 FROM risks_v2 rv
                  WHERE rv.linked_audits::text LIKE '%%' || af.reference_number || '%%'
                    AND rv.tenant_id IS NOT DISTINCT FROM af.tenant_id
              )
            ORDER BY af.id
        """)).fetchall()

    if findings_for_risk:
        max_risk_row = conn.execute(
            text("""
                SELECT COALESCE(MAX(
                    CAST(SUBSTRING(reference FROM '[0-9]+$') AS INTEGER)
                ), 0) AS max_seq
                FROM risks_v2
                WHERE reference LIKE :pattern
            """),
            {"pattern": f"RSK-{year}-%"},
        ).fetchone()
        risk_seq = max_risk_row.max_seq if max_risk_row else 0

        capa_lookup = {}
        if findings_for_capa or True:
            capa_rows = conn.execute(text("""
                    SELECT source_id, reference_number
                    FROM capa_actions
                    WHERE source_type = 'audit_finding'
                """)).fetchall()
            capa_lookup = {r.source_id: r.reference_number for r in capa_rows}

        for f in findings_for_risk:
            ref, risk_seq = _next_risk_ref(conn, year, risk_seq)
            likelihood, impact = _RISK_SCORES.get(f.severity, (1, 2))
            score = likelihood * impact
            title = (f"Audit escalation: {f.run_ref} / {f.finding_ref}")[:255]
            user_id = f.created_by_id or 1

            capa_ref = capa_lookup.get(f.finding_id)
            linked_actions = json.dumps([capa_ref] if capa_ref else [])
            linked_audits = json.dumps(sorted(set(filter(None, [f.run_ref, f.finding_ref]))))

            review_date = now_naive + timedelta(days=30)

            result = conn.execute(
                text("""
                    INSERT INTO risks_v2 (
                        tenant_id, reference, title, description,
                        category, subcategory, source, context,
                        department, location, process,
                        inherent_likelihood, inherent_impact, inherent_score,
                        residual_likelihood, residual_impact, residual_score,
                        risk_appetite, appetite_threshold, is_within_appetite,
                        treatment_strategy, treatment_plan,
                        risk_owner_id, status, review_frequency_days,
                        next_review_date, is_escalated,
                        escalation_reason, escalation_date,
                        linked_audits, linked_actions,
                        identified_date, created_at, updated_at, created_by
                    ) VALUES (
                        :tenant_id, :ref, :title, :desc,
                        'compliance', 'audit_finding', 'audit_finding',
                        :context, 'quality', :location, 'audit remediation',
                        :l, :i, :s,
                        :rl, :ri, :rs,
                        'cautious', 12, :within,
                        'treat',
                        'Raised automatically from an audit finding requiring remediation.',
                        :owner, 'open', 30,
                        :review_date, true,
                        :esc_reason, :esc_date,
                        :linked_audits::jsonb, :linked_actions::jsonb,
                        :now, :now, :now, :created_by
                    )
                    RETURNING id
                """),
                {
                    "tenant_id": f.tenant_id,
                    "ref": ref,
                    "title": title,
                    "desc": f.finding_desc or "",
                    "context": f"{f.assurance_scheme or 'audit'}:{f.run_ref}",
                    "location": f.location,
                    "l": likelihood,
                    "i": impact,
                    "s": score,
                    "rl": max(1, likelihood - 1),
                    "ri": impact,
                    "rs": max(1, (likelihood - 1) * impact),
                    "within": score <= 12,
                    "owner": f.assigned_to_id,
                    "esc_reason": f"Auto-escalated from {f.finding_ref}",
                    "esc_date": now_naive,
                    "linked_audits": linked_audits,
                    "linked_actions": linked_actions,
                    "review_date": review_date,
                    "now": now_naive,
                    "created_by": user_id,
                },
            )
            new_risk_id = result.fetchone()[0]

            existing_risk_ids = []
            if f.risk_ids_json:
                try:
                    existing_risk_ids = (
                        list(f.risk_ids_json) if isinstance(f.risk_ids_json, list) else json.loads(f.risk_ids_json)
                    )
                except (json.JSONDecodeError, TypeError):
                    existing_risk_ids = []

            updated_ids = sorted(set(existing_risk_ids) | {new_risk_id})
            conn.execute(
                text("""
                    UPDATE audit_findings
                    SET risk_ids_json = :ids::jsonb,
                        updated_at = :now
                    WHERE id = :fid
                """),
                {
                    "ids": json.dumps(updated_ids),
                    "now": now_naive,
                    "fid": f.finding_id,
                },
            )


def downgrade() -> None:
    pass
