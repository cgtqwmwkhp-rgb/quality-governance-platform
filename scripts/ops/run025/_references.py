"""What deleting a row does to the next reference number the application will mint.

``ReferenceNumberService._next_sequence`` is the only thing that decides the next
reference, and it decides it like this::

    max_ref  = MAX(ref_col) WHERE ref_col LIKE 'PREFIX-YYYY-%'   -- a *string* MAX
    max_seq  = int(max_ref.split("-")[-1])                       -- failure swallowed
    count    = COUNT(*)   WHERE ref_col LIKE 'PREFIX-YYYY-%'
    next     = max(max_seq, count) + 1

Three properties of that make deletion dangerous, and none of them are obvious:

* **The string MAX.** Ordering is whatever the column's collation says, not numeric
  order. So the arithmetic here reads ``MAX`` back out of the database rather than
  recomputing it in Python — a Python ``max()`` over the same strings can disagree
  with PostgreSQL under a non-C collation, and the number that matters is the one
  the *application* will see.
* **The swallowed ``int()``.** A portal-style eight-hex-digit suffix raises
  ``ValueError``, which is caught and ignored, leaving ``max_seq`` at 0. In a table
  that mixes reference schemes the next value is therefore governed by ``COUNT(*)``
  alone — and then deleting *any* row lowers it, whether or not that row held the
  highest reference.
* **``COUNT(*)`` is part of the maximum.** Because ``next`` is
  ``max(max_seq, count) + 1``, removing rows can only ever move ``next`` down. It
  never moves up. So a delete can hand a previously-issued number back out.

There are two distinct bad outcomes and they need separating, because one is a
silent record-keeping failure and the other is an outage:

``reissue``
    ``next`` drops to at or below a suffix that one of the *deleted* rows held. A
    future genuine record is minted with a reference that has already appeared in
    an export, an email or an external auditor's notes, pointing at a record that
    no longer exists. Nothing fails; the register is just quietly wrong.

``collision``
    ``next`` drops to at or below a suffix that a *surviving* row still holds. The
    reference columns are backed by UNIQUE indexes, so the next attempt to create
    that record type fails outright. Whoever is trying to raise an audit finding
    simply cannot.

Both are reported. Neither is inferred from a rule of thumb; both are computed
from the rows actually in the database, before and after the proposed delete.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Sequence

import sqlalchemy as sa

#: ``PREFIX-YYYY-NNNN``, the sequential form ``ReferenceNumberService`` mints.
SEQUENTIAL_REFERENCE = re.compile(r"^([A-Z]+)-(\d{4})-(\d+)$")

#: Candidate reference columns, in the order ``ReferenceNumberService._ref_column``
#: tries them. ``risks_v2`` uses ``reference``; everything else in the audit family
#: uses ``reference_number``. A helper that assumed either one alone would crash on
#: the other, which is how a purge discovers a table it cannot handle at the worst
#: possible moment.
REFERENCE_COLUMNS: tuple[str, ...] = ("reference_number", "reference")


def reference_column(columns: Any) -> Optional[str]:
    """The reference column this table actually has, or ``None`` if it has none.

    ``compliance_evidence_links`` has neither, so "none" is a normal answer and
    must not be an error: a table with no reference column cannot have a reference
    reuse problem.
    """
    for candidate in REFERENCE_COLUMNS:
        if candidate in columns:
            return candidate
    return None


def reference_parts(reference: Optional[str]) -> Optional[tuple[str, str, int]]:
    """``(prefix, year, suffix)`` for a sequential reference, else ``None``.

    A portal hex reference such as ``INC-2026-FFFFFFFF`` deliberately returns
    ``None``. It is not a sequential reference with a large number in it; its
    suffix has no ordinal meaning at all, and treating it as one would produce a
    confident, wrong answer about the sequence.
    """
    if not reference:
        return None
    match = SEQUENTIAL_REFERENCE.match(reference.strip())
    if not match:
        return None
    return match.group(1), match.group(2), int(match.group(3))


def next_sequence(max_ref: Optional[str], count: int) -> int:
    """Reproduce ``ReferenceNumberService._next_sequence`` exactly.

    Including the parts that look like bugs: the ``int()`` failure is swallowed to
    zero rather than raised, because that is what the application does, and a
    safety check that models the *intended* behaviour instead of the real one is
    worse than no check.
    """
    max_seq = 0
    if max_ref:
        try:
            max_seq = int(str(max_ref).split("-")[-1])
        except (ValueError, IndexError):
            max_seq = 0
    return max(max_seq, count) + 1


@dataclass(frozen=True)
class ReferenceArithmetic:
    """The next-value sum for one ``PREFIX-YYYY`` pattern, before and after a delete."""

    table: str
    column: str
    pattern: str
    doomed_references: tuple[str, ...]
    max_ref_before: Optional[str]
    count_before: int
    max_ref_after: Optional[str]
    count_after: int
    surviving_suffixes: tuple[int, ...]
    doomed_suffixes: tuple[int, ...]
    pattern_year_is_current: bool

    @property
    def next_before(self) -> int:
        return next_sequence(self.max_ref_before, self.count_before)

    @property
    def next_after(self) -> int:
        return next_sequence(self.max_ref_after, self.count_after)

    @property
    def would_reissue(self) -> tuple[int, ...]:
        """Suffixes of deleted rows that the next mints would hand out again."""
        return tuple(s for s in self.doomed_suffixes if s >= self.next_after)

    @property
    def would_collide(self) -> tuple[int, ...]:
        """Suffixes still in the table that the next mints would try to reuse.

        The reference columns are UNIQUE, so this is not a record-keeping nuance —
        it is the next insert failing.
        """
        return tuple(s for s in self.surviving_suffixes if s >= self.next_after)

    @property
    def is_hazardous(self) -> bool:
        return bool(self.would_reissue or self.would_collide)

    def explain(self) -> str:
        """The sum in full, so an operator can check it rather than trust it."""
        return (
            f"before: max({_seq_of(self.max_ref_before)}, count={self.count_before}) + 1 = {self.next_before}; "
            f"after: max({_seq_of(self.max_ref_after)}, count={self.count_after}) + 1 = {self.next_after}"
        )

    def as_report(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "reference_column": self.column,
            "pattern": self.pattern,
            "deleted_references": list(self.doomed_references),
            "max_reference_before": self.max_ref_before,
            "count_before": self.count_before,
            "next_value_before": self.next_before,
            "max_reference_after": self.max_ref_after,
            "count_after": self.count_after,
            "next_value_after": self.next_after,
            "arithmetic": self.explain(),
            "would_reissue_deleted_suffixes": list(self.would_reissue),
            "would_collide_with_surviving_suffixes": list(self.would_collide),
            "pattern_year_is_current": self.pattern_year_is_current,
            "verdict": _verdict(self),
        }


def _seq_of(max_ref: Optional[str]) -> str:
    """How ``_next_sequence`` reads a MAX, shown as it computes it."""
    if not max_ref:
        return "max_seq=0 (no reference matched)"
    try:
        return f"max_seq={int(str(max_ref).split('-')[-1])} (from {max_ref!r})"
    except (ValueError, IndexError):
        return f"max_seq=0 ({max_ref!r} did not parse; the int() failure is swallowed)"


def _verdict(arithmetic: ReferenceArithmetic) -> str:
    if arithmetic.would_collide:
        return (
            "COLLISION: the next reference this pattern mints is already held by a surviving row, "
            "and the column is UNIQUE, so the next record of this type cannot be created at all"
        )
    if arithmetic.would_reissue:
        return (
            "REISSUE: the next reference this pattern mints was already issued to a row this purge "
            "deletes, so a future genuine record would carry a reference that has already been used"
        )
    if not arithmetic.pattern_year_is_current:
        return (
            "safe: the sequence moves down, but this pattern's year is not the current year, so "
            "nothing will be minted against it unless a record is backdated"
        )
    return "safe: the next value does not fall to or below any reference that has been issued"


async def _max_and_count(
    db: Any,
    *,
    table: str,
    column: str,
    pattern: str,
    key_column: str,
    excluded_keys: Sequence[Any],
) -> tuple[Optional[str], int]:
    """``MAX`` and ``COUNT`` for a pattern, optionally ignoring some rows.

    ``MAX`` is evaluated by the database so it uses the column's collation, which
    is what the application will see. Table, column and key names come from the
    inspector and from module-level literals, never from argv.
    """
    where = f"{column} LIKE :pattern"
    params: dict[str, Any] = {"pattern": pattern}
    if excluded_keys:
        placeholders = ", ".join(f":excluded_{index}" for index in range(len(excluded_keys)))
        where += f" AND {key_column} NOT IN ({placeholders})"
        params.update({f"excluded_{index}": key for index, key in enumerate(excluded_keys)})
    row = (
        await db.execute(
            sa.text(f"SELECT MAX({column}) AS max_ref, COUNT(*) AS row_count FROM {table} WHERE {where}"),  # noqa: S608
            params,
        )
    ).one()
    return row[0], int(row[1] or 0)


async def _suffixes(
    db: Any,
    *,
    table: str,
    column: str,
    pattern: str,
    key_column: str,
    excluded_keys: Sequence[Any],
) -> tuple[int, ...]:
    """Parseable suffixes for a pattern, optionally ignoring some rows.

    Filtered in Python rather than with a SQL substring cast: only references
    matching the sequential form have a meaningful numeric suffix, and expressing
    that filter in SQL differs between PostgreSQL and the SQLite these scripts are
    also exercised against.
    """
    where = f"{column} LIKE :pattern"
    params: dict[str, Any] = {"pattern": pattern}
    if excluded_keys:
        placeholders = ", ".join(f":excluded_{index}" for index in range(len(excluded_keys)))
        where += f" AND {key_column} NOT IN ({placeholders})"
        params.update({f"excluded_{index}": key for index, key in enumerate(excluded_keys)})
    rows = (
        (await db.execute(sa.text(f"SELECT {column} FROM {table} WHERE {where}"), params)).scalars().all()  # noqa: S608
    )
    parsed = [reference_parts(row) for row in rows]
    return tuple(sorted(part[2] for part in parsed if part is not None))


async def reference_arithmetic(
    db: Any,
    *,
    table: str,
    column: str,
    key_column: str,
    doomed: dict[Any, Optional[str]],
    now: Optional[datetime] = None,
) -> list[ReferenceArithmetic]:
    """Next-value arithmetic for every pattern the doomed rows touch.

    ``doomed`` maps primary key to that row's reference. Rows whose reference is
    not sequential contribute no pattern of their own, but they are still excluded
    from the "after" counts, because deleting them still lowers ``COUNT(*)`` for
    whatever pattern they matched — which is precisely how a mixed-scheme table
    loses numbers it never appeared to own.
    """
    current_year = (now or datetime.now()).year
    doomed_keys = list(doomed)

    patterns: dict[str, list[str]] = {}
    for reference in doomed.values():
        parts = reference_parts(reference)
        if parts is None:
            continue
        prefix, year, _suffix = parts
        patterns.setdefault(f"{prefix}-{year}-%", []).append(str(reference))

    out: list[ReferenceArithmetic] = []
    for pattern, references in sorted(patterns.items()):
        max_before, count_before = await _max_and_count(
            db, table=table, column=column, pattern=pattern, key_column=key_column, excluded_keys=()
        )
        max_after, count_after = await _max_and_count(
            db, table=table, column=column, pattern=pattern, key_column=key_column, excluded_keys=doomed_keys
        )
        surviving = await _suffixes(
            db, table=table, column=column, pattern=pattern, key_column=key_column, excluded_keys=doomed_keys
        )
        doomed_suffixes = tuple(
            sorted(part[2] for reference in references if (part := reference_parts(reference)) is not None)
        )
        year = pattern.split("-")[1]
        out.append(
            ReferenceArithmetic(
                table=table,
                column=column,
                pattern=pattern,
                doomed_references=tuple(sorted(references)),
                max_ref_before=max_before,
                count_before=count_before,
                max_ref_after=max_after,
                count_after=count_after,
                surviving_suffixes=surviving,
                doomed_suffixes=doomed_suffixes,
                pattern_year_is_current=year == str(current_year),
            )
        )
    return out


async def mixed_reference_schemes(db: Any, table: str, column: str) -> Optional[dict[str, Any]]:
    """Report a table whose references the sequential generator cannot all parse.

    Where both a sequential and a hex scheme coexist, ``max_seq`` collapses to 0
    and the next value is driven entirely by ``COUNT(*)``. That is a property of
    the existing generator rather than of any delete, so it is reported rather
    than blocking — but an operator reading the arithmetic above needs to know the
    row count is doing the work.
    """
    rows = (await db.execute(sa.text(f"SELECT {column} FROM {table}"))).scalars().all()  # noqa: S608
    unparsable = [row for row in rows if row and reference_parts(row) is None]
    if not unparsable or len(unparsable) == len(rows):
        return None
    return {
        "table": table,
        "reference_column": column,
        "non_sequential_references": len(unparsable),
        "example": unparsable[0],
        "reason": (
            "this table mixes sequential and non-sequential references, so MAX(...) fails to parse, "
            "max_seq falls back to 0, and the next value is governed by COUNT(*) alone"
        ),
    }
