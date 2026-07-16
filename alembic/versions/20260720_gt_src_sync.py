"""Evidence source integrity CHECK + orphan report; finding↔risk junction sync.

Revision ID: 20260720_gt_src_sync
Revises: 20260720_capa_src_chk
Create Date: 2026-07-20

GT-UAT R63 + R48:
- CHECK evidence_assets.source_id is non-empty (no polymorphic FK)
- Log orphan counts per source_module (advisory; never invent tenants)
- Idempotent backfill audit_finding_risks from risk_ids_json drift
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_gt_src_sync"
down_revision: Union[str, Sequence[str], None] = "20260720_capa_src_chk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

EVIDENCE_TABLE = "evidence_assets"
SOURCE_ID_CONSTRAINT = "ck_evidence_assets_source_id_present"
SOURCE_ID_SQL = "source_id IS NOT NULL AND length(trim(source_id)) > 0"

# Modules with integer parent tables (skip action — uses action_key strings).
_ORPHAN_PARENTS = (
    ("incident", "incidents"),
    ("near_miss", "near_misses"),
    ("road_traffic_collision", "road_traffic_collisions"),
    ("complaint", "complaints"),
    ("investigation", "investigation_runs"),
    ("audit", "audit_runs"),
    ("asset", "assets"),
    ("certificate", "certificates"),
    ("assessment", "assessment_runs"),
    ("induction", "induction_runs"),
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _constraint_names(table: str) -> set[str]:
    if not _inspector().has_table(table):
        return set()
    return {c["name"] for c in _inspector().get_check_constraints(table)}


def _create_source_id_check() -> None:
    if not _inspector().has_table(EVIDENCE_TABLE):
        return
    if SOURCE_ID_CONSTRAINT in _constraint_names(EVIDENCE_TABLE):
        return
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(EVIDENCE_TABLE) as batch_op:
            batch_op.create_check_constraint(SOURCE_ID_CONSTRAINT, SOURCE_ID_SQL)
        return
    op.create_check_constraint(SOURCE_ID_CONSTRAINT, EVIDENCE_TABLE, SOURCE_ID_SQL)


def _drop_source_id_check() -> None:
    if SOURCE_ID_CONSTRAINT not in _constraint_names(EVIDENCE_TABLE):
        return
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(EVIDENCE_TABLE) as batch_op:
            batch_op.drop_constraint(SOURCE_ID_CONSTRAINT, type_="check")
        return
    op.drop_constraint(SOURCE_ID_CONSTRAINT, EVIDENCE_TABLE, type_="check")


def _report_orphans() -> None:
    """Advisory orphan counts — never fail the migration."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    inspector = _inspector()
    if not inspector.has_table(EVIDENCE_TABLE):
        return

    for source_module, parent_table in _ORPHAN_PARENTS:
        if not inspector.has_table(parent_table):
            continue
        result = bind.execute(sa.text(f"""
                SELECT COUNT(*) FROM {EVIDENCE_TABLE} AS ea
                WHERE ea.source_module = :source_module
                  AND NOT EXISTS (
                    SELECT 1 FROM {parent_table} AS parent
                    WHERE CAST(parent.id AS VARCHAR) = ea.source_id
                  )
                """).bindparams(source_module=source_module))
        count = int(result.scalar() or 0)
        if count:
            logger.warning(
                "evidence_assets orphan report: source_module=%s orphans=%s (no FK enforced)",
                source_module,
                count,
            )


def _sync_finding_risk_junction() -> None:
    """Re-sync junction from risk_ids_json where drift remains (idempotent)."""
    inspector = _inspector()
    if not inspector.has_table("audit_findings") or not inspector.has_table("audit_finding_risks"):
        return
    if not inspector.has_table("risks_v2"):
        return

    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("""
                INSERT INTO audit_finding_risks (audit_finding_id, risk_id)
                SELECT af.id, candidate.risk_id
                FROM audit_findings AS af
                CROSS JOIN LATERAL (
                    SELECT CAST(value AS INTEGER) AS risk_id
                    FROM jsonb_array_elements_text(
                        CASE
                            WHEN af.risk_ids_json IS NULL THEN '[]'::jsonb
                            WHEN jsonb_typeof(af.risk_ids_json::jsonb) = 'array'
                            THEN af.risk_ids_json::jsonb
                            ELSE '[]'::jsonb
                        END
                    )
                    WHERE value ~ '^[0-9]+$'
                ) AS candidate
                JOIN risks_v2 AS risk
                  ON risk.id = candidate.risk_id
                 AND risk.tenant_id = af.tenant_id
                ON CONFLICT (audit_finding_id, risk_id) DO NOTHING
                """))
        return

    op.execute(sa.text("""
            INSERT OR IGNORE INTO audit_finding_risks (audit_finding_id, risk_id)
            SELECT af.id, CAST(entry.value AS INTEGER)
            FROM audit_findings AS af
            JOIN json_each(
                CASE
                    WHEN af.risk_ids_json IS NULL THEN '[]'
                    WHEN json_valid(af.risk_ids_json)
                     AND json_type(af.risk_ids_json) = 'array'
                    THEN af.risk_ids_json
                    ELSE '[]'
                END
            ) AS entry
            JOIN risks_v2 AS risk
              ON risk.id = CAST(entry.value AS INTEGER)
             AND risk.tenant_id = af.tenant_id
            WHERE entry.type = 'integer'
               OR (
                    entry.type = 'text'
                AND entry.value GLOB '[0-9]*'
                AND entry.value NOT GLOB '*[^0-9]*'
               )
            """))


def upgrade() -> None:
    _create_source_id_check()
    _report_orphans()
    _sync_finding_risk_junction()


def downgrade() -> None:
    _drop_source_id_check()
    # Junction rows from sync are additive; leave in place on downgrade.
