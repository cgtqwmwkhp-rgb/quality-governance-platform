"""Align the near-miss lifecycle with the incident lifecycle (N-2).

Revision ID: 20260910_nm_status_align
Revises: 20260909_iso_absorb
Create Date: 2026-09-09

What was wrong
--------------
``near_misses.status`` was the only case register storing an uppercase plain
string. The other three -- incidents, complaints, road traffic collisions --
persist lowercase enum values. The near-miss labels were not merely a different
casing of the same lifecycle either; they were a different lifecycle:

    REPORTED         -> reported
    UNDER_REVIEW     -> under_investigation
    ACTION_REQUIRED  -> pending_actions
    IN_PROGRESS      -> actions_in_progress
    (absent)         -> pending_review
    CLOSED           -> closed

The consequences were spread thinly across the stack rather than concentrated
anywhere obvious: ``case_closure.CASE_CONFIGS`` carried a near-miss-only
uppercase ``closed_status``/``reopen_status`` pair, ``is_closed_status`` had to
compare case-insensitively for every register to keep near misses working,
``normalize_portal_status`` existed to give the portal one casing across four
tables, and the near-miss register had no equivalent of ``pending_review`` --
so a near miss whose actions were finished had nowhere to sit while somebody
checked them, and reopening a closed one landed straight back in review rather
than at the incident register's controlled ``pending_review`` staging point.

What this migration does
------------------------
Rewrites the five legacy labels to their incident counterparts and installs
``ck_near_misses_status`` over the six aligned values.

The rewrite matches on ``upper(status)``, which makes it idempotent: a database
that has already been through it holds ``reported``/``closed``, whose
``upper()`` maps back to themselves, and the four labels that are new to this
register (``under_investigation``, ``pending_actions``, ``actions_in_progress``,
``pending_review``) do not appear on the left-hand side at all, so a re-run
cannot walk a record backwards through the lifecycle.

``pending_review`` is added to the allowed set but no row is moved into it. It
is a state operators reach by working a case, not one that can be inferred from
a record that never had it.

Why the constraint is created rather than altered
-------------------------------------------------
``ck_near_misses_status`` has been declared on the ``NearMiss`` model since the
table was added, but no migration ever created it --
``20260121_add_near_miss_and_rta_enhancements`` built ``near_misses`` without
one, and autogenerate does not compare CHECK
constraints, so no gate reported the gap. A database built by
``alembic upgrade head`` therefore does not have it; one built by
``Base.metadata.create_all`` (the test harnesses) does. ``DROP CONSTRAINT IF
EXISTS`` covers both, and this is the point at which the declared constraint
starts actually being enforced on a deployed database.

Refusing rather than guessing
-----------------------------
If a row holds a status outside both the legacy set and the aligned set, this
migration raises instead of continuing. The alternatives are worse: adding the
constraint over it fails anyway, with an opaque PostgreSQL error naming neither
the value nor the row count; skipping the constraint leaves the model and the
database disagreeing again, silently, which is the exact failure this migration
exists to close. Nothing is deleted and nothing is coerced -- an unrecognised
governance state is a data question for its owner, not a value a migration may
invent (#1398).

Reversibility
-------------
``downgrade`` restores the uppercase labels and the uppercase constraint. The
one thing it cannot restore is the distinction ``pending_review`` carries: the
old register had no such state, so those rows collapse into ``IN_PROGRESS``,
which is where the same case would have sat before the alignment. That is
logged with a count, and the individual moves remain recoverable from the
``near_miss.updated`` audit events that recorded them.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260910_nm_status_align"
down_revision: Union[str, Sequence[str], None] = "20260909_iso_absorb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

TABLE = "near_misses"
CONSTRAINT = "ck_near_misses_status"

#: The aligned set, identical to ``IncidentStatus``. ``pending_review`` is new to
#: this register and is reachable only by working a case forward.
ALIGNED_STATUSES: tuple[str, ...] = (
    "reported",
    "under_investigation",
    "pending_actions",
    "actions_in_progress",
    "pending_review",
    "closed",
)

#: What the register held before this revision.
LEGACY_STATUSES: tuple[str, ...] = (
    "REPORTED",
    "UNDER_REVIEW",
    "ACTION_REQUIRED",
    "IN_PROGRESS",
    "CLOSED",
)

# Both rewrites are written out rather than generated so the statement that runs
# against real governance records is the statement in the file, and so the unit
# tests can execute the shipped string (the idiom 20260816/20260826 established;
# the repository's own ``alembic`` package directory makes importing a migration
# module in a test impossible).
#
# Matching on ``upper(status)`` is what makes this safe to re-run: the four labels
# that are new to this register do not appear in the WHERE list, so a second pass
# cannot walk an aligned record backwards.
UPGRADE_REWRITE_SQL = """
UPDATE near_misses
SET status = CASE upper(status)
    WHEN 'REPORTED' THEN 'reported'
    WHEN 'UNDER_REVIEW' THEN 'under_investigation'
    WHEN 'ACTION_REQUIRED' THEN 'pending_actions'
    WHEN 'IN_PROGRESS' THEN 'actions_in_progress'
    WHEN 'CLOSED' THEN 'closed'
    ELSE status
END
WHERE upper(status) IN ('REPORTED', 'UNDER_REVIEW', 'ACTION_REQUIRED', 'IN_PROGRESS', 'CLOSED')
"""

# ``pending_review`` collapses into ``IN_PROGRESS``: the old register had no state
# for "actions done, awaiting a check", so there is no label that preserves it.
DOWNGRADE_REWRITE_SQL = """
UPDATE near_misses
SET status = CASE lower(status)
    WHEN 'reported' THEN 'REPORTED'
    WHEN 'under_investigation' THEN 'UNDER_REVIEW'
    WHEN 'pending_actions' THEN 'ACTION_REQUIRED'
    WHEN 'actions_in_progress' THEN 'IN_PROGRESS'
    WHEN 'pending_review' THEN 'IN_PROGRESS'
    WHEN 'closed' THEN 'CLOSED'
    ELSE status
END
WHERE lower(status) IN ('reported', 'under_investigation', 'pending_actions',
                        'actions_in_progress', 'pending_review', 'closed')
"""


class UnmappedNearMissStatusError(RuntimeError):
    """A near miss holds a status this migration has no aligned label for."""


def _in_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _statuses_the_constraint_would_reject(allowed: Sequence[str]) -> list[tuple[str, int]]:
    rows = op.get_bind().execute(
        sa.text(
            f"SELECT status, count(*) AS n FROM {TABLE} "  # noqa: S608 - identifiers are module constants
            "WHERE status NOT IN :allowed GROUP BY status ORDER BY status"
        ).bindparams(sa.bindparam("allowed", expanding=True)),
        {"allowed": list(allowed)},
    )
    return [(row[0], int(row[1])) for row in rows]


def _assert_every_status_is_known(allowed: Sequence[str]) -> None:
    leftovers = _statuses_the_constraint_would_reject(allowed)
    if not leftovers:
        return
    detail = ", ".join(f"{status!r} x{count}" for status, count in leftovers)
    raise UnmappedNearMissStatusError(
        f"{TABLE} holds status values outside the aligned lifecycle: {detail}. "
        f"This migration will not guess which of {_in_list(allowed)} they meant, and "
        f"{CONSTRAINT} would refuse them. Resolve those rows, then re-run -- the "
        "rewrite is idempotent."
    )


def _replace_constraint(allowed: Sequence[str]) -> None:
    """Install ``CONSTRAINT`` over ``allowed``, whether or not it exists today."""
    if op.get_bind().dialect.name != "postgresql":
        # The migration chain is PostgreSQL-only (see tests/integration/
        # _alembic_only_schema.py); SQLite cannot drop or add a table constraint
        # in place, and the data rewrite above is the part that has to be portable.
        return
    op.execute(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
    op.execute(f"ALTER TABLE {TABLE} ADD CONSTRAINT {CONSTRAINT} CHECK (status IN ({_in_list(allowed)}))")


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table(TABLE):
        logger.info("%s: no %r table, nothing to align.", revision, TABLE)
        return

    op.execute(UPGRADE_REWRITE_SQL)
    _assert_every_status_is_known(ALIGNED_STATUSES)
    _replace_constraint(ALIGNED_STATUSES)

    logger.info(
        "%s: %s.status aligned to the incident lifecycle; %s now enforces %s.",
        revision,
        TABLE,
        CONSTRAINT,
        _in_list(ALIGNED_STATUSES),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(TABLE):
        return

    collapsed = bind.execute(
        sa.text(f"SELECT count(*) FROM {TABLE} WHERE lower(status) = 'pending_review'")  # noqa: S608
    ).scalar()
    if collapsed:
        logger.warning(
            "%s: %d near miss/misses in 'pending_review' collapse to 'IN_PROGRESS' -- the state "
            "did not exist before this revision. The individual moves remain in the "
            "near_miss.updated audit events.",
            revision,
            collapsed,
        )

    op.execute(DOWNGRADE_REWRITE_SQL)
    _assert_every_status_is_known(LEGACY_STATUSES)
    _replace_constraint(LEGACY_STATUSES)
