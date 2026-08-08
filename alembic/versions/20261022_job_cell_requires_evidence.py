"""JL-UX-W4: mandatory-evidence flag on job cells.

Revision ID: 20261022_job_cell_req_ev
Revises: 20261021_job_nest_pdca
Create Date: 2026-10-22

Additive, one column on a table the JL chain already created and hardened:

``job_cells.requires_evidence`` — boolean NOT NULL DEFAULT false. It records
that a lane × step intersection is *expected* to hold evidence, so a cell that
is empty can be reported as a gap instead of reading as a deliberate blank.

Default false, not true: marking every existing cell mandatory would invent a
governance claim about packs this migration has never seen. Readiness itself
is **not** stored — it is derived on read from the cell's document refs and,
when assure is on, the Library / Document Control status of those documents.
There is no readiness, status or "last checked" column here for the same reason
W3 cached nothing: the document tables stay the source of truth.

No RLS changes: ``job_cells`` was hardened by 20261019 and no table is added.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_job_cell_req_ev"
down_revision: Union[str, Sequence[str], None] = "20261021_job_nest_pdca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

INDEX_NAME = "ix_job_cells_tenant_requires_evidence"


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(col["name"] == column_name for col in _inspector().get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(idx["name"] == index_name for idx in _inspector().get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("job_cells"):
        logger.warning("%s: job_cells missing — requires_evidence skipped", revision)
        return
    if not _column_exists("job_cells", "requires_evidence"):
        op.add_column(
            "job_cells",
            sa.Column(
                "requires_evidence",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if not _index_exists("job_cells", INDEX_NAME):
        # Readiness reads only the mandatory cells, so the index carries the
        # flag rather than being a bare tenant index that scans the whole pack.
        op.create_index(INDEX_NAME, "job_cells", ["tenant_id", "requires_evidence"])


def downgrade() -> None:
    if not _table_exists("job_cells"):
        return
    if _index_exists("job_cells", INDEX_NAME):
        op.drop_index(INDEX_NAME, table_name="job_cells")
    if _column_exists("job_cells", "requires_evidence"):
        op.drop_column("job_cells", "requires_evidence")
