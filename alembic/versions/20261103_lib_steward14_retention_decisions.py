"""STEWARD-14: apply the fourteen accepted category retention decisions

Revision ID: 20261103_lib_steward14
Revises: 20261102_lib_cut1_sor
Create Date: 2026-08-10

Why this revision exists (ADR-0023 / F-7 §2 / CUT-1)
----------------------------------------------------
CUT-1 made retention executable *where the prose permitted it* and deliberately
refused fourteen rules rather than guessing which of the two periods they name is
the real one. Those fourteen categories were left with ``retention_years`` and
``retention_anchor`` NULL, which is safe (NULL is never a disposal candidate) but
is not an answer: ADR-0023's amendment says Citation (ATLAS) is not retired for a
category until that category has an executable retention.

A steward accepted all fourteen on 2026-08-10. This revision writes those
decisions onto the existing ``document_categories`` rows so the database matches
the seed, without waiting for a reseed to run.

What it does — and does not do
------------------------------
- Sets ``retention_years`` + ``retention_anchor`` on exactly fourteen rows,
  matched by ``taxonomy_id``.
- Touches no other row, no other column, and no schema. There is no DDL here.
- Does **not** write ``documents.retention_until``. The disposal clock stays a
  file-time decision; re-dating documents already filed would be re-deciding
  retention for records nobody re-reviewed (the same reason CUT-1 refused to
  backfill ``documents.retention_*``).
- Does **not** touch ``specs/governance-library/taxonomy.json``
  ``retention_rule``. The prose is the governance authority and the R19 basis;
  every period it names is honoured or exceeded by the decision, and none was
  shortened to make a decision fit.

Explicitly out of scope (later slices, named so they are not "forgotten")
------------------------------------------------------------------------
- Dropping ``controlled_documents.retention_period_years`` — CUT-1b, once no
  writer remains.
- Backfilling legacy ``documents.retention_until`` / ``documents.retention_*``
  for rows filed before CUT-1 — CUT-1c, deferred.

Why the decision table is a frozen literal
------------------------------------------
It is a snapshot of ``specs/governance-library/steward_retention_decisions.json``
as accepted on 2026-08-10, not an import of it. A migration that reads live
files changes meaning whenever those files change, which is the one thing a
migration must never do.
``tests/unit/test_lib_steward14_retention_decisions.py`` asserts the snapshot
still agrees with the decision file, so drift fails CI instead of silently
producing a database that disagrees with the seed.

Downgrade
---------
Clears both columns back to NULL for exactly these fourteen ``taxonomy_id``
values, which is the state CUT-1 left them in — every one of them was refused by
the prose grammar, so there is no earlier non-NULL value to restore. NULL is also
the fail-safe direction: a category with no executable retention produces no
disposal date, so the effect of a downgrade is that those documents are kept, not
that they are destroyed.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261103_lib_steward14"
down_revision: Union[str, Sequence[str], None] = "20261102_lib_cut1_sor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

#: Frozen snapshot of the accepted decisions: (taxonomy_id, years, anchor).
#: Source: ``specs/governance-library/steward_retention_decisions.json``,
#: accepted by the Governance Library steward on 2026-08-10. Kept in taxonomy_id
#: order so a reviewer can diff it against the decision file by eye.
STEWARD_RETENTION_DECISIONS: tuple[tuple[str, int, str], ...] = (
    ("02.02", 40, "supersede"),
    ("02.04", 6, "supersede"),
    ("02.05", 3, "issue"),
    ("02.06", 3, "issue"),
    ("02.07", 6, "issue"),
    ("02.08", 40, "issue"),
    ("03.04", 3, "supersede"),
    ("04.08", 40, "supersede"),
    ("04.10", 40, "issue"),
    ("06.02", 2, "issue"),
    ("06.04", 2, "issue"),
    ("07.03", 6, "supersede"),
    ("08.03", 3, "issue"),
    ("08.04", 6, "supersede"),
)


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _retention_columns_present() -> bool:
    """CUT-1's columns must exist before a decision can be written to them.

    They are added by ``20261102_lib_cut1_sor``, which this revision revises, so
    in a normal upgrade they are always there. The guard matters for the
    partially-built databases parts of the suite construct, and it matches the
    tolerance the WI-2 / WJ-0 / CUT-1 revisions already use.
    """
    columns = _columns("document_categories")
    return {"retention_years", "retention_anchor"}.issubset(columns)


def upgrade() -> None:
    if not _retention_columns_present():
        logger.info("%s: document_categories retention columns absent, nothing to set", revision)
        return

    bind = op.get_bind()
    statement = sa.text(
        "UPDATE document_categories "
        "SET retention_years = :years, retention_anchor = :anchor "
        "WHERE taxonomy_id = :taxonomy_id"
    )
    applied = 0
    for taxonomy_id, years, anchor in STEWARD_RETENTION_DECISIONS:
        result = bind.execute(statement, {"taxonomy_id": taxonomy_id, "years": years, "anchor": anchor})
        applied += result.rowcount or 0
    logger.info(
        "%s: applied %d of %d steward retention decisions",
        revision,
        applied,
        len(STEWARD_RETENTION_DECISIONS),
    )


def downgrade() -> None:
    """Return the fourteen categories to the NULL that CUT-1 left them at."""
    if not _retention_columns_present():
        return

    bind = op.get_bind()
    statement = sa.text(
        "UPDATE document_categories "
        "SET retention_years = NULL, retention_anchor = NULL "
        "WHERE taxonomy_id = :taxonomy_id"
    )
    for taxonomy_id, _years, _anchor in STEWARD_RETENTION_DECISIONS:
        bind.execute(statement, {"taxonomy_id": taxonomy_id})
