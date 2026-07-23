"""Incident contract FK, medical assistance, emergency services.

Revision ID: 20260812_hs_cme
Revises: 20260811_hs_manual_hours
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_hs_cme"
down_revision: Union[str, Sequence[str], None] = "20260811_hs_manual_hours"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("contract_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_incidents_contract_id",
        "incidents",
        "contracts",
        ["contract_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_incidents_contract_id", "incidents", ["contract_id"])

    op.add_column(
        "incidents",
        sa.Column("medical_assistance", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "incidents",
        sa.Column("emergency_services", sa.JSON(), nullable=True),
    )

    # Seed emergency_services lookup (global/null tenant) for Admin → Lookups.
    op.execute("""
        INSERT INTO lookup_options (
            tenant_id, category, code, label, is_active, display_order, created_at, updated_at
        )
        SELECT NULL, v.category, v.code, v.label, true, v.display_order, NOW(), NOW()
        FROM (
            VALUES
                ('emergency_services', 'police', 'Police', 1),
                ('emergency_services', 'ambulance', 'Ambulance', 2),
                ('emergency_services', 'fire', 'Fire & rescue', 3),
                ('emergency_services', 'recovery', 'Recovery', 4)
        ) AS v(category, code, label, display_order)
        WHERE NOT EXISTS (
            SELECT 1 FROM lookup_options l
            WHERE l.category = v.category AND l.code = v.code AND l.tenant_id IS NULL
        )
        """)


def downgrade() -> None:
    op.drop_index("ix_incidents_contract_id", table_name="incidents")
    op.drop_constraint("fk_incidents_contract_id", "incidents", type_="foreignkey")
    op.drop_column("incidents", "emergency_services")
    op.drop_column("incidents", "medical_assistance")
    op.drop_column("incidents", "contract_id")
