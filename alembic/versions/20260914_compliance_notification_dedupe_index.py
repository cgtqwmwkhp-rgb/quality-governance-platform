"""Unique index enforcing one compliance-schedule notification per occurrence+band.

Revision ID: 20260914_cs_notif_dedupe
Revises: 20260913_cs_wave0
Create Date: 2026-09-14

The Wave 2 sweep decides whether to notify by looking for an existing row and
inserting when it finds none. That is a read followed by a write with no lock
between them, so two workers -- a retry overlapping its original, two beat ticks,
or one sweep racing a manual trigger -- both read "absent" and both insert. The
duplicate is what the user sees, and nothing in application code can prevent it.

This index is the constraint that can. It carries the same shape the sweep's
``ON CONFLICT`` clause infers, so the second writer is refused by PostgreSQL
rather than trusted to have checked first.

Why the predicate and the COALESCE
----------------------------------
``notifications`` is shared by every feature in the platform and the overwhelming
majority of its rows have no ``dedupe_key`` in ``extra_data``. Without the
``entity_type`` predicate every one of those rows would coalesce to the empty
string and the index would permit a user exactly one notification. The predicate
confines the constraint to rows this module writes.

``COALESCE(extra_data ->> 'dedupe_key', '')`` rather than the bare ``->>``:
PostgreSQL treats NULLs in a unique index as distinct, so a compliance row that
somehow carried no dedupe_key would be insertable without limit. Folding NULL to
the empty string makes that case collide with itself, which is the safer
direction to fail.
``NULLS NOT DISTINCT`` would express the same thing but needs PostgreSQL 15+, and
this migration has to be applicable to whatever version each environment is on.

Why this is not CONCURRENTLY
----------------------------
Every other index in this repository is built inside its migration's transaction,
and no migration here has ever used ``autocommit_block``. CONCURRENTLY would buy
the avoidance of an ACCESS EXCLUSIVE lock, and cost the atomicity all the others
have: a failed concurrent build leaves an INVALID index behind that the next
attempt has to detect and drop, and the reversibility check in CI would be
exercising a code path no other revision has. Staging measures 9 rows and 112 kB
on this table, the lock is held for one scan of it, and migrations run inside a
deploy window that already drops requests for a minute or two while containers
restart. Introducing the repository's first non-atomic migration to shorten a lock
that cannot be observed is the worse trade.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260914_cs_notif_dedupe"
down_revision: Union[str, Sequence[str], None] = "20260913_cs_wave0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

INDEX_NAME = "uq_notifications_compliance_dedupe"
TABLE_NAME = "notifications"
ENTITY_TYPE = "compliance_requirement"

# Held as a literal, and asserted against pg_index after the fact, for the reason
# 20260913_cs_wave0 keeps its own copy of the RLS predicate: a migration describes
# the database at this revision and must not change meaning when the model file is
# edited later. A unit test asserts this and the ORM declaration stay identical.
INDEX_DDL = (
    f"CREATE UNIQUE INDEX {INDEX_NAME} ON {TABLE_NAME} "
    "(user_id, COALESCE(extra_data ->> 'dedupe_key', '')) "
    f"WHERE entity_type = '{ENTITY_TYPE}'"
)


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _index_exists() -> bool:
    return bool(
        op.get_bind()
        .execute(
            sa.text("SELECT 1 FROM pg_class WHERE relkind = 'i' AND relname = :name"),
            {"name": INDEX_NAME},
        )
        .fetchone()
    )


def _assert_no_existing_duplicates() -> None:
    """Refuse with an actionable message rather than a cryptic build failure.

    ``CREATE UNIQUE INDEX`` on data that already violates it fails with the
    offending key and nothing else, mid-deploy. Counting first turns that into a
    message naming how many groups collide, so whoever is holding the pager knows
    whether they are looking at two rows or two thousand before deciding.
    """
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(f"""
            SELECT count(*) FROM (
                SELECT user_id, COALESCE(extra_data ->> 'dedupe_key', '') AS key
                FROM {TABLE_NAME}
                WHERE entity_type = :entity_type
                GROUP BY 1, 2
                HAVING count(*) > 1
            ) AS collisions
            """),
            {"entity_type": ENTITY_TYPE},
        )
        .scalar_one()
    )

    if duplicates:
        raise RuntimeError(
            f"{revision}: cannot create {INDEX_NAME}: {duplicates} "
            f"(user_id, dedupe_key) group(s) in {TABLE_NAME} already hold more than "
            f"one row with entity_type = '{ENTITY_TYPE}'. These are duplicate "
            "notifications already delivered to users. Decide which row of each "
            "group to keep before re-running; this migration will not choose for you."
        )


def _assert_index_matches() -> None:
    """Re-read pg_index and raise unless the index really has both parts.

    Same shape as the policy assertion in 20260913_cs_wave0 and for the same
    reason: an index that exists under the right name but without the partial
    predicate would silently constrain every notification in the table, and a
    migration that reports a state it did not reach is how that ships unnoticed.
    """
    row = (
        op.get_bind()
        .execute(
            sa.text("""
            SELECT i.indisunique AS is_unique,
                   i.indisvalid  AS is_valid,
                   pg_get_expr(i.indpred, i.indrelid) AS predicate,
                   pg_get_indexdef(i.indexrelid)      AS definition
            FROM pg_index AS i
            JOIN pg_class AS c ON c.oid = i.indexrelid
            WHERE c.relname = :name
            """),
            {"name": INDEX_NAME},
        )
        .mappings()
        .fetchone()
    )

    problems: list[str] = []
    if row is None:
        problems.append("index is absent from pg_index")
    else:
        if not row["is_unique"]:
            problems.append("index is not UNIQUE, so it constrains nothing")
        if not row["is_valid"]:
            problems.append("index is INVALID and will not be used or enforced")
        predicate = row["predicate"]
        if predicate is None:
            problems.append(
                "index has no partial predicate: it would apply to every row in "
                "the table, limiting each user to one notification overall"
            )
        elif ENTITY_TYPE not in predicate:
            problems.append(f"predicate is {predicate!r}, expected it to reference {ENTITY_TYPE!r}")
        definition = row["definition"] or ""
        if "COALESCE" not in definition.upper():
            problems.append(
                f"definition is {definition!r}, expected the COALESCE expression; "
                "without it a NULL dedupe_key is unconstrained"
            )

    if problems:
        raise RuntimeError(
            f"{revision} did not achieve the index state it reported. "
            "Refusing to record this revision as applied.\n  " + "\n  ".join(problems)
        )


def upgrade() -> None:
    # SQLite gets this index from the ORM declaration via create_all, which
    # carries sqlite_where. Emitting the PostgreSQL DDL here would fail on it.
    if not _is_postgres():
        logger.info("%s: not PostgreSQL — index comes from the model metadata", revision)
        return

    if _index_exists():
        logger.info("%s: %s already present — verifying rather than recreating", revision, INDEX_NAME)
        _assert_index_matches()
        return

    _assert_no_existing_duplicates()
    op.execute(sa.text(INDEX_DDL))
    _assert_index_matches()
    logger.info("%s: created %s", revision, INDEX_NAME)


def downgrade() -> None:
    if not _is_postgres():
        return
    op.execute(sa.text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))
