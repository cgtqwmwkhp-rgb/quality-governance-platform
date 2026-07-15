"""Create case_risk_links junction for case ↔ enterprise risk dual-write.

Revision ID: 20260719_case_risk_jn
Revises: 20260719_rls_gt_exp
Create Date: 2026-07-19

Golden-thread D05 MVP: normalized junction alongside legacy linked_risk_ids CSV
and risks_v2.linked_incidents JSONB. Legacy columns remain for one transition release.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260719_case_risk_jn"
down_revision: Union[str, Sequence[str], None] = "20260719_rls_gt_exp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_from_case_csv() -> None:
    """Backfill incident / near_miss / rta / complaint linked_risk_ids CSV."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    case_sources = (
        ("incident", "incidents"),
        ("near_miss", "near_misses"),
        ("rta", "road_traffic_collisions"),
        ("complaint", "complaints"),
    )

    for case_type, table in case_sources:
        inspector = sa.inspect(bind)
        if not inspector.has_table(table):
            continue

        op.execute(sa.text(f"""
                INSERT INTO case_risk_links (tenant_id, case_type, case_id, risk_id)
                SELECT src.tenant_id, :case_type, src.id, candidate.risk_id
                FROM {table} AS src
                CROSS JOIN LATERAL (
                    SELECT CAST(part AS INTEGER) AS risk_id
                    FROM regexp_split_to_table(COALESCE(src.linked_risk_ids, ''), ',') AS part
                    WHERE TRIM(part) ~ '^[0-9]+$'
                ) AS candidate
                JOIN risks_v2 AS risk
                  ON risk.id = candidate.risk_id
                 AND risk.tenant_id = src.tenant_id
                WHERE src.tenant_id IS NOT NULL
                ON CONFLICT (tenant_id, case_type, case_id, risk_id) DO NOTHING
                """).bindparams(case_type=case_type))


def _backfill_from_risk_linked_incidents() -> None:
    """Backfill from risks_v2.linked_incidents reference numbers."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = sa.inspect(bind)
    if not inspector.has_table("risks_v2"):
        return

    ref_sources = (
        ("incident", "incidents", "reference_number"),
        ("near_miss", "near_misses", "reference_number"),
        ("rta", "road_traffic_collisions", "reference_number"),
        ("complaint", "complaints", "reference_number"),
    )

    for case_type, table, ref_col in ref_sources:
        if not inspector.has_table(table):
            continue
        op.execute(sa.text(f"""
                INSERT INTO case_risk_links (tenant_id, case_type, case_id, risk_id)
                SELECT risk.tenant_id, :case_type, src.id, risk.id
                FROM risks_v2 AS risk
                CROSS JOIN LATERAL (
                    SELECT jsonb_array_elements_text(
                        CASE
                            WHEN jsonb_typeof(risk.linked_incidents::jsonb) = 'array'
                            THEN risk.linked_incidents::jsonb
                            ELSE '[]'::jsonb
                        END
                    ) AS ref
                ) AS elem
                JOIN {table} AS src
                  ON src.{ref_col} = elem.ref
                 AND src.tenant_id = risk.tenant_id
                WHERE risk.tenant_id IS NOT NULL
                ON CONFLICT (tenant_id, case_type, case_id, risk_id) DO NOTHING
                """).bindparams(case_type=case_type))


def upgrade() -> None:
    op.create_table(
        "case_risk_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("case_type", sa.String(length=32), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("risk_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["risk_id"], ["risks_v2.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "case_type",
            "case_id",
            "risk_id",
            name="uq_case_risk_links_tenant_case_risk",
        ),
    )
    op.create_index("ix_case_risk_links_tenant_id", "case_risk_links", ["tenant_id"])
    op.create_index("ix_case_risk_links_case_type", "case_risk_links", ["case_type"])
    op.create_index("ix_case_risk_links_case_id", "case_risk_links", ["case_id"])
    op.create_index("ix_case_risk_links_risk_id", "case_risk_links", ["risk_id"])
    op.create_index(
        "ix_case_risk_links_tenant_case",
        "case_risk_links",
        ["tenant_id", "case_type", "case_id"],
    )

    _backfill_from_case_csv()
    _backfill_from_risk_linked_incidents()


def downgrade() -> None:
    op.drop_index("ix_case_risk_links_tenant_case", table_name="case_risk_links")
    op.drop_index("ix_case_risk_links_risk_id", table_name="case_risk_links")
    op.drop_index("ix_case_risk_links_case_id", table_name="case_risk_links")
    op.drop_index("ix_case_risk_links_case_type", table_name="case_risk_links")
    op.drop_index("ix_case_risk_links_tenant_id", table_name="case_risk_links")
    op.drop_table("case_risk_links")
