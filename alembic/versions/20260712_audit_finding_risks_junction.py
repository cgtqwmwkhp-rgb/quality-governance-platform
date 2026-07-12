"""Create and backfill the audit finding to enterprise risk junction.

Revision ID: 20260712_af_risks_jn
Revises: 20260711_ctl_docs_create
Create Date: 2026-07-12

The legacy audit_findings.risk_ids_json column remains in place for one
transition release while application code dual-writes both representations.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260712_af_risks_jn"
down_revision: Union[str, Sequence[str], None] = "20260711_ctl_docs_create"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                INSERT INTO audit_finding_risks (audit_finding_id, risk_id)
                SELECT af.id, candidate.risk_id
                FROM audit_findings AS af
                CROSS JOIN LATERAL (
                    SELECT CAST(value AS INTEGER) AS risk_id
                    FROM jsonb_array_elements_text(
                        CASE
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
                """
            )
        )
        return

    # SQLite support keeps local migration tests and development databases viable.
    op.execute(
        sa.text(
            """
            INSERT OR IGNORE INTO audit_finding_risks (audit_finding_id, risk_id)
            SELECT af.id, CAST(entry.value AS INTEGER)
            FROM audit_findings AS af
            JOIN json_each(
                CASE
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
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        "audit_finding_risks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("audit_finding_id", sa.Integer(), nullable=False),
        sa.Column("risk_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["audit_finding_id"],
            ["audit_findings.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["risk_id"], ["risks_v2.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "audit_finding_id",
            "risk_id",
            name="uq_audit_finding_risks_finding_risk",
        ),
    )
    op.create_index(
        "ix_audit_finding_risks_audit_finding_id",
        "audit_finding_risks",
        ["audit_finding_id"],
    )
    op.create_index(
        "ix_audit_finding_risks_risk_id",
        "audit_finding_risks",
        ["risk_id"],
    )
    _backfill()


def downgrade() -> None:
    op.drop_index(
        "ix_audit_finding_risks_risk_id",
        table_name="audit_finding_risks",
    )
    op.drop_index(
        "ix_audit_finding_risks_audit_finding_id",
        table_name="audit_finding_risks",
    )
    op.drop_table("audit_finding_risks")
