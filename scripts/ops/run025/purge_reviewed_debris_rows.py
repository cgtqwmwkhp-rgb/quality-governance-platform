#!/usr/bin/env python3
"""Delete the six reviewed CI-debris rows, and nothing else, ever.

Scope
-----
Of the tenant-less rows outside the ``20260901_case_tenant_nn`` scope that
``backfill_tenant_orphan_rows`` can see, 816 inherit a real tenant from an active
user who already holds one. Four do not: they were created by
``smoke-runner@plantexpand.com`` (user id 4), a deactivated account whose own
``tenant_id`` is NULL, so there is no evidence to inherit and the only remaining
attribution would be the invented single-tenant default.

Two more rows joined the set on 2026-07-28. ``audit_responses#1`` and ``#2`` are
the single answer each smoke run recorded, seconds after its parent run; they were
found because ``audit_responses.run_id`` is ``ON DELETE CASCADE``, so the first
production dry run refused rather than let them be destroyed unreviewed. They were
then inspected and approved on the same evidence. That is the only way this set
grows: another reviewed row, not a flag that widens the delete.

``audit_responses`` records no creator at all, so those two are held by their
parent run plus the ``notes = 'E2E response'`` marker the smoke test wrote. See
:class:`ReviewedRow` for why that is treated as borrowing the parent's evidence
rather than as a weaker standard of proof.

Deleting these *first* is what lets the backfill then run on inheritance alone.
That is not a workaround for ``backfill_tenant_orphan_rows``'s single-tenant
precondition — it removes the need for it, so the migration family's "do not invent
``tenant_id = 1``" fail-safe is satisfied on its own terms rather than overridden.

Why this is a separate script from ``purge_tenant_orphan_rows``
--------------------------------------------------------------
``purge_tenant_orphan_rows`` selects rows by *predicate*: every NULL-tenant row in
the ten tables the migration names, parsed out of the migration itself. Its safety
story is "exactly the rows that make revision 20260901 refuse", and it is correct
for that job — which is why it reports nothing to do today.

This script selects rows by *identity*: six primary keys, in four tables the
migration does not touch, each carrying its own recorded expectation about where it
came from. Three things follow, and each of them argues against widening the
predicate script instead:

1. **The reviewed set is a literal, so it can be re-verified.** A predicate cannot
   notice that the database stopped matching the evidence a human approved; a
   literal list plus per-row expectations can, and does — see
   :func:`verify_reviewed_row`.
2. **Table disjointness is load-bearing.** ``assign_tenant_orphan_rows`` refuses
   production outright because attributing a *case* to a tenant is a
   confidentiality claim, and ``backfill_tenant_orphan_rows`` rests on the
   guarantee — asserted by ``_assert_disjoint`` and by a test — that the
   case/action tables and everything else are handled by scripts that cannot reach
   each other's tables. Teaching the case/action purge to delete from
   ``audit_runs`` and ``risks_v2`` would put one script astride both sets and
   silently retire that guarantee.
3. **The two want opposite defaults.** Widening would mean a flag that switches a
   ``DELETE`` between "every NULL-tenant row in these tables" and "only these six
   ids". A flag that changes which rows a delete targets is the one flag most
   worth not having.

Refusals
--------
Every one of these stops the run rather than warning:

* **A precondition that has moved since the review.** The row must still exist and
  still be NULL-tenant. A row with a creator must still name the expected account,
  and that account must still be deactivated and still hold no tenant of its own —
  if it were reactivated, or had gained a tenant, the row would no longer be
  unattributable debris but inheritable history, and it belongs in the backfill
  instead of here. A row held by a parent must still hang off that same reviewed
  parent and still carry its marker.
* **A reviewed table with no ``tenant_id`` column.** Checked rather than assumed,
  because ``AuditResponse`` does not declare the column its production table has.
  See :data:`TENANT_COLUMN`.
* **A dependent row outside the reviewed set.** ``audit_responses.run_id``,
  ``audit_findings.run_id`` and ``audit_finding_risks`` are all ``ON DELETE
  CASCADE``, and the drafts and jobs tables cascade off ``audit_runs`` too — so a
  careless delete of one audit run can reach the 754 import drafts that are real
  user work. This is the guard that stopped the first production run: it named the
  two ``audit_responses`` rows, which is how they came to be reviewed at all.
  Anything referencing a doomed row and not itself doomed is a refusal, reported by
  constraint, child table and child key.
* **Row-level security that could hide the rows.** ``audit_runs``,
  ``audit_findings``, ``risks_v2`` and ``users`` are all under FORCE RLS with a
  ``tenant_isolation`` policy comparing ``tenant_id`` against
  ``current_setting('app.current_tenant_id')``. That is never true for NULL, so an
  RLS-subject role sees *none* of these rows — and a ``DELETE`` it issues removes
  nothing while reporting no error. Absence is therefore only ever treated as
  absence when the role is provably not subject to that table's policies;
  otherwise it is a refusal.
* **A reference number that would become mintable again.** Computed as real
  before/after arithmetic against the live rows, not asserted as a general risk.
  See ``_references``. Override deliberately with
  ``--accept-reference-reuse-risk``.
* **``--apply`` without ``--manifest``.** These rows belong to no tenant, and
  ``audit_log_entries.tenant_id`` is NOT NULL with a foreign key to ``tenants``, so
  the deletion cannot be recorded in the per-tenant hash-chained trail without
  first inventing the very attribution under review. The manifest is the change
  record instead, and it captures every column of every row before anything is
  deleted.

Deletion order is computed from the reflected foreign keys and enforced here,
children before parents, so the delete never depends on a cascade firing.

Usage:
  env -u DATABASE_URL -u PRODDB -u STAGING_DB \\
    DATABASE_URL=postgresql+asyncpg://user@host/db \\
    python -m scripts.ops.run025.purge_reviewed_debris_rows --json \\
    --manifest /tmp/run025-debris-purge-manifest.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import sqlalchemy as sa

from scripts.ops.run021._common import (
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    open_session,
    require_database_url,
    utc_now_iso,
)
from scripts.ops.run025._dependencies import (
    InboundRef,
    RowKey,
    deletion_order,
    dependent_ids,
    inbound_refs,
    single_column_primary_keys,
)
from scripts.ops.run025._models import migration_target_tables
from scripts.ops.run025._references import (
    ReferenceArithmetic,
    mixed_reference_schemes,
    reference_arithmetic,
    reference_column,
)
from scripts.ops.run025.inventory_tenant_id_nulls import _reflect, dsn_label


@dataclass(frozen=True)
class ReviewedRow:
    """One row a named human has looked at and agreed is CI debris.

    The expectations are part of the record, not documentation. Each is re-checked
    against the database at run time, and a mismatch is a refusal: the approval was
    given for a row with these properties, so a row without them is a different
    row as far as that approval is concerned.

    There are two shapes of evidence here, because the rows come in two kinds.

    **Created by a known account.** ``creator_column`` plus ``creator_email``: the
    row names a user, and that user must still be the deactivated smoke runner with
    no tenant of its own. This is the stronger form and every row that *has* a
    creator column uses it.

    **Owned by a row that is itself reviewed debris.** ``parent_column``,
    ``parent_table`` and ``parent_row_id``, optionally with ``marker_column`` and
    ``marker_value``. ``audit_responses`` records no creator at all — there is no
    ``created_by_id`` on the table — so the only provenance available is that the
    row hangs off a run which *has* been shown to be smoke-test debris, and that it
    carries the marker the smoke test wrote. The parent must itself be in the
    reviewed set, checked by :func:`assert_reviewed_set_coherent`, so this borrows
    the parent's account evidence rather than inventing weaker evidence of its own.

    A row with neither is rejected at import time. "I could not establish where this
    came from" must never be a way of getting a row onto the list.
    """

    table: str
    row_id: int
    evidence: str
    creator_column: Optional[str] = None
    creator_email: Optional[str] = None
    parent_column: Optional[str] = None
    parent_table: Optional[str] = None
    parent_row_id: Optional[int] = None
    marker_column: Optional[str] = None
    marker_value: Optional[str] = None

    def __post_init__(self) -> None:
        has_creator = bool(self.creator_column and self.creator_email)
        has_parent = bool(self.parent_column and self.parent_table and self.parent_row_id is not None)
        if not has_creator and not has_parent:
            raise ValueError(
                f"{self.table}#{self.row_id} declares neither a creator nor a reviewed parent, so nothing "
                "about it can be re-verified against the database. A row whose provenance cannot be "
                "re-established must not be on the reviewed list at all."
            )
        if bool(self.marker_column) != bool(self.marker_value):
            raise ValueError(
                f"{self.table}#{self.row_id} declares half a marker expectation; give both "
                "marker_column and marker_value or neither"
            )

    @property
    def key(self) -> RowKey:
        return (self.table, self.row_id)

    @property
    def parent_key(self) -> Optional[RowKey]:
        if self.parent_table is None or self.parent_row_id is None:
            return None
        return (self.parent_table, self.parent_row_id)


#: The reviewed set, measured on production 2026-07-28 and agreed with David
#: Harris. Four rows were created directly by ``smoke-runner@plantexpand.com`` (user
#: id 4), a deactivated account with ``tenant_id`` NULL, which is why none of them
#: can inherit a tenant. Two more — the ``audit_responses`` rows — record no creator
#: at all and are held by their parent run plus the marker the smoke test wrote.
#:
#: Held as a literal, in code, deliberately. Passing primary keys on a command line
#: would make the delete set an operator's transcription of a review rather than the
#: review itself, and there would be nothing to re-verify against.
#:
#: The two responses were added on 2026-07-28 after the production dry run refused
#: on them: ``audit_responses.run_id`` is ``ON DELETE CASCADE``, so deleting the two
#: smoke runs would have destroyed them silently. They were then inspected and found
#: to be debris on the same evidence, which is the "another reviewed row, approved on
#: the same evidence" path — not an override, and deliberately not a sweep flag.
REVIEWED_DEBRIS: tuple[ReviewedRow, ...] = (
    ReviewedRow(
        table="audit_runs",
        row_id=5,
        creator_column="created_by_id",
        creator_email="smoke-runner@plantexpand.com",
        evidence='E2E smoke audit run, title "E2E Audit 20260327202714"',
    ),
    ReviewedRow(
        table="audit_runs",
        row_id=6,
        creator_column="created_by_id",
        creator_email="smoke-runner@plantexpand.com",
        evidence='E2E smoke audit run, title "E2E Audit 20260327213101"',
    ),
    ReviewedRow(
        table="audit_findings",
        row_id=4,
        creator_column="created_by_id",
        creator_email="smoke-runner@plantexpand.com",
        evidence="finding raised inside one of the two E2E smoke runs above",
    ),
    ReviewedRow(
        table="risks_v2",
        row_id=2,
        creator_column="created_by",
        creator_email="smoke-runner@plantexpand.com",
        evidence='auto-escalation of that finding, title "Audit escalation: AUD-2026-0006 / FND-2026-0001"',
    ),
    # The single answer each smoke run recorded, two and three seconds after its
    # parent run was created. Genuine runs in production carry 3 to 58 responses;
    # these carry exactly one each, on the same question, both "yes". No creator
    # column exists on this table, so the parent run and the marker are the evidence.
    ReviewedRow(
        table="audit_responses",
        row_id=1,
        parent_column="run_id",
        parent_table="audit_runs",
        parent_row_id=5,
        marker_column="notes",
        marker_value="E2E response",
        evidence='sole response of smoke run 5, notes "E2E response", written 2s after the run',
    ),
    ReviewedRow(
        table="audit_responses",
        row_id=2,
        parent_column="run_id",
        parent_table="audit_runs",
        parent_row_id=6,
        marker_column="notes",
        marker_value="E2E response",
        evidence='sole response of smoke run 6, notes "E2E response", written 3s after the run',
    ),
)

#: ``users`` is read to re-verify provenance, and it is under FORCE RLS too, so its
#: visibility has to be established alongside the target tables.
PROVENANCE_TABLE = "users"

#: Every reviewed table must have this column in the *database*, whatever its model
#: says. Three facts depend on it and none of them degrade gracefully: "still
#: tenant-less" is the reviewed property, ``tenant_id IS NULL`` is restated in the
#: DELETE so the statement itself cannot remove an attributed row, and RLS visibility
#: is reasoned about in terms of it. ``audit_responses`` is the reason this is
#: checked rather than assumed — the column exists in production but
#: ``AuditResponse`` does not declare it, so a database built from model metadata
#: rather than the migration chain does not have it at all.
TENANT_COLUMN = "tenant_id"


class PurgeBlocked(RuntimeError):
    """Raised when the reviewed row set cannot be deleted safely."""


class PreconditionDrifted(RuntimeError):
    """Raised when the database stopped matching the plan between plan and apply."""


def reviewed_tables(reviewed: tuple[ReviewedRow, ...] = REVIEWED_DEBRIS) -> list[str]:
    return sorted({row.table for row in reviewed})


def assert_reviewed_set_coherent(reviewed: tuple[ReviewedRow, ...] = REVIEWED_DEBRIS) -> None:
    """Check the list against itself, before any database is opened.

    Two ways a hand-edited literal goes wrong, both of which would otherwise only
    show up as a confusing database result:

    *Duplicates.* The same row twice would be counted twice in the manifest and
    would make the second DELETE's rowcount zero, which the apply path reads as
    drift.

    *A parent nobody approved.* A row held by its parent is only as approved as that
    parent is. If the parent is not on the list, the row has no provenance — that is
    exactly the shape of "a genuine run's response added to the debris list", where
    the response would then be deleted on the strength of a run that was never
    reviewed and is not being deleted.
    """
    seen: set[RowKey] = set()
    for row in reviewed:
        if row.key in seen:
            raise RuntimeError(f"refusing to run: {row.table}#{row.row_id} appears twice in the reviewed set")
        seen.add(row.key)

    for row in reviewed:
        parent = row.parent_key
        if parent is not None and parent not in seen:
            raise RuntimeError(
                f"refusing to run: {row.table}#{row.row_id} is held by {parent[0]}#{parent[1]}, which is not "
                "itself in the reviewed set. A row whose only provenance is its parent inherits that "
                "parent's approval, so an unreviewed parent means the row has no approval to inherit."
            )


def assert_outside_migration_scope(reviewed: tuple[ReviewedRow, ...] = REVIEWED_DEBRIS) -> None:
    """Fail loudly if this script could ever delete a case or action row.

    The mirror image of ``backfill_tenant_orphan_rows._assert_disjoint``. Cases and
    actions are ``purge_tenant_orphan_rows``'s territory, reached by a predicate the
    migration itself declares; a hand-written primary key list must never be able
    to reach into that register.
    """
    overlap = sorted(set(reviewed_tables(reviewed)).intersection(migration_target_tables()))
    if overlap:
        raise RuntimeError(
            f"refusing to run: {', '.join(overlap)} are in the case/action migration scope, which is "
            "purge_tenant_orphan_rows' predicate-driven territory and must not be reached by a "
            "hand-written primary key list"
        )


# --------------------------------------------------------------------------- #
# Row-level security
# --------------------------------------------------------------------------- #


def rls_exposure(sync_session: Any, tables: list[str]) -> dict[str, Any]:
    """Whether this connection's role is subject to each table's RLS policies.

    Deliberately stronger than the ``relforcerowsecurity`` test used elsewhere in
    this package. FORCE is what makes the *owner* subject to its own policies, but a
    role that is not the owner is subject to plain ``relrowsecurity`` as well. A
    check that only looks at FORCE therefore reports "not blinded" for an
    application role reading an ordinary RLS table — the exact false negative that
    makes a zero look trustworthy.

    So the verdict per table is: RLS applies to me if I do not bypass RLS, the
    table has RLS enabled, and either it is FORCEd or I do not have the privileges
    of its owner.
    """
    bind = sync_session.get_bind()
    if bind.dialect.name != "postgresql":
        return {
            "dialect": bind.dialect.name,
            "role": None,
            "bypasses_rls": None,
            "per_table": {},
            "subject_to_rls": [],
            "determinable": False,
            "note": (
                "row-level security is a PostgreSQL feature; on this dialect there is nothing to "
                "check, and equally nothing that could be hiding rows"
            ),
        }

    role = sync_session.execute(sa.text("SELECT current_user")).scalar()
    bypasses = bool(
        sync_session.execute(
            sa.text(
                "SELECT COALESCE(bool_or(rolsuper OR rolbypassrls), false) FROM pg_roles WHERE rolname = current_user"
            )
        ).scalar()
    )

    rows = (
        sync_session.execute(
            sa.text(
                "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
                "pg_get_userbyid(c.relowner) AS owner, "
                "pg_has_role(current_user, c.relowner, 'USAGE') AS has_owner_privileges "
                "FROM pg_class AS c JOIN pg_namespace AS n ON n.oid = c.relnamespace "
                "WHERE n.nspname = current_schema()"
            )
        )
        .mappings()
        .all()
    )
    catalogue = {row["relname"]: dict(row) for row in rows}

    per_table: dict[str, Any] = {}
    for table in tables:
        entry = catalogue.get(table)
        if entry is None:
            per_table[table] = {"present": False}
            continue
        subject = bool(
            not bypasses
            and entry["relrowsecurity"]
            and (entry["relforcerowsecurity"] or not entry["has_owner_privileges"])
        )
        per_table[table] = {
            "present": True,
            "rls_enabled": bool(entry["relrowsecurity"]),
            "rls_forced": bool(entry["relforcerowsecurity"]),
            "owner": entry["owner"],
            "role_has_owner_privileges": bool(entry["has_owner_privileges"]),
            "subject_to_rls": subject,
        }

    return {
        "dialect": "postgresql",
        "role": role,
        "bypasses_rls": bypasses,
        "per_table": per_table,
        "subject_to_rls": sorted(name for name, info in per_table.items() if info.get("subject_to_rls")),
        "determinable": True,
    }


def _blinded_on(rls: dict[str, Any], table: str) -> bool:
    """True when a missing row in ``table`` cannot be trusted to mean "absent".

    A non-PostgreSQL dialect answers False: there is no RLS to hide anything.
    """
    if not rls.get("determinable"):
        return False
    return bool(rls["per_table"].get(table, {}).get("subject_to_rls"))


# --------------------------------------------------------------------------- #
# Per-row verification
# --------------------------------------------------------------------------- #


@dataclass
class RowVerdict:
    """What the database currently says about one reviewed row."""

    reviewed: ReviewedRow
    row: Optional[dict[str, Any]]
    creator: Optional[dict[str, Any]]
    problems: list[str]

    @property
    def present(self) -> bool:
        return self.row is not None

    @property
    def deletable(self) -> bool:
        return self.present and not self.problems

    @property
    def key(self) -> RowKey:
        return (self.reviewed.table, self.reviewed.row_id)

    def as_report(self) -> dict[str, Any]:
        reviewed = self.reviewed
        row = self.row or {}
        report: dict[str, Any] = {
            "table": reviewed.table,
            "id": reviewed.row_id,
            "evidence": reviewed.evidence,
            "present": self.present,
            "tenant_id": row.get(TENANT_COLUMN, "(row not read)"),
            "problems": list(self.problems),
        }
        if reviewed.creator_column is not None:
            report["creator_column"] = reviewed.creator_column
            report["creator_id"] = row.get(reviewed.creator_column)
            report["creator_email"] = (self.creator or {}).get("email")
            report["creator_is_active"] = (self.creator or {}).get("is_active")
            report["creator_tenant_id"] = (self.creator or {}).get("tenant_id")
            report["expected_creator_email"] = reviewed.creator_email
        else:
            report["creator_column"] = None
            report["provenance"] = (
                f"no creator column on {reviewed.table}; held by reviewed parent "
                f"{reviewed.parent_table}#{reviewed.parent_row_id}"
            )
        if reviewed.parent_column is not None:
            report["parent_column"] = reviewed.parent_column
            report["parent_id"] = row.get(reviewed.parent_column)
            report["expected_parent"] = f"{reviewed.parent_table}#{reviewed.parent_row_id}"
        if reviewed.marker_column is not None:
            report["marker_column"] = reviewed.marker_column
            report["marker"] = row.get(reviewed.marker_column)
            report["expected_marker"] = reviewed.marker_value
        return report


def _missing_expectation_columns(reviewed: ReviewedRow, columns: set[str]) -> list[str]:
    """Every column an expectation names must exist before the row can be read.

    A missing column is not a soft failure. ``dict.get`` on a column that is not
    there returns ``None``, which for the tenant check reads as "tenant-less" and for
    the marker check reads as "marker absent" — the first silently agreeing with the
    reviewed property and the second silently disagreeing with it. Neither is an
    answer, so the row is refused before anything is read.
    """
    table = reviewed.table
    problems: list[str] = []

    if TENANT_COLUMN not in columns:
        problems.append(
            f"{table} has no {TENANT_COLUMN} column in this database. The reviewed property is that "
            f"the row is tenant-less, and the DELETE restates {TENANT_COLUMN} IS NULL as its own "
            "guard; with no such column neither is possible. Note that AuditResponse, AuditQuestion "
            "and AuditSection do not declare tenant_id even though production has it, so a database "
            "built from model metadata rather than the migration chain will land here"
        )
    if reviewed.creator_column is not None and reviewed.creator_column not in columns:
        problems.append(
            f"{table} has no {reviewed.creator_column} column in this database, so the row's "
            "provenance cannot be re-verified and it must not be deleted on trust"
        )
    if reviewed.parent_column is not None and reviewed.parent_column not in columns:
        problems.append(
            f"{table} has no {reviewed.parent_column} column in this database, so it cannot be shown "
            f"to still hang off reviewed debris {reviewed.parent_table}#{reviewed.parent_row_id}"
        )
    if reviewed.marker_column is not None and reviewed.marker_column not in columns:
        problems.append(
            f"{table} has no {reviewed.marker_column} column in this database, so the "
            f"{reviewed.marker_value!r} marker the review turned on cannot be re-read"
        )
    return problems


async def verify_reviewed_row(
    db: Any,
    reviewed: ReviewedRow,
    *,
    columns: set[str],
    rls: dict[str, Any],
    lock: str = "",
) -> RowVerdict:
    """Re-establish, from the database, every fact the review rested on.

    Called once while planning and again inside the apply transaction with
    ``lock='" FOR UPDATE"'``, so a change committed in between cannot slip past:
    the second call reads the locked row and disagrees.
    """
    problems: list[str] = []
    table = reviewed.table

    missing = _missing_expectation_columns(reviewed, columns)
    if missing:
        return RowVerdict(reviewed, None, None, missing)

    # Table and column names come from the reviewed literal above and are checked
    # against the reflected schema before use. Nothing here originates in argv.
    row = (
        (
            await db.execute(
                sa.text(f"SELECT * FROM {table} WHERE id = :row_id{lock}"),  # noqa: S608
                {"row_id": reviewed.row_id},
            )
        )
        .mappings()
        .one_or_none()
    )

    if row is None:
        if _blinded_on(rls, table):
            problems.append(
                f"{table}#{reviewed.row_id} was not returned, and this role is subject to "
                f"{table}'s row-level security, so absence cannot be distinguished from being "
                "hidden. A tenant-less row never satisfies tenant_isolation. Re-run as a role "
                "with rolsuper or rolbypassrls"
            )
        return RowVerdict(reviewed, None, None, problems)

    row_dict = dict(row)

    if row_dict.get(TENANT_COLUMN) is not None:
        problems.append(
            f"{table}#{reviewed.row_id} now holds tenant_id={row_dict[TENANT_COLUMN]!r}. It was "
            "reviewed as tenant-less; something has attributed it since. Deleting an attributed "
            "row is outside what was approved"
        )

    if reviewed.parent_column is not None:
        actual_parent = row_dict.get(reviewed.parent_column)
        if actual_parent != reviewed.parent_row_id:
            problems.append(
                f"{table}#{reviewed.row_id} now has {reviewed.parent_column}={actual_parent!r}, not "
                f"{reviewed.parent_row_id!r}. Its whole provenance is that it hangs off reviewed "
                f"debris {reviewed.parent_table}#{reviewed.parent_row_id}; re-parented, it is a row "
                "belonging to something nobody has looked at"
            )

    if reviewed.marker_column is not None:
        actual_marker = row_dict.get(reviewed.marker_column)
        normalised = actual_marker.strip() if isinstance(actual_marker, str) else actual_marker
        if normalised != reviewed.marker_value:
            problems.append(
                f"{table}#{reviewed.row_id} now has {reviewed.marker_column}={actual_marker!r}, not "
                f"{reviewed.marker_value!r}. That marker is what identified it as the smoke test's own "
                "output rather than a real answer someone recorded"
            )

    if reviewed.creator_column is None:
        # No creator column exists on this table; the parent and marker checks above
        # are the provenance, and assert_reviewed_set_coherent has already shown the
        # parent is itself reviewed.
        return RowVerdict(reviewed, row_dict, None, problems)

    creator_id = row_dict.get(reviewed.creator_column)
    if creator_id is None:
        problems.append(
            f"{table}#{reviewed.row_id} has no {reviewed.creator_column}, so it cannot be shown to "
            f"have been created by {reviewed.creator_email}"
        )
        return RowVerdict(reviewed, row_dict, None, problems)

    creator = (
        (
            await db.execute(
                sa.text(f"SELECT id, email, is_active, tenant_id FROM {PROVENANCE_TABLE} WHERE id = :creator_id"),
                {"creator_id": creator_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if creator is None:
        detail = (
            "this role is subject to users' row-level security, and the smoke-runner account holds "
            "no tenant_id, so it is invisible here"
            if _blinded_on(rls, PROVENANCE_TABLE)
            else "there is no such user row"
        )
        problems.append(
            f"{table}#{reviewed.row_id} names {reviewed.creator_column}={creator_id} but that user "
            f"could not be read: {detail}. Provenance is the whole basis for deleting this row"
        )
        return RowVerdict(reviewed, row_dict, None, problems)

    creator_dict = dict(creator)
    actual_email = (creator_dict.get("email") or "").strip().lower()
    if actual_email != reviewed.creator_email:
        problems.append(
            f"{table}#{reviewed.row_id} was created by {actual_email!r}, not "
            f"{reviewed.creator_email!r}. The review covered a row created by the CI smoke runner"
        )
    if creator_dict.get("is_active"):
        problems.append(
            f"{table}#{reviewed.row_id}'s creator {actual_email!r} is active again. A live account's "
            "records are not CI debris by virtue of the account name; re-establish the evidence"
        )
    if creator_dict.get("tenant_id") is not None:
        problems.append(
            f"{table}#{reviewed.row_id}'s creator {actual_email!r} now holds "
            f"tenant_id={creator_dict['tenant_id']!r}. This row is therefore inheritable and belongs "
            "in backfill_tenant_orphan_rows, not in a delete"
        )

    return RowVerdict(reviewed, row_dict, creator_dict, problems)


# --------------------------------------------------------------------------- #
# Dependency scan
# --------------------------------------------------------------------------- #


def _out_of_scope_effect(ref: InboundRef) -> str:
    if ref.deletes_child:
        return "WOULD BE DELETED by cascade — destruction of a record outside the reviewed set"
    if ref.mutates_child:
        return f"WOULD BE MODIFIED ({ref.on_delete}) — silent rewrite of a row outside the reviewed set"
    return "WOULD BLOCK the delete — the statement will fail"


async def scan_dependents(
    db: Any,
    *,
    present: list[RowVerdict],
) -> tuple[list[tuple[RowKey, RowKey]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Find every row that references a doomed row, inside the set and outside it."""
    reviewed_keys = {verdict.key for verdict in present}
    parents = sorted({verdict.reviewed.table for verdict in present})
    refs = await db.run_sync(inbound_refs, parents)

    # Only the tables that actually reference a doomed row need a key resolved,
    # rather than all 240 in the schema.
    referencing = sorted({ref.child_table for table_refs in refs.values() for ref in table_refs})
    child_keys = await db.run_sync(single_column_primary_keys, referencing)

    edges: list[tuple[RowKey, RowKey]] = []
    in_scope: list[dict[str, Any]] = []
    out_of_scope: list[dict[str, Any]] = []
    unscannable: list[str] = []

    for verdict in present:
        parent_key = verdict.key
        for ref in refs.get(verdict.reviewed.table, []):
            key_column = child_keys.get(ref.child_table)
            if key_column is None:
                unscannable.append(
                    f"{ref.child_table} references {ref.parent_table} via {ref.constraint} but has no "
                    "single-column primary key, so its dependent rows cannot be enumerated or named"
                )
                continue
            for child_id in await dependent_ids(db, ref, verdict.reviewed.row_id, key_column=key_column):
                child_key: RowKey = (ref.child_table, child_id)
                record = {
                    "constraint": ref.constraint,
                    "reference": ref.describe(),
                    "parent": f"{verdict.reviewed.table}#{verdict.reviewed.row_id}",
                    "child": f"{ref.child_table}#{child_id}",
                    "child_key_column": key_column,
                    "on_delete": ref.on_delete,
                }
                if child_key in reviewed_keys:
                    edges.append((child_key, parent_key))
                    in_scope.append(record)
                else:
                    record["effect"] = _out_of_scope_effect(ref)
                    out_of_scope.append(record)

    return edges, in_scope, out_of_scope, sorted(set(unscannable))


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #


async def plan(*, reviewed: tuple[ReviewedRow, ...] = REVIEWED_DEBRIS) -> dict[str, Any]:
    """Work out whether the reviewed rows may be deleted. Read-only."""
    assert_reviewed_set_coherent(reviewed)
    assert_outside_migration_scope(reviewed)
    tables = reviewed_tables(reviewed)
    blockers: list[str] = []

    async with await open_session() as db:
        reflected = await db.run_sync(_reflect, tables + [PROVENANCE_TABLE])
        rls = await db.run_sync(rls_exposure, tables + [PROVENANCE_TABLE])
        parent_keys = await db.run_sync(single_column_primary_keys, tables)

        missing_tables = [table for table in tables if not reflected[table].get("exists")]
        if missing_tables:
            blockers.append(
                f"{', '.join(missing_tables)} do not exist in this database, so the reviewed rows "
                "cannot be verified, let alone deleted"
            )
        if not reflected[PROVENANCE_TABLE].get("exists"):
            blockers.append("there is no users table in this database, so no row's provenance can be re-verified")

        # Rows are addressed as `id` throughout — in the reviewed literal, in the
        # manifest and in the DELETE. That is true of every table here, but it is
        # checked rather than assumed, because a table keyed on anything else would
        # otherwise be addressed by a column that means something different.
        for table in tables:
            if reflected[table].get("exists") and parent_keys.get(table) != "id":
                blockers.append(
                    f"{table}'s primary key is {parent_keys.get(table)!r}, not 'id'. The reviewed set "
                    "names rows by id, so those identifiers no longer address what was reviewed"
                )

        verdicts: list[RowVerdict] = []
        for entry in reviewed:
            info = reflected[entry.table]
            if not info.get("exists"):
                continue
            verdicts.append(await verify_reviewed_row(db, entry, columns=set(info.get("columns") or ()), rls=rls))

        for verdict in verdicts:
            blockers.extend(verdict.problems)

        present = [verdict for verdict in verdicts if verdict.present]
        absent = [verdict for verdict in verdicts if not verdict.present and not verdict.problems]

        if absent and present:
            blockers.append(
                f"{len(absent)} of the {len(reviewed)} reviewed rows are already gone while "
                f"{len(present)} remain: {', '.join(f'{v.reviewed.table}#{v.reviewed.row_id}' for v in absent)}. "
                "The dependency graph and the reference arithmetic were reviewed over the whole set, so a "
                "partial set is a different change and needs looking at again"
            )

        edges, in_scope, out_of_scope, unscannable = await scan_dependents(db, present=present)
        blockers.extend(unscannable)

        if out_of_scope:
            affected = ", ".join(sorted({record["child"] for record in out_of_scope}))
            blockers.append(
                f"{len(out_of_scope)} row(s) outside the reviewed set are affected by these deletes "
                f"({affected}); see dependents_outside_reviewed_set for the constraint and effect of "
                "each. Deleting anyway would destroy or silently rewrite records nobody approved"
            )

        arithmetic: list[ReferenceArithmetic] = []
        caveats: list[dict[str, Any]] = []
        for table in sorted({verdict.reviewed.table for verdict in present}):
            columns = set(reflected[table].get("columns") or ())
            column = reference_column(columns)
            if column is None:
                continue
            doomed = {
                verdict.reviewed.row_id: (verdict.row or {}).get(column)
                for verdict in present
                if verdict.reviewed.table == table
            }
            arithmetic.extend(
                await reference_arithmetic(db, table=table, column=column, key_column="id", doomed=doomed)
            )
            caveat = await mixed_reference_schemes(db, table, column)
            if caveat is not None:
                caveats.append(caveat)

        hazardous = [entry for entry in arithmetic if entry.is_hazardous]

        try:
            order = deletion_order({verdict.key for verdict in present}, edges)
        except RuntimeError as exc:
            order = []
            blockers.append(str(exc))

    return {
        "database": dsn_label(require_database_url()),
        "reviewed_rows": len(reviewed),
        "rows_present": len(present),
        "rows_already_absent": [f"{v.reviewed.table}#{v.reviewed.row_id}" for v in absent],
        "rows_to_delete": len(order),
        "deletion_order": [f"{table}#{row_id}" for table, row_id in order],
        "row_verification": [verdict.as_report() for verdict in verdicts],
        "dependents_inside_reviewed_set": in_scope,
        "dependents_outside_reviewed_set": out_of_scope,
        "reference_arithmetic": [entry.as_report() for entry in arithmetic],
        "reference_scheme_caveats": caveats,
        "row_level_security": rls,
        "blockers": blockers,
        "_order": order,
        "_verdicts": verdicts,
        "_hazardous": hazardous,
    }


# --------------------------------------------------------------------------- #
# Applying
# --------------------------------------------------------------------------- #


async def apply_plan(
    order: list[RowKey],
    *,
    reviewed: tuple[ReviewedRow, ...] = REVIEWED_DEBRIS,
) -> dict[str, int]:
    """Delete the planned rows, children first, in one transaction.

    Everything is re-verified inside that transaction with the rows locked, because
    the plan was computed against a snapshot that a concurrent writer — or a second
    copy of this script — may have moved on from. Two things could otherwise go
    wrong silently:

    * a row stops being debris between plan and apply, and gets deleted anyway;
    * the ``DELETE`` matches nothing, because RLS filtered it, and the run reports
      success having removed nothing.

    So each statement is checked to have removed exactly one row, and anything else
    rolls the whole transaction back.
    """
    by_key = {(entry.table, entry.row_id): entry for entry in reviewed}
    deleted: dict[str, int] = {}

    async with await open_session() as db:
        dialect = await db.run_sync(lambda session: session.get_bind().dialect.name)
        # SQLite has no row locks and rejects the clause outright.
        lock = " FOR UPDATE" if dialect == "postgresql" else ""
        reflected = await db.run_sync(_reflect, sorted({table for table, _ in order}) + [PROVENANCE_TABLE])
        rls = await db.run_sync(rls_exposure, sorted({table for table, _ in order}) + [PROVENANCE_TABLE])

        for key in order:
            entry = by_key.get(key)
            if entry is None:
                await db.rollback()
                raise PreconditionDrifted(
                    f"{key[0]}#{key[1]} is not in the reviewed set; refusing to delete a row nobody approved"
                )
            verdict = await verify_reviewed_row(
                db,
                entry,
                columns=set(reflected[entry.table].get("columns") or ()),
                rls=rls,
                lock=lock,
            )
            if not verdict.deletable:
                await db.rollback()
                raise PreconditionDrifted(
                    f"{entry.table}#{entry.row_id} no longer matches the reviewed evidence: "
                    f"{'; '.join(verdict.problems) or 'the row is no longer there'}. Nothing was deleted"
                )

        for table, row_id in order:
            entry = by_key[(table, row_id)]
            result = await db.execute(
                # tenant_id IS NULL is restated here rather than trusted from the
                # check above: it makes the statement itself unable to remove an
                # attributed row.
                sa.text(f"DELETE FROM {table} WHERE id = :row_id AND {TENANT_COLUMN} IS NULL"),  # noqa: S608
                {"row_id": row_id},
            )
            affected = result.rowcount or 0
            if affected != 1:
                await db.rollback()
                raise PreconditionDrifted(
                    f"DELETE FROM {table} WHERE id = {row_id} removed {affected} row(s), not 1. "
                    "Under row-level security a delete that matches nothing reports no error, so this "
                    "is treated as a failure rather than a no-op. Nothing was deleted"
                )
            deleted[table] = deleted.get(table, 0) + affected

        await db.commit()
    return deleted


def _rows_by_table(verdicts: list[RowVerdict]) -> dict[str, list[dict[str, Any]]]:
    """Full pre-deletion row contents, grouped by table, for the manifest.

    Whole rows rather than a projection: this file is the only record of what was
    destroyed, so it has to be complete enough to reconstruct from.
    """
    rows: dict[str, list[dict[str, Any]]] = {}
    for verdict in verdicts:
        if verdict.row is None:
            continue
        rows.setdefault(verdict.reviewed.table, []).append(verdict.row)
    return rows


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


async def _amain(args: argparse.Namespace) -> int:
    if args.tenant_id is not None:
        print(
            "REFUSING: --tenant-id means nothing here. Every row in the reviewed set has no tenant, "
            "which is the entire reason it is in the set; a tenant filter could only ever exclude all "
            "of them or none of them.",
            file=sys.stderr,
        )
        return 2

    mode = enforce_apply_safety(apply=args.apply, i_understand_prod=args.i_understand_prod)
    require_database_url()

    result = await plan()
    order = result.pop("_order")
    verdicts = result.pop("_verdicts")
    hazardous = result.pop("_hazardous")

    blockers = list(result["blockers"])
    if hazardous and not args.accept_reference_reuse_risk:
        for entry in hazardous:
            blockers.append(
                f"{entry.table}: deleting {', '.join(entry.doomed_references)} moves the next "
                f"{entry.pattern} reference from {entry.next_before} to {entry.next_after} "
                f"({entry.explain()}). {entry.as_report()['verdict']}. Re-run with "
                "--accept-reference-reuse-risk only if a named human has accepted that"
            )
    result["blockers"] = blockers

    payload: dict[str, Any] = {"script": "purge_reviewed_debris_rows", "mode": mode, **result}

    if args.manifest:
        _write_manifest(
            Path(args.manifest),
            {
                "script": "purge_reviewed_debris_rows",
                "mode": mode,
                "database": result["database"],
                "captured_at": utc_now_iso(),
                "deletion_order": result["deletion_order"],
                "row_verification": result["row_verification"],
                "reference_arithmetic": result["reference_arithmetic"],
                "dependents_inside_reviewed_set": result["dependents_inside_reviewed_set"],
                "dependents_outside_reviewed_set": result["dependents_outside_reviewed_set"],
                "row_level_security": result["row_level_security"],
                "rows": _rows_by_table(verdicts),
                "creators": {
                    f"{verdict.reviewed.table}#{verdict.reviewed.row_id}": verdict.creator
                    for verdict in verdicts
                    if verdict.creator is not None
                },
                "blockers": blockers,
                "note": (
                    "Every column of every row proposed for deletion, plus the user row each was "
                    "attributed to, captured before any delete ran. These rows belong to no tenant, so "
                    "the deletion cannot be recorded in the per-tenant hash-chained audit_log_entries "
                    "without inventing a tenant for it — the one register an external auditor is "
                    "entitled to trust. Attach this file to the change record instead."
                ),
            },
        )
        payload["manifest_written_to"] = str(args.manifest)

    if blockers:
        payload["outcome"] = "refused"
        payload["note"] = "Nothing was deleted. Resolve every blocker above, then re-run the dry run."
        emit_report(payload, as_json=args.json)
        return 3

    if not order:
        payload["outcome"] = "nothing-to-do"
        payload["note"] = (
            "Every reviewed row is already absent, and this role is not subject to row-level "
            "security on their tables, so that absence is real rather than a filtered view. Re-run "
            "backfill_tenant_orphan_rows to confirm it now reports inheritance only."
        )
        emit_report(payload, as_json=args.json)
        return 0

    if not args.apply:
        payload["outcome"] = "dry-run"
        payload["note"] = (
            f"No writes performed. {len(order)} row(s) would be deleted in the order shown. Review "
            "'row_verification' and 'reference_arithmetic', keep the manifest with the change record, "
            "then re-run with --apply --i-understand-prod --manifest <path>."
        )
        emit_report(payload, as_json=args.json)
        return 1

    if not args.manifest:
        payload["outcome"] = "refused"
        payload["note"] = "--apply requires --manifest: an unrecorded delete of audited rows is not acceptable."
        emit_report(payload, as_json=args.json)
        return 2

    try:
        payload["deleted"] = await apply_plan(order)
    except PreconditionDrifted as exc:
        payload["outcome"] = "refused"
        payload["note"] = f"Rolled back, nothing deleted: {exc}"
        emit_report(payload, as_json=args.json)
        return 3

    payload["outcome"] = "applied"
    payload["note"] = (
        "Rows deleted, children first. Now run backfill_tenant_orphan_rows: it should report 816 rows, "
        "all inherited, none defaulted."
    )
    emit_report(payload, as_json=args.json)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    parser.add_argument(
        "--manifest",
        default=None,
        help="Path to write the full pre-deletion row contents. Required with --apply.",
    )
    parser.add_argument(
        "--accept-reference-reuse-risk",
        action="store_true",
        default=False,
        dest="accept_reference_reuse_risk",
        help="Proceed even though a deleted reference number could later be reissued or collide.",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
