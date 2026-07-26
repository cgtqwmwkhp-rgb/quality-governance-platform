"""Scope the investigation source uniqueness to the owning tenant.

Revision ID: 20260829_inv_tenant_src
Revises: 20260828_lookup_defaults
Create Date: 2026-08-29

uq_investigation_runs_source was global: (assigned_entity_type, assigned_entity_id).
Source ids are per-tenant sequences, so two organisations reporting their own near
miss can collide on the same integer id, and whichever tenant investigated first
silently blocked the other from creating an investigation at all. Re-key the index
on (tenant_id, assigned_entity_type, assigned_entity_id) so one source record still
has at most one investigation, but only within its own tenant.

tenant_id is NOT NULL on investigation_runs, so no row escapes the new index.

No de-duplication is required on the way up: the global index it replaces was
strictly stronger, so no tenant can already hold two investigations for one source.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260829_inv_tenant_src"
down_revision: Union[str, Sequence[str], None] = "20260828_lookup_defaults"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GLOBAL_INDEX = "uq_investigation_runs_source"
TENANT_INDEX = "uq_investigation_runs_tenant_source"

CROSS_TENANT_DUPLICATES_SQL = """
SELECT assigned_entity_type, assigned_entity_id, COUNT(*) AS run_count
FROM investigation_runs
GROUP BY assigned_entity_type, assigned_entity_id
HAVING COUNT(*) > 1
ORDER BY assigned_entity_type, assigned_entity_id
"""


def upgrade() -> None:
    op.drop_index(GLOBAL_INDEX, table_name="investigation_runs")
    op.create_index(
        TENANT_INDEX,
        "investigation_runs",
        ["tenant_id", "assigned_entity_type", "assigned_entity_id"],
        unique=True,
    )


def downgrade() -> None:
    """Restore the global index, refusing rather than deleting another tenant's work.

    Once tenants have investigated colliding source ids the old global index cannot be
    recreated without destroying rows (and, via ON DELETE CASCADE, their comments,
    actions, revision events and customer packs). Stop and make the operator decide.
    """
    duplicates = op.get_bind().execute(sa.text(CROSS_TENANT_DUPLICATES_SQL)).fetchall()
    if duplicates:
        collisions = ", ".join(f"{row[0]}:{row[1]} ({row[2]} runs)" for row in duplicates[:10])
        raise RuntimeError(
            f"Cannot restore global index {GLOBAL_INDEX}: {len(duplicates)} source record(s) are "
            f"investigated by more than one tenant — {collisions}. Resolve these rows by hand "
            "before downgrading; this migration will not delete another tenant's investigations."
        )

    op.drop_index(TENANT_INDEX, table_name="investigation_runs")
    op.create_index(
        GLOBAL_INDEX,
        "investigation_runs",
        ["assigned_entity_type", "assigned_entity_id"],
        unique=True,
    )
