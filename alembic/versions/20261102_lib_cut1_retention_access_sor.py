"""CUT-1: one retention · one Access · QGP as system of record

Revision ID: 20261102_lib_cut1_sor
Revises: 20261101_lib_wj0_drop
Create Date: 2026-08-10

Why this revision exists (ADR-0023 / F-7)
-----------------------------------------
ADR-0023 retires Citation (ATLAS) as the authority for these documents and puts
QGP in its place. Its own risk register makes machine-readable retention
(``retention_years`` + a basis) a **prerequisite of cutover, not a follow-up**,
because a flat "7 Years" is at least computable and free-text prose is not.
F-7 §2/§3 then names the homes this revision creates and folds.

What it does
------------
1. ``document_categories`` gains ``retention_years`` + ``retention_anchor`` —
   the machine-readable projection of ``retention_rule``. The prose column stays
   and remains the governance authority (and the R19 "basis"); it is not copied
   into a second text column, which would be the parallel home F-7 §4 forbids.
2. ``documents`` gains ``retention_years`` + ``retention_anchor`` +
   ``retention_basis``, copied onto the document when it is filed so a disposal
   decision is answerable from the row itself and a later taxonomy edit cannot
   silently re-date documents already filed under the old rule.
   ``documents.retention_until`` is untouched and remains the single clock.
3. Backfills the 30 taxonomy rules the CUT-1 grammar reads unambiguously. The
   other 14 are left NULL on purpose — see below.
4. Folds ``controlled_documents.access_level`` onto the one Library vocabulary:
   anchored control rows take the Register document's level (the Register is
   SoR), and the remaining legacy spellings are normalised.

Why 14 rules are deliberately left NULL
---------------------------------------
Rules such as ``"Tacho data 12 months; working time records 2 years"`` or
``"3 years minimum (to age 21 if a minor); investigations 6 years"`` state two
different periods for two different record types. One category-level integer
cannot represent both. The pre-CUT-1 parser resolved this by taking whichever
number its regex found first, which produced disposal dates years too early on
a queue that hard-deletes rows and blobs. NULL here means "a steward must
decide", and a NULL ``retention_until`` is never a disposal candidate — so the
conservative outcome of an unreadable rule is keep, not destroy.
``scripts/governance/library/citation_cutover_readiness.py`` lists them.

Why the backfill table is a frozen literal
------------------------------------------
It is a snapshot of what ``library_retention_policy.resolve_retention_rule``
returned for the checked-in taxonomy on 2026-08-10, not an import of it. A
migration that calls live application code changes meaning whenever that code
changes, which is the one thing a migration must never do.
``tests/unit/test_lib_cut1_retention_policy.py`` asserts the snapshot still
agrees with the resolver, so drift fails CI instead of failing silently.

Access normalisation is one-way
-------------------------------
Every alias resolves to a level at least as restrictive as the value it
replaces, so this revision cannot widen who may read a document. ``downgrade``
drops the columns but does **not** restore the pre-CUT-1 access spellings: the
parallel vocabulary is what F-7 §3 retires, and re-splitting it would be
re-introducing the defect rather than reversing a mistake.

Out of scope (do not add here)
------------------------------
- Dropping ``controlled_documents.retention_period_years`` — the control layer
  still writes it; CUT-1 stops it being an independent SoR, the column drop
  waits until no writer remains.
- ``documents.sensitivity`` / ``is_public`` / ``restricted_to_*``. F-7 §3 does
  not list them as access homes for library filing and they serve search
  redaction, not the Register ACL.
- Backfilling ``documents.retention_*`` for legacy rows. A filed document's
  retention is a decision that was taken at file time; deriving it now from
  today's category would be inventing an attestation.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261102_lib_cut1_sor"
down_revision: Union[str, Sequence[str], None] = "20261101_lib_wj0_drop"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

#: (table, column, type) added by this revision, dropped in reverse on downgrade.
ADDED_COLUMNS: tuple[tuple[str, str, sa.types.TypeEngine], ...] = (
    ("document_categories", "retention_years", sa.SmallInteger()),
    ("document_categories", "retention_anchor", sa.String(length=20)),
    ("documents", "retention_years", sa.SmallInteger()),
    ("documents", "retention_anchor", sa.String(length=20)),
    ("documents", "retention_basis", sa.Text()),
)

#: Frozen snapshot: taxonomy ``retention_rule`` → (years, anchor). Generated
#: from ``library_retention_policy.resolve_retention_rule`` against
#: ``specs/governance-library/taxonomy.json`` on 2026-08-10. Rules the grammar
#: refuses are absent from this table and stay NULL.
RETENTION_BACKFILL: tuple[tuple[str, Union[int, None], str], ...] = (
    ("3 years", 3, "issue"),
    ("5 years", 5, "issue"),
    ("6 years", 6, "issue"),
    ("6 years (2 certification cycles)", 6, "issue"),
    ("Contract + 6 years", 6, "event"),
    ("Current", None, "indefinite"),
    ("Current + 3 years", 3, "supersede"),
    ("Current + 3 years after superseded", 3, "supersede"),
    ("Current + 6 years", 6, "supersede"),
    ("Current + previous", None, "indefinite"),
    ("Current + previous 2 years", 2, "supersede"),
    ("Current + previous versions", None, "indefinite"),
    ("Current + superseded", None, "indefinite"),
    ("Current + superseded 6 years", 6, "supersede"),
    ("Current cycle + previous", None, "indefinite"),
    ("Current cycle + previous (6 years)", 6, "supersede"),
    ("Current logbook + 6 years", 6, "event"),
    ("Current versions", None, "indefinite"),
    ("Duration of employment", None, "event"),
    ("Duration of use + 3 years", 3, "event"),
    ("Employment + 6 years", 6, "event"),
    ("Life of asset + 6 years", 6, "event"),
    ("Life of occupancy + 6 years", 6, "event"),
    ("Life of vehicle + 6 years", 6, "event"),
    ("Records 6 years", 6, "issue"),
    ("Until next report + 2 years", 2, "event"),
    ("Until superseded", None, "indefinite"),
    ("Until superseded + 6 years", 6, "supersede"),
    ("Until superseded + previous", None, "indefinite"),
    ("While processing + 6 years", 6, "event"),
)

#: Control-layer spelling → the one Library vocabulary (F-7 §3). Mirrors
#: ``library_rules._ACCESS_LEVEL_ALIASES``; frozen here for the same reason the
#: retention table is.
ACCESS_LEVEL_NORMALISATION: tuple[tuple[str, str], ...] = (
    ("internal", "all_staff"),
    ("public", "all_staff"),
    ("staff", "all_staff"),
    ("all staff", "all_staff"),
    ("all employees", "all_staff"),
    ("all_employees", "all_staff"),
    ("manager", "managers"),
    ("management", "managers"),
    ("managers only", "managers"),
    ("confidential", "restricted"),
    ("restricted_access", "restricted"),
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {c["name"] for c in _inspector().get_columns(table_name)}


def _backfill_category_retention() -> None:
    """Project the readable taxonomy rules onto the new machine-readable columns."""
    if "retention_rule" not in _columns("document_categories"):
        logger.info("%s: document_categories.retention_rule absent, nothing to project", revision)
        return
    bind = op.get_bind()
    statement = sa.text(
        "UPDATE document_categories "
        "SET retention_years = :years, retention_anchor = :anchor "
        "WHERE retention_rule = :rule"
    )
    for rule, years, anchor in RETENTION_BACKFILL:
        bind.execute(statement, {"rule": rule, "years": years, "anchor": anchor})


def _converge_control_access() -> None:
    """F-7 §3 — one access vocabulary; the Register wins where it is anchored."""
    columns = _columns("controlled_documents")
    if "access_level" not in columns:
        logger.info("%s: controlled_documents.access_level absent, nothing to converge", revision)
        return
    bind = op.get_bind()

    if "library_document_id" in columns:
        # Correlated subquery rather than UPDATE ... FROM so the same statement
        # runs on PostgreSQL and on the SQLite used by parts of the test suite.
        bind.execute(
            sa.text(
                "UPDATE controlled_documents SET access_level = ("
                "  SELECT d.access_level FROM documents d"
                "  WHERE d.id = controlled_documents.library_document_id"
                ") "
                "WHERE library_document_id IS NOT NULL AND ("
                "  SELECT d.access_level FROM documents d"
                "  WHERE d.id = controlled_documents.library_document_id"
                ") IS NOT NULL"
            )
        )

    statement = sa.text("UPDATE controlled_documents SET access_level = :canonical WHERE LOWER(access_level) = :legacy")
    for legacy, canonical in ACCESS_LEVEL_NORMALISATION:
        bind.execute(statement, {"legacy": legacy, "canonical": canonical})


def upgrade() -> None:
    for table_name, column_name, column_type in ADDED_COLUMNS:
        if not _table_exists(table_name):
            logger.info("%s: %s absent, skipping %s", revision, table_name, column_name)
            continue
        if column_name in _columns(table_name):
            continue
        op.add_column(table_name, sa.Column(column_name, column_type, nullable=True))

    _backfill_category_retention()
    _converge_control_access()


def downgrade() -> None:
    """Drop the machine-readable retention columns.

    The access vocabulary fold is not reversed — see the module docstring. No
    document loses a retention date: ``documents.retention_until`` is not
    touched by this revision in either direction.
    """
    for table_name, column_name, _column_type in reversed(ADDED_COLUMNS):
        if not _table_exists(table_name):
            continue
        if column_name in _columns(table_name):
            op.drop_column(table_name, column_name)
