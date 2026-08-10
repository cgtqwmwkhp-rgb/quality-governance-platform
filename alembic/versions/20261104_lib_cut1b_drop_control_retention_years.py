"""CUT-1b: drop controlled_documents.retention_period_years — one retention SoR

Revision ID: 20261104_lib_cut1b_drop
Revises: 20261103_lib_steward14
Create Date: 2026-08-10

Why this revision exists (ADR-0023 / F-7 §2 / CUT-1 / STEWARD-14)
-----------------------------------------------------------------
F-7 §2 assigns retention exactly one home: the category's machine-readable
policy (``document_categories.retention_years`` / ``retention_anchor``) copied
onto the Register row at file (``documents.retention_years`` /
``retention_anchor`` / ``retention_basis``), with ``documents.retention_until``
as the single disposal clock. ``controlled_documents.retention_period_years``
was a second answer to the same question, and it was not a dormant one:

    retention_period_years: Mapped[int] = mapped_column(Integer, default=7)

A SQLAlchemy ``default`` runs on every INSERT, so every controlled document
created since ``20260711_create_controlled_documents`` was stamped with seven
years — Citation (ATLAS)'s flat "7 Years / all employees" position, expressed as
code, regardless of what the document's category actually says. Two of the
categories STEWARD-14 decided are forty-year records. The single reader,
``POST /document-control/{id}/obsolete``, then turned that seven into the
archive's ``retention_end_date`` via ``timedelta(days=years * 365)``.

CUT-1 named the condition for this drop — "once no writer remains" — and
STEWARD-14 restated it. The application change in the same PR removes the last
writer (the model default) and the last reader (the obsolete route now derives
the archive date from the Register row through
``document_library_filing_service.supersede_retention_until``, or records NULL
when it is not derivable). This revision removes the column they wrote.

What it does — and does not do
------------------------------
- Drops one column from ``controlled_documents``. No other column, no other
  table, no data written anywhere.
- Does **not** copy the old value onto the Register. It is not a governance
  fact: it is a constructor default that nobody chose, so migrating it forward
  would be laundering Citation's flat seven years into the system of record that
  CUT-1 and STEWARD-14 built specifically to replace it.
- Does **not** touch ``obsolete_document_records``. Rows already written keep
  the ``retention_end_date`` they were given; re-dating an archive nobody
  re-reviewed is the same error as the CUT-1c backfill this project deferred.
- Does **not** backfill legacy ``documents.retention_until`` — CUT-1c, deferred.

What the deploy log will show
-----------------------------
Production row counts could not be queried when this revision was written (no
operator access to the production database from the authoring environment), so
the total and the number of rows holding anything other than the default seven
are logged at INFO immediately before the ``DROP``. If that second number is
zero, the drop destroyed only the default — which is what the code makes
likely, since no route, schema or script ever set the column to anything else.
A non-zero count is visible in the deploy log rather than inferred, and can be
acted on as a records question about specific documents.

Downgrade
---------
Recreates the column exactly as ``20260711_create_controlled_documents`` built
it: ``Integer NOT NULL DEFAULT 7``. That is a **schema** restore, not a data
one, and it is honest to say so — every existing row will read seven whether or
not seven was ever its value, and the model no longer maps the attribute, so
nothing will read it. The point of the downgrade is that an older application
image which still expects the column can start; it is not a way to recover a
retention decision, because the column never held one.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261104_lib_cut1b_drop"
down_revision: Union[str, Sequence[str], None] = "20261103_lib_steward14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

TABLE_NAME: str = "controlled_documents"
COLUMN_NAME: str = "retention_period_years"

#: The value the dropped column's server default wrote. Restored by ``downgrade``
#: for schema compatibility only — see the module docstring.
CITATION_FLAT_YEARS: str = "7"


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in _inspector().get_columns(table_name)}


def _log_what_is_destroyed() -> None:
    """Record what the drop removes, in the deploy log, before it happens.

    Both identifiers are module-level literals, so the interpolation carries no
    external input.
    """
    bind = op.get_bind()
    total = bind.execute(sa.text(f'SELECT COUNT(*) FROM "{TABLE_NAME}"')).scalar()
    # The column has been ``NOT NULL`` since it was created, so a plain
    # inequality is exact here and is ANSI on both PostgreSQL and SQLite.
    non_default = bind.execute(
        sa.text(f'SELECT COUNT(*) FROM "{TABLE_NAME}" WHERE "{COLUMN_NAME}" <> {CITATION_FLAT_YEARS}')
    ).scalar()
    logger.info(
        "%s: dropping %s.%s from %s row(s); %s row(s) held a value other than the default %s",
        revision,
        TABLE_NAME,
        COLUMN_NAME,
        total,
        non_default,
        CITATION_FLAT_YEARS,
    )


def upgrade() -> None:
    if COLUMN_NAME not in _columns(TABLE_NAME):
        logger.info("%s: %s.%s absent, nothing to drop", revision, TABLE_NAME, COLUMN_NAME)
        return
    _log_what_is_destroyed()
    op.drop_column(TABLE_NAME, COLUMN_NAME)


def downgrade() -> None:
    """Restore the column's schema. The values it held do not come back."""
    if not _table_exists(TABLE_NAME):
        return
    if COLUMN_NAME in _columns(TABLE_NAME):
        return
    op.add_column(
        TABLE_NAME,
        sa.Column(COLUMN_NAME, sa.Integer(), nullable=False, server_default=CITATION_FLAT_YEARS),
    )
