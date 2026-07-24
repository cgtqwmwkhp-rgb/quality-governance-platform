"""Near Miss contract SSOT: add contract_id FK, backfill from legacy contract code/name.

Revision ID: 20260816_nm_contract_fk
Revises: 20260815_safety_insights
Create Date: 2026-08-16

Near Miss has historically stored the customer/contract as a free-text
``contract`` string (a customers-lookup code, e.g. "ukpn"). This adds a
``contract_id`` FK to ``contracts.id`` — the same golden-thread pattern used
by Incident and Complaint — and backfills it by matching the legacy
``contract`` string against ``contracts.code``/``contracts.name`` (tenant or
global rows). The legacy ``contract`` column is kept as-is for read
compatibility during the transition; it is not dropped or made nullable.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_nm_contract_fk"
down_revision: Union[str, Sequence[str], None] = "20260815_safety_insights"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "near_misses",
        sa.Column("contract_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_near_misses_contract_id",
        "near_misses",
        "contracts",
        ["contract_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_near_misses_contract_id", "near_misses", ["contract_id"])

    # Backfill: match legacy `contract` code/name string to a contracts row
    # scoped to the near-miss's tenant (or a global/null-tenant contract).
    # Written as a portable correlated subquery (works on SQLite + Postgres).
    op.execute(
        """
        UPDATE near_misses
        SET contract_id = (
            SELECT c.id
            FROM contracts c
            WHERE (c.tenant_id = near_misses.tenant_id OR c.tenant_id IS NULL)
              AND (
                    lower(c.code) = lower(near_misses.contract)
                    OR lower(c.name) = lower(near_misses.contract)
                  )
            ORDER BY (c.tenant_id IS NOT NULL) DESC, c.id ASC
            LIMIT 1
        )
        WHERE near_misses.contract_id IS NULL
          AND near_misses.contract IS NOT NULL
          AND EXISTS (
                SELECT 1 FROM contracts c
                WHERE (c.tenant_id = near_misses.tenant_id OR c.tenant_id IS NULL)
                  AND (
                        lower(c.code) = lower(near_misses.contract)
                        OR lower(c.name) = lower(near_misses.contract)
                      )
          )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_near_misses_contract_id", table_name="near_misses")
    op.drop_constraint("fk_near_misses_contract_id", "near_misses", type_="foreignkey")
    op.drop_column("near_misses", "contract_id")
