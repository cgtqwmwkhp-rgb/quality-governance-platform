"""Repair Near Miss contract FKs that do not belong to the record tenant.

Revision ID: 20260826_nm_contract_tenant
Revises: 20260825_merge_chal_wit
Create Date: 2026-08-26

The original Near Miss contract backfill allowed global contracts. Runtime
validation only accepts contracts owned by the Near Miss tenant. Clear any
incompatible links that may already have been backfilled before the original
migration was tightened.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260826_nm_contract_tenant"
down_revision: Union[str, Sequence[str], None] = "20260825_merge_chal_wit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CLEAR_INVALID_CONTRACTS_SQL = """
UPDATE near_misses
SET contract_id = NULL
WHERE contract_id IS NOT NULL
  AND NOT EXISTS (
        SELECT 1
        FROM contracts c
        WHERE c.id = near_misses.contract_id
          AND c.tenant_id = near_misses.tenant_id
  )
"""


def upgrade() -> None:
    op.execute(CLEAR_INVALID_CONTRACTS_SQL)


def downgrade() -> None:
    # Cleared cross-tenant/global links must not be recreated.
    pass
