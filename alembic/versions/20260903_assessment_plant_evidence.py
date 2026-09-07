"""Plant evidence on assessment_runs (CB-UI-3).

Revision ID: 20260903_asm_plant_evid
Revises: 20260903_cb_bind_mode

Starting a family demonstration from a plant cell records *which machine it
happened on*: make, model, serial, or the PAMS plant id, any subset, all
optional. One nullable JSON column rather than a table, because there is no
entity here to own a row — the evidence has no life outside the run it belongs
to, and giving it a table would invite a second plant registry next to PAMS.

It is not four board squares and it is not an OEM catalogue (CB-OEM owns
make/model as data). Null means the assessor recorded none, which is a complete
family assessment and not a missing one, so there is no backfill and no default.

The parent is the real Alembic head from ``ScriptDirectory``/``alembic heads``
— ``20260903_cb_bind_mode`` — not the filename that sorts last. Filenames in
this tree do not follow the chain: ``20260901_*`` revisions chain *after*
``20261119_*``, so picking the last file forks the graph and only
``alembic upgrade head`` finds out.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260903_asm_plant_evid"
down_revision: Union[str, Sequence[str], None] = "20260903_cb_bind_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "assessment_runs"
COLUMN = "plant_evidence"


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in _inspector().get_columns(table_name)}


def upgrade() -> None:
    if not _has_table(TABLE):
        return
    if COLUMN in _columns(TABLE):
        return
    # Nullable with no server default, so the add is a metadata-only change on
    # Postgres and re-running the revision is a no-op. JSON rather than JSONB:
    # nothing queries inside this column, and ``JSON`` is what the model
    # declares and what SQLite understands in the test path.
    op.add_column(TABLE, sa.Column(COLUMN, sa.JSON(), nullable=True))


def downgrade() -> None:
    """Drop the column. Evidence recorded against past runs is lost with it.

    Stated rather than worked around: there is nowhere else on the run to move
    make/model/serial to, and writing it into ``notes`` on the way out would
    turn structured evidence into prose that a re-upgrade could not recover.
    The runs, their outcomes and their demonstrations are untouched.
    """
    if not _has_table(TABLE):
        return
    if COLUMN not in _columns(TABLE):
        return
    op.drop_column(TABLE, COLUMN)
