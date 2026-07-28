"""Tests for the reviewed-debris purge (Run025 ops park).

The safety behaviours *are* the product here, so each refusal is proved by building
the condition that should trigger it and observing the refusal, rather than by
asserting that a branch exists in the source.

Two layers, for two different reasons:

* **SQLite-backed** — the decision logic runs against a real database with real
  reflected foreign keys, real ``ON DELETE`` rules and real rows. That covers
  provenance drift, out-of-set cascades, deletion order, the dry-run default, the
  manifest and the ``rowcount != 1`` guard, and it runs in the unit job with no
  services.
* **PostgreSQL-backed** — row-level security and the ``tenant_id`` nullability drift
  that every production orphan depends on cannot be reproduced on SQLite at all.
  Those live in ``tests/integration/test_run025_reviewed_debris_purge_postgres.py``.

Nothing here imports the FastAPI app. The ops scripts do not need it, and walking
``app.routes`` across the 0.135/0.140 FastAPI split has already cost three lanes
time this week.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from scripts.ops.run025 import purge_reviewed_debris_rows as purge
from scripts.ops.run025._references import ReferenceArithmetic, next_sequence, reference_column, reference_parts
from scripts.ops.run025.purge_reviewed_debris_rows import (
    REVIEWED_DEBRIS,
    PreconditionDrifted,
    ReviewedRow,
    apply_plan,
    assert_outside_migration_scope,
    assert_reviewed_set_coherent,
)
from scripts.ops.run025.purge_reviewed_debris_rows import main as purge_main
from scripts.ops.run025.purge_reviewed_debris_rows import plan

# --------------------------------------------------------------------------- #
# The reviewed set is the approval. It must not drift silently.
# --------------------------------------------------------------------------- #


def test_the_reviewed_set_is_exactly_the_six_rows_that_were_measured():
    """Pinned deliberately.

    These six primary keys are the whole authority for a production delete. If a
    later change adds a seventh row, moves an id, or points a row at a different
    account, that is a new approval and this test should be the thing that says so.

    It went from four to six on 2026-07-28, after the production dry run refused on
    the two ``audit_responses`` rows that cascade off the smoke runs and they were
    inspected and approved on the same evidence.
    """
    assert [(row.table, row.row_id, row.creator_column) for row in REVIEWED_DEBRIS] == [
        ("audit_runs", 5, "created_by_id"),
        ("audit_runs", 6, "created_by_id"),
        ("audit_findings", 4, "created_by_id"),
        ("risks_v2", 2, "created_by"),
        ("audit_responses", 1, None),
        ("audit_responses", 2, None),
    ]
    assert {row.creator_email for row in REVIEWED_DEBRIS if row.creator_email} == {"smoke-runner@plantexpand.com"}


def test_the_two_responses_are_held_by_their_parent_run_and_the_smoke_marker():
    """``audit_responses`` has no creator column at all, so the account evidence the
    other four rest on is unavailable and has to be borrowed from the parent."""
    responses = [row for row in REVIEWED_DEBRIS if row.table == "audit_responses"]
    assert [(row.row_id, row.parent_key, row.marker_column, row.marker_value) for row in responses] == [
        (1, ("audit_runs", 5), "notes", "E2E response"),
        (2, ("audit_runs", 6), "notes", "E2E response"),
    ]
    reviewed_keys = {row.key for row in REVIEWED_DEBRIS}
    assert all(row.parent_key in reviewed_keys for row in responses)


def test_a_row_with_neither_a_creator_nor_a_reviewed_parent_cannot_be_constructed():
    """ "I could not work out where this came from" must not be a way onto the list."""
    with pytest.raises(ValueError, match="neither a creator nor a reviewed parent"):
        ReviewedRow(table="audit_responses", row_id=9, evidence="looked like debris to me")


def test_half_a_marker_expectation_is_rejected():
    with pytest.raises(ValueError, match="half a marker expectation"):
        ReviewedRow(
            table="audit_responses",
            row_id=9,
            parent_column="run_id",
            parent_table="audit_runs",
            parent_row_id=5,
            marker_column="notes",
            evidence="marker column named, but nothing to compare it against",
        )


def test_a_row_held_by_a_parent_nobody_reviewed_is_refused_before_any_query():
    """The shape of a genuine run's response being added to the debris list.

    The response would be deleted on the strength of a run that was never reviewed
    and is not being deleted, so the approval it claims to inherit does not exist.
    """
    assert_reviewed_set_coherent()
    with pytest.raises(RuntimeError, match="which is not itself in the reviewed set"):
        assert_reviewed_set_coherent(
            REVIEWED_DEBRIS
            + (
                ReviewedRow(
                    table="audit_responses",
                    row_id=3,
                    parent_column="run_id",
                    parent_table="audit_runs",
                    parent_row_id=7,
                    marker_column="notes",
                    marker_value="E2E response",
                    evidence="a genuine run's response, claimed as debris",
                ),
            )
        )


def test_the_same_row_twice_is_refused():
    with pytest.raises(RuntimeError, match="appears twice"):
        assert_reviewed_set_coherent(REVIEWED_DEBRIS + (REVIEWED_DEBRIS[0],))


def test_risks_v2_creator_column_is_created_by_not_created_by_id():
    """Every other table uses ``created_by_id``; a generic sweep would miss this one."""
    by_table = {row.table: row.creator_column for row in REVIEWED_DEBRIS}
    assert by_table["risks_v2"] == "created_by"
    assert by_table["audit_runs"] == "created_by_id"


def test_this_script_can_never_reach_a_case_or_action_table():
    """The mirror of ``backfill._assert_disjoint``.

    ``purge_tenant_orphan_rows`` owns the case/action registers via a predicate the
    migration itself declares. A hand-written primary key list must not be able to
    delete an incident.
    """
    assert_outside_migration_scope()
    with pytest.raises(RuntimeError, match="case/action migration scope"):
        assert_outside_migration_scope(
            REVIEWED_DEBRIS
            + (
                ReviewedRow(
                    table="incidents",
                    row_id=1,
                    creator_column="created_by_id",
                    creator_email="smoke-runner@plantexpand.com",
                    evidence="not a real review",
                ),
            )
        )


# --------------------------------------------------------------------------- #
# Reference-number arithmetic
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "reference,expected",
    [
        ("AUD-2026-0006", ("AUD", "2026", 6)),
        ("FND-2026-0001", ("FND", "2026", 1)),
        ("RSK-2026-0002", ("RSK", "2026", 2)),
        ("RTAACT-2026-0001", ("RTAACT", "2026", 1)),
        # A portal hex reference has no ordinal suffix. Reading FFFFFFFF as
        # 4294967295 would produce a confident, wrong answer about the sequence.
        ("INC-2026-FFFFFFFF", None),
        ("nonsense", None),
        (None, None),
        ("", None),
    ],
)
def test_only_sequential_references_are_parsed(reference, expected):
    assert reference_parts(reference) == expected


@pytest.mark.parametrize(
    "columns,expected",
    [
        ({"id", "reference_number", "tenant_id"}, "reference_number"),
        # risks_v2 names it `reference`; a helper hardcoding the other name crashes.
        ({"id", "reference", "tenant_id"}, "reference"),
        # ReferenceNumberService._ref_column prefers reference_number, so this does.
        ({"id", "reference", "reference_number"}, "reference_number"),
        # compliance_evidence_links has neither, and that is a normal answer.
        ({"id", "tenant_id"}, None),
    ],
)
def test_the_reference_column_is_resolved_the_way_the_service_resolves_it(columns, expected):
    assert reference_column(columns) == expected


@pytest.mark.parametrize(
    "max_ref,count,expected,why",
    [
        ("FND-2026-0001", 1, 2, "the ordinary case: one row, suffix 1, next is 2"),
        (None, 0, 1, "an empty pattern starts at 1"),
        # COUNT(*) is part of the maximum, so a table with gaps is driven by the count.
        ("FND-2026-0002", 9, 10, "nine rows but a low MAX: the count wins"),
        # The swallowed int() is reproduced, not corrected. A hex MAX yields max_seq=0
        # and the next value falls to COUNT(*) + 1.
        ("INC-2026-FFFFFFFF", 4, 5, "an unparsable MAX collapses max_seq to 0"),
        ("", 3, 4, "an empty MAX is falsy and contributes nothing"),
    ],
)
def test_next_sequence_reproduces_the_service_including_its_swallowed_int(max_ref, count, expected, why):
    assert next_sequence(max_ref, count) == expected, why


def test_the_real_reference_number_service_agrees_with_this_arithmetic():
    """Guard against the two implementations drifting apart.

    If ``_next_sequence`` is ever fixed to stop swallowing the parse failure, this
    fails and the safety check gets updated with it, rather than quietly modelling a
    version of the application that no longer exists.
    """
    import inspect

    from src.domain.services.reference_number import ReferenceNumberService

    source = inspect.getsource(ReferenceNumberService._next_sequence)
    assert "max(max_seq, count) + 1" in source
    assert "except (ValueError, IndexError):" in source
    assert 'int(max_ref.split("-")[-1])' in source


def _arithmetic(**overrides: Any) -> ReferenceArithmetic:
    defaults: dict[str, Any] = {
        "table": "audit_findings",
        "column": "reference_number",
        "pattern": "FND-2026-%",
        "doomed_references": ("FND-2026-0001",),
        "max_ref_before": "FND-2026-0001",
        "count_before": 1,
        "max_ref_after": None,
        "count_after": 0,
        "surviving_suffixes": (),
        "doomed_suffixes": (1,),
        "pattern_year_is_current": True,
    }
    defaults.update(overrides)
    return ReferenceArithmetic(**defaults)


def test_deleting_the_only_reference_for_a_pattern_makes_it_reissuable():
    entry = _arithmetic()
    assert (entry.next_before, entry.next_after) == (2, 1)
    assert entry.would_reissue == (1,)
    assert entry.would_collide == ()
    assert entry.is_hazardous is True
    assert "REISSUE" in entry.as_report()["verdict"]


def test_a_surviving_higher_reference_keeps_the_sequence_and_the_delete_is_safe():
    """The audit_runs case: 35 runs survive above the two being deleted."""
    entry = _arithmetic(
        table="audit_runs",
        pattern="AUD-2026-%",
        doomed_references=("AUD-2026-0005", "AUD-2026-0006"),
        doomed_suffixes=(5, 6),
        max_ref_before="AUD-2026-0041",
        count_before=37,
        max_ref_after="AUD-2026-0041",
        count_after=35,
        surviving_suffixes=tuple(range(7, 42)),
    )
    assert (entry.next_before, entry.next_after) == (42, 42)
    assert entry.is_hazardous is False
    assert entry.as_report()["verdict"].startswith("safe")


def test_a_count_driven_sequence_can_collide_with_a_row_that_still_exists():
    """The worse of the two outcomes, and the one that is an outage.

    In a table whose MAX does not parse, the next value is ``COUNT(*) + 1``.
    Deleting rows lowers the count onto references that are still present, and the
    column is UNIQUE, so the next record of that type cannot be created at all.
    """
    entry = _arithmetic(
        table="incidents",
        pattern="INC-2026-%",
        doomed_references=("INC-2026-0009",),
        doomed_suffixes=(9,),
        max_ref_before="INC-2026-FFFFFFFF",
        count_before=9,
        max_ref_after="INC-2026-FFFFFFFF",
        count_after=8,
        surviving_suffixes=(1, 2, 3, 4, 5, 6, 7, 8),
    )
    assert (entry.next_before, entry.next_after) == (10, 9)
    assert entry.would_collide == ()
    entry = _arithmetic(
        table="incidents",
        pattern="INC-2026-%",
        doomed_references=("INC-2026-0003",),
        doomed_suffixes=(3,),
        max_ref_before="INC-2026-FFFFFFFF",
        count_before=9,
        max_ref_after="INC-2026-FFFFFFFF",
        count_after=8,
        surviving_suffixes=(1, 2, 4, 5, 6, 7, 8, 9),
    )
    assert entry.next_after == 9
    assert entry.would_collide == (9,)
    assert "COLLISION" in entry.as_report()["verdict"]


def test_a_pattern_from_a_past_year_is_reported_as_harmless():
    """``generate()`` builds the pattern from ``datetime.now().year``.

    So a 2025 sequence cannot be minted against in 2026, and reporting it as a live
    hazard would train an operator to pass the override flag out of habit.
    """
    entry = _arithmetic(pattern="FND-2025-%", pattern_year_is_current=False, doomed_suffixes=())
    assert entry.is_hazardous is False
    assert "not the current year" in entry.as_report()["verdict"]


def test_the_arithmetic_is_shown_in_full_so_it_can_be_checked():
    assert _arithmetic().explain() == (
        "before: max(max_seq=1 (from 'FND-2026-0001'), count=1) + 1 = 2; "
        "after: max(max_seq=0 (no reference matched), count=0) + 1 = 1"
    )


# --------------------------------------------------------------------------- #
# Row-level security classification
# --------------------------------------------------------------------------- #


class _FakeBind:
    def __init__(self, dialect: str):
        self.dialect = type("_D", (), {"name": dialect})()


class _FakeSyncSession:
    """Enough of a sync session to answer ``rls_exposure``'s three queries."""

    def __init__(self, *, dialect: str = "postgresql", role: str = "app", bypasses: bool = False, catalogue=()):
        self._bind = _FakeBind(dialect)
        self._role = role
        self._bypasses = bypasses
        self._catalogue = list(catalogue)

    def get_bind(self):
        return self._bind

    def execute(self, statement, _params=None):
        sql = str(statement)
        # Checked most-specific-first: the catalogue query also mentions
        # current_user, inside pg_has_role().
        if "pg_class" in sql:
            return _Mappings(self._catalogue)
        if "pg_roles" in sql:
            return _Scalar(self._bypasses)
        return _Scalar(self._role)


class _Scalar:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _Mappings:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def scalars(self):
        """``_rls_blinded`` reads the same catalogue, but only asks for the names of
        FORCE-RLS tables, so the fake applies that query's WHERE clause itself."""
        return _Scalars([row["relname"] for row in self._rows if row["relforcerowsecurity"]])


class _Scalars:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


def _catalogue_row(name: str, *, enabled: bool, forced: bool, owner: str = "dbowner", is_owner: bool = False):
    return {
        "relname": name,
        "relrowsecurity": enabled,
        "relforcerowsecurity": forced,
        "owner": owner,
        "has_owner_privileges": is_owner,
    }


def test_force_rls_makes_even_the_owner_subject_to_the_policy():
    session = _FakeSyncSession(catalogue=[_catalogue_row("audit_runs", enabled=True, forced=True, is_owner=True)])
    assert purge.rls_exposure(session, ["audit_runs"])["subject_to_rls"] == ["audit_runs"]


def test_plain_rls_blinds_a_role_that_is_not_the_owner():
    """The false negative the FORCE-only check in this package still has.

    ``relforcerowsecurity`` is about the *owner* being subject to its own policies. A
    role that is not the owner is filtered by plain ``relrowsecurity`` too, so a
    check that only looks at FORCE reports "not blinded" for exactly the kind of
    application role whose zero cannot be trusted.
    """
    session = _FakeSyncSession(catalogue=[_catalogue_row("audit_runs", enabled=True, forced=False, is_owner=False)])
    assert purge.rls_exposure(session, ["audit_runs"])["subject_to_rls"] == ["audit_runs"]

    from scripts.ops.run025.inventory_tenant_id_nulls import _rls_blinded

    assert (
        _rls_blinded(session, ["audit_runs"]) == set()
    ), "documents the gap this script closes: the FORCE-only check sees no problem here"


def test_the_owner_of_a_non_forced_rls_table_is_not_blinded():
    session = _FakeSyncSession(catalogue=[_catalogue_row("audit_runs", enabled=True, forced=False, is_owner=True)])
    assert purge.rls_exposure(session, ["audit_runs"])["subject_to_rls"] == []


def test_a_bypass_role_is_never_blinded():
    session = _FakeSyncSession(
        bypasses=True, catalogue=[_catalogue_row("audit_runs", enabled=True, forced=True, is_owner=False)]
    )
    exposure = purge.rls_exposure(session, ["audit_runs"])
    assert exposure["bypasses_rls"] is True
    assert exposure["subject_to_rls"] == []


def test_a_table_without_rls_is_never_blinded():
    session = _FakeSyncSession(
        catalogue=[_catalogue_row("external_audit_import_drafts", enabled=False, forced=False, is_owner=False)]
    )
    assert purge.rls_exposure(session, ["external_audit_import_drafts"])["subject_to_rls"] == []


def test_sqlite_has_no_row_level_security_to_reason_about():
    exposure = purge.rls_exposure(_FakeSyncSession(dialect="sqlite"), ["audit_runs"])
    assert exposure["determinable"] is False
    assert purge._blinded_on(exposure, "audit_runs") is False


# --------------------------------------------------------------------------- #
# A real database: provenance, cascades, order, and the apply guards
# --------------------------------------------------------------------------- #

# Two things about this DDL are load-bearing rather than stylistic, and both are
# quirks of SQLAlchemy's SQLite reflection, which parses the stored CREATE TABLE text
# instead of asking a catalogue:
#
# * ``ondelete`` is only recovered from a *table-level* ``FOREIGN KEY`` clause. An
#   inline ``column ... REFERENCES parent(id) ON DELETE CASCADE`` reflects with no
#   options at all, so the scan would read it as NO ACTION and the cascade tests would
#   silently exercise the wrong branch.
# * ``CONSTRAINT <name> FOREIGN KEY`` has to sit on one line for the name to be
#   recovered, hence the concatenated strings rather than a readable block. Without it
#   every constraint reflects as unnamed, and the refusal cannot tell an operator
#   which foreign key it tripped over.
#
# PostgreSQL, which is what production is, reports all of this either way.
_SCHEMA: tuple[str, ...] = (
    "CREATE TABLE users ("
    " id INTEGER PRIMARY KEY,"
    " email VARCHAR(200) NOT NULL,"
    " is_active BOOLEAN NOT NULL,"
    " tenant_id INTEGER"
    " )",
    "CREATE TABLE audit_runs ("
    " id INTEGER PRIMARY KEY,"
    " reference_number VARCHAR(50) NOT NULL UNIQUE,"
    " title VARCHAR(200),"
    " tenant_id INTEGER,"
    " created_by_id INTEGER,"
    " CONSTRAINT audit_runs_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES users(id)"
    " )",
    "CREATE TABLE audit_findings ("
    " id INTEGER PRIMARY KEY,"
    " run_id INTEGER NOT NULL,"
    " reference_number VARCHAR(50) NOT NULL UNIQUE,"
    " tenant_id INTEGER,"
    " created_by_id INTEGER,"
    " CONSTRAINT audit_findings_run_id_fkey FOREIGN KEY (run_id) REFERENCES audit_runs(id) ON DELETE CASCADE,"
    " CONSTRAINT audit_findings_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES users(id)"
    " )",
    "CREATE TABLE risks_v2 ("
    " id INTEGER PRIMARY KEY,"
    " reference VARCHAR(50) NOT NULL UNIQUE,"
    " title VARCHAR(255) NOT NULL,"
    " tenant_id INTEGER,"
    " created_by INTEGER,"
    " CONSTRAINT risks_v2_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id)"
    " )",
    # The junction row an escalation writes. CASCADE from both parents, and not itself
    # a reviewed row.
    "CREATE TABLE audit_finding_risks ("
    " id INTEGER PRIMARY KEY,"
    " audit_finding_id INTEGER NOT NULL,"
    " risk_id INTEGER NOT NULL,"
    " CONSTRAINT audit_finding_risks_finding_fkey"
    " FOREIGN KEY (audit_finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE,"
    " CONSTRAINT audit_finding_risks_risk_fkey"
    " FOREIGN KEY (risk_id) REFERENCES risks_v2(id) ON DELETE CASCADE"
    " )",
    # Real user work that cascades off an audit run: 754 of these exist in production.
    "CREATE TABLE external_audit_import_drafts ("
    " id INTEGER PRIMARY KEY,"
    " audit_run_id INTEGER NOT NULL,"
    " title VARCHAR(200) NOT NULL,"
    " tenant_id INTEGER,"
    " CONSTRAINT external_audit_import_drafts_run_fkey"
    " FOREIGN KEY (audit_run_id) REFERENCES audit_runs(id) ON DELETE CASCADE"
    " )",
    # A reference that merely blocks rather than cascading, so the third ondelete class
    # is covered too.
    "CREATE TABLE external_audit_records ("
    " id INTEGER PRIMARY KEY,"
    " audit_run_id INTEGER NOT NULL,"
    " tenant_id INTEGER,"
    " CONSTRAINT external_audit_records_run_fkey FOREIGN KEY (audit_run_id) REFERENCES audit_runs(id)"
    " )",
    "CREATE TABLE audit_questions ("
    " id INTEGER PRIMARY KEY,"
    " question_text TEXT NOT NULL,"
    " tenant_id INTEGER"
    " )",
    # Deliberately without a created_by_id, because production's audit_responses has
    # none. That absence is what forces the parent-and-marker form of provenance, so a
    # test schema that invented a creator column would test the wrong thing.
    "CREATE TABLE audit_responses ("
    " id INTEGER PRIMARY KEY,"
    " run_id INTEGER NOT NULL,"
    " question_id INTEGER NOT NULL,"
    " response_value VARCHAR(500),"
    " notes TEXT,"
    " tenant_id INTEGER,"
    " CONSTRAINT audit_responses_run_id_fkey FOREIGN KEY (run_id) REFERENCES audit_runs(id) ON DELETE CASCADE,"
    " CONSTRAINT audit_responses_question_id_fkey FOREIGN KEY (question_id) REFERENCES audit_questions(id)"
    " )",
)

_REVIEWED: tuple[ReviewedRow, ...] = REVIEWED_DEBRIS

#: Production holds 37 audit runs, ids 5 and 6 among them. Seeding only the two
#: doomed ones would make ``AUD-2026-%`` look hazardous, which is the opposite of
#: what production measures, so the 35 survivors are seeded as well.
_SURVIVING_RUN_IDS: tuple[int, ...] = tuple(range(7, 42))


class _FreshSession:
    """A session on a brand-new engine, per call.

    ``main()`` calls ``asyncio.run``, so the CLI tests execute on an event loop that
    did not exist when the fixture was built, and an engine bound to another loop
    cannot be reused across that boundary. Each ``open_session()`` therefore gets its
    own engine and disposes of it on the way out.
    """

    def __init__(self, url: str):
        self._url = url

    async def __aenter__(self) -> AsyncSession:
        self._engine = create_async_engine(self._url, poolclass=NullPool)
        self._session = AsyncSession(self._engine, expire_on_commit=False)
        return self._session

    async def __aexit__(self, *_exc: Any) -> bool:
        await self._session.close()
        await self._engine.dispose()
        return False


class _DebrisDb:
    """A real SQLite database holding the four debris rows, plus setup helpers.

    Setup and assertions go through a *synchronous* engine so one fixture serves both
    the ``await plan(...)`` tests and the ``main()`` tests, which cannot be async.
    """

    def __init__(self, path: Any):
        self.url = f"sqlite+aiosqlite:///{path}"
        self._engine = create_engine(f"sqlite:///{path}")
        with self._engine.begin() as conn:
            for statement in _SCHEMA:
                conn.execute(text(statement))

    def seed(self, **overrides: Any) -> None:
        """The four debris rows, their creator, and the surviving runs around them.

        ``overrides`` move exactly one fact, so a test can observe the refusal that
        fact is supposed to cause.
        """
        with self._engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users (id, email, is_active, tenant_id) VALUES (4, :email, :active, :tenant)"),
                {
                    "email": overrides.get("creator_email", "smoke-runner@plantexpand.com"),
                    "active": overrides.get("creator_is_active", False),
                    "tenant": overrides.get("creator_tenant_id", None),
                },
            )
            conn.execute(
                text(
                    "INSERT INTO users (id, email, is_active, tenant_id) "
                    "VALUES (5, 'david.harris@plantexpand.com', 1, 1)"
                )
            )
            for row_id in (5, 6):
                conn.execute(
                    text(
                        "INSERT INTO audit_runs (id, reference_number, title, tenant_id, created_by_id) "
                        "VALUES (:id, :ref, 'E2E Audit', :tenant, :creator)"
                    ),
                    {
                        "id": row_id,
                        "ref": f"AUD-2026-{row_id:04d}",
                        "tenant": overrides.get("run_tenant_id", None),
                        "creator": overrides.get("run_creator_id", 4),
                    },
                )
            for row_id in _SURVIVING_RUN_IDS:
                conn.execute(
                    text(
                        "INSERT INTO audit_runs (id, reference_number, title, tenant_id, created_by_id) "
                        "VALUES (:id, :ref, 'Real audit', NULL, 5)"
                    ),
                    {"id": row_id, "ref": f"AUD-2026-{row_id:04d}"},
                )
            conn.execute(
                text(
                    "INSERT INTO audit_findings (id, run_id, reference_number, tenant_id, created_by_id) "
                    "VALUES (4, 6, 'FND-2026-0001', NULL, 4)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO risks_v2 (id, reference, title, tenant_id, created_by) VALUES "
                    "(2, 'RSK-2026-0002', 'Audit escalation: AUD-2026-0006 / FND-2026-0001', NULL, 4)"
                )
            )
            conn.execute(text("INSERT INTO audit_questions (id, question_text, tenant_id) VALUES (1, 'Ok?', NULL)"))
            # One response per debris run, on the same question, both marked. Production
            # runs carry 3 to 58 responses; these carry one each, which is what a smoke
            # test asserting a single question leaves behind.
            for response_id, default_run in ((1, 5), (2, 6)):
                conn.execute(
                    text(
                        "INSERT INTO audit_responses (id, run_id, question_id, response_value, notes, tenant_id) "
                        "VALUES (:id, :run, 1, 'yes', :notes, :tenant)"
                    ),
                    {
                        "id": response_id,
                        "run": overrides.get("response_run_id", default_run),
                        "notes": overrides.get("response_notes", "E2E response"),
                        "tenant": overrides.get("response_tenant_id", None),
                    },
                )
            # A genuine answer on a surviving run, with a real note. Nothing in the
            # reviewed set reaches it, and a set that did would be refused on the marker.
            conn.execute(
                text(
                    "INSERT INTO audit_responses (id, run_id, question_id, response_value, notes, tenant_id) "
                    "VALUES (3, 7, 1, 'no', 'Observed on site, evidence photo 1', NULL)"
                )
            )

    def execute(self, statement: str, **params: Any) -> None:
        with self._engine.begin() as conn:
            conn.execute(text(statement), params)

    def count(self, table: str) -> int:
        with self._engine.begin() as conn:
            return int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)  # noqa: S608

    def dispose(self) -> None:
        self._engine.dispose()


@pytest.fixture
def debris_db(tmp_path, monkeypatch):
    """A real database with real reflected foreign keys, wired into the script."""
    db = _DebrisDb(tmp_path / "purge.db")

    async def _open_session():
        return _FreshSession(db.url)

    monkeypatch.setattr(purge, "open_session", _open_session)
    monkeypatch.setenv("DATABASE_URL", db.url)
    for marker in ("APP_ENV", "ENVIRONMENT", "QGP_ENV"):
        monkeypatch.delenv(marker, raising=False)
    try:
        yield db
    finally:
        db.dispose()


@pytest.mark.anyio
async def test_the_clean_case_plans_a_delete_with_children_first(debris_db):
    """Both ``audit_findings.run_id`` and ``audit_responses.run_id`` are CASCADE, so
    deleting the runs first would appear to work. Deleting the children first means
    each statement removes exactly the row that was reviewed, and the operation never
    depends on a cascade firing — a cascade deletes whatever happens to be attached at
    the time, which is precisely what nobody reviewed."""
    debris_db.seed()

    result = await plan(reviewed=_REVIEWED)

    assert result["blockers"] == []
    assert result["rows_present"] == 6
    order = result["deletion_order"]
    assert set(order) == {
        "audit_runs#5",
        "audit_runs#6",
        "audit_findings#4",
        "risks_v2#2",
        "audit_responses#1",
        "audit_responses#2",
    }
    assert order.index("audit_findings#4") < order.index("audit_runs#6")
    assert order.index("audit_responses#1") < order.index("audit_runs#5")
    assert order.index("audit_responses#2") < order.index("audit_runs#6")
    assert result["dependents_outside_reviewed_set"] == []
    inside = result["dependents_inside_reviewed_set"]
    assert sorted((hit["parent"], hit["child"], hit["on_delete"]) for hit in inside) == [
        ("audit_runs#5", "audit_responses#1", "CASCADE"),
        ("audit_runs#6", "audit_findings#4", "CASCADE"),
        ("audit_runs#6", "audit_responses#2", "CASCADE"),
    ]


@pytest.mark.anyio
async def test_the_genuine_response_on_a_surviving_run_is_left_alone(debris_db):
    """Nothing in the reviewed set reaches response 3, and the scan does not name it."""
    debris_db.seed()

    result = await plan(reviewed=_REVIEWED)

    touched = {hit["child"] for hit in result["dependents_inside_reviewed_set"]}
    touched |= {hit["child"] for hit in result["dependents_outside_reviewed_set"]}
    assert "audit_responses#3" not in touched
    assert "audit_responses#3" not in result["deletion_order"]


@pytest.mark.anyio
async def test_nothing_cascades_off_a_response_so_the_chain_ends_there(debris_db):
    """Checked rather than assumed: if a later migration hangs evidence or a comment
    off ``audit_responses``, the same out-of-set rule has to catch it, and the scan
    covers every reviewed table rather than only the ones that had children in July."""
    debris_db.seed()

    result = await plan(reviewed=_REVIEWED)

    assert [
        hit for hit in result["dependents_inside_reviewed_set"] if hit["parent"].startswith("audit_responses")
    ] == []
    assert [
        hit for hit in result["dependents_outside_reviewed_set"] if hit["parent"].startswith("audit_responses")
    ] == []


@pytest.mark.anyio
async def test_a_junction_row_outside_the_four_stops_the_delete(debris_db):
    """The escalation link between the finding and the risk.

    It cascades from both, and is not itself reviewed, so the reviewed set was not the
    whole story and the run stops.
    """
    debris_db.seed()
    debris_db.execute("INSERT INTO audit_finding_risks (id, audit_finding_id, risk_id) VALUES (77, 4, 2)")

    result = await plan(reviewed=_REVIEWED)

    assert any("outside the reviewed set" in blocker for blocker in result["blockers"])
    hits = result["dependents_outside_reviewed_set"]
    assert {hit["child"] for hit in hits} == {"audit_finding_risks#77"}
    # Named from both parents, because both cascades reach it.
    assert {hit["parent"] for hit in hits} == {"audit_findings#4", "risks_v2#2"}
    assert all("WOULD BE DELETED by cascade" in hit["effect"] for hit in hits)
    # Named, so the refusal says which foreign key it tripped over rather than
    # "something references this".
    assert {hit["constraint"] for hit in hits} == {
        "audit_finding_risks_finding_fkey",
        "audit_finding_risks_risk_fkey",
    }


@pytest.mark.anyio
async def test_an_import_draft_hanging_off_a_debris_run_stops_the_delete(debris_db):
    """The worst realistic outcome available here.

    ``external_audit_import_drafts.audit_run_id`` is CASCADE and those 754 drafts are
    real work by an active user, so deleting a smoke-test audit run must not be able
    to take one with it.
    """
    debris_db.seed()
    debris_db.execute(
        "INSERT INTO external_audit_import_drafts (id, audit_run_id, title, tenant_id) "
        "VALUES (900, 5, 'Imported nonconformance', NULL)"
    )

    result = await plan(reviewed=_REVIEWED)

    hits = [
        hit for hit in result["dependents_outside_reviewed_set"] if hit["child"] == "external_audit_import_drafts#900"
    ]
    assert hits, "a draft cascading off a doomed audit run must be reported"
    assert hits[0]["parent"] == "audit_runs#5"
    assert "WOULD BE DELETED by cascade" in hits[0]["effect"]
    assert any("outside the reviewed set" in blocker for blocker in result["blockers"])


@pytest.mark.anyio
async def test_a_reference_that_merely_blocks_the_delete_is_still_a_refusal(debris_db):
    """NO ACTION destroys nothing, but it aborts the operator's transaction halfway
    through. Better to say so during the dry run."""
    debris_db.seed()
    debris_db.execute("INSERT INTO external_audit_records (id, audit_run_id, tenant_id) VALUES (300, 6, NULL)")

    result = await plan(reviewed=_REVIEWED)

    hits = [hit for hit in result["dependents_outside_reviewed_set"] if hit["child"] == "external_audit_records#300"]
    assert hits
    assert hits[0]["on_delete"] == "NO ACTION"
    assert "WOULD BLOCK the delete" in hits[0]["effect"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"run_tenant_id": 1}, "now holds tenant_id=1"),
        ({"creator_is_active": True}, "is active again"),
        ({"creator_tenant_id": 1}, "This row is therefore inheritable"),
        ({"creator_email": "someone.else@plantexpand.com"}, "not 'smoke-runner@plantexpand.com'"),
        ({"run_creator_id": 5}, "not 'smoke-runner@plantexpand.com'"),
    ],
)
async def test_every_moved_precondition_refuses(debris_db, overrides, expected):
    """One fact changes and the run stops rather than deleting on trust.

    The approval was given for rows with these properties; a row without them is, as
    far as that approval goes, a different row.
    """
    debris_db.seed(**overrides)

    result = await plan(reviewed=_REVIEWED)

    assert result["blockers"], f"{overrides} should have refused"
    assert any(expected in blocker for blocker in result["blockers"]), result["blockers"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "overrides,expected",
    [
        (
            {"response_notes": "Auditor follow-up required"},
            "now has notes='Auditor follow-up required', not 'E2E response'",
        ),
        ({"response_notes": None}, "now has notes=None, not 'E2E response'"),
        ({"response_tenant_id": 1}, "audit_responses#1 now holds tenant_id=1"),
    ],
)
async def test_every_moved_response_precondition_refuses(debris_db, overrides, expected):
    """The two responses carry no account evidence of their own, so the marker and the
    parent are all there is. Each has to be re-established, not assumed."""
    debris_db.seed(**overrides)

    result = await plan(reviewed=_REVIEWED)

    assert result["blockers"], f"{overrides} should have refused"
    assert any(expected in blocker for blocker in result["blockers"]), result["blockers"]


@pytest.mark.anyio
async def test_a_response_re_parented_onto_a_genuine_run_refuses(debris_db):
    """Its whole provenance is the run it hangs off. Moved, it belongs to something
    nobody looked at, and the smoke-test marker alone is not enough to delete it."""
    debris_db.seed()
    debris_db.execute("UPDATE audit_responses SET run_id = 8 WHERE id = 1")

    result = await plan(reviewed=_REVIEWED)

    assert any("audit_responses#1 now has run_id=8, not 5" in blocker for blocker in result["blockers"]), result[
        "blockers"
    ]
    assert any("nobody has looked at" in blocker for blocker in result["blockers"])


@pytest.mark.anyio
async def test_a_genuine_runs_response_claimed_as_debris_refuses_on_both_counts(debris_db):
    """Response 3 answers a real question on a surviving run. An operator who added it
    to the list while claiming it belonged to debris run 6 is refused twice over: the
    parent is wrong and the marker is not there."""
    debris_db.seed()
    mislabelled = _REVIEWED + (
        ReviewedRow(
            table="audit_responses",
            row_id=3,
            parent_column="run_id",
            parent_table="audit_runs",
            parent_row_id=6,
            marker_column="notes",
            marker_value="E2E response",
            evidence="claimed as the debris run's response, but it is not",
        ),
    )

    result = await plan(reviewed=mislabelled)

    assert any("audit_responses#3 now has run_id=7, not 6" in blocker for blocker in result["blockers"])
    assert any(
        "now has notes='Observed on site, evidence photo 1', not 'E2E response'" in blocker
        for blocker in result["blockers"]
    )
    assert debris_db.count("audit_responses") == 3


@pytest.mark.anyio
async def test_a_reviewed_table_with_no_tenant_id_column_refuses(debris_db):
    """``AuditResponse`` does not declare ``tenant_id``, so a database built from model
    metadata — which is how the integration suite builds its schema — has no such
    column on this table.

    Without this check the row reads as tenant-less because ``dict.get`` returns None,
    and the delete's own ``tenant_id IS NULL`` guard would fail with a driver error
    mid-transaction instead of refusing during the dry run.
    """
    debris_db.seed()
    debris_db.execute("ALTER TABLE audit_responses DROP COLUMN tenant_id")

    result = await plan(reviewed=_REVIEWED)

    assert any(
        "audit_responses has no tenant_id column in this database" in blocker for blocker in result["blockers"]
    ), result["blockers"]
    assert any("AuditResponse" in blocker for blocker in result["blockers"])
    assert debris_db.count("audit_responses") == 3


@pytest.mark.anyio
async def test_a_missing_marker_column_refuses_rather_than_reading_it_as_absent(debris_db):
    debris_db.seed()
    debris_db.execute("ALTER TABLE audit_responses DROP COLUMN notes")

    result = await plan(reviewed=_REVIEWED)

    assert any(
        "audit_responses has no notes column in this database" in blocker for blocker in result["blockers"]
    ), result["blockers"]


@pytest.mark.anyio
async def test_a_missing_creator_refuses_rather_than_assuming(debris_db):
    """Provenance is the entire basis for the delete, so it cannot be skipped."""
    debris_db.seed()
    debris_db.execute("UPDATE audit_runs SET created_by_id = NULL WHERE id = 5")

    result = await plan(reviewed=_REVIEWED)

    assert any("cannot be shown to have been created by" in blocker for blocker in result["blockers"])


@pytest.mark.anyio
async def test_a_creator_row_that_cannot_be_read_refuses(debris_db):
    """On production ``users`` is under FORCE RLS and the smoke account holds no
    tenant, so an unreadable creator is exactly what an RLS-subject role would hit."""
    debris_db.seed()
    debris_db.execute("UPDATE audit_runs SET created_by_id = 999 WHERE id = 5")

    result = await plan(reviewed=_REVIEWED)

    assert any("could not be read" in blocker for blocker in result["blockers"])


@pytest.mark.anyio
async def test_a_partially_deleted_set_refuses_rather_than_finishing_the_job(debris_db):
    """The dependency graph and the arithmetic were reviewed over all four at once."""
    debris_db.seed()
    debris_db.execute("DELETE FROM risks_v2 WHERE id = 2")

    result = await plan(reviewed=_REVIEWED)

    assert any("are already gone while" in blocker for blocker in result["blockers"])
    assert result["rows_already_absent"] == ["risks_v2#2"]


@pytest.mark.anyio
async def test_all_six_absent_on_a_dialect_with_no_rls_is_a_clean_nothing_to_do(debris_db):
    debris_db.seed()
    debris_db.execute("DELETE FROM audit_findings")
    debris_db.execute("DELETE FROM risks_v2")
    debris_db.execute("DELETE FROM audit_responses WHERE id IN (1, 2)")
    debris_db.execute("DELETE FROM audit_runs WHERE id IN (5, 6)")

    result = await plan(reviewed=_REVIEWED)

    assert result["blockers"] == []
    assert result["rows_present"] == 0
    assert sorted(result["rows_already_absent"]) == [
        "audit_findings#4",
        "audit_responses#1",
        "audit_responses#2",
        "audit_runs#5",
        "audit_runs#6",
        "risks_v2#2",
    ]


@pytest.mark.anyio
async def test_the_arithmetic_is_computed_from_the_rows_actually_present(debris_db):
    """A surviving higher reference is the whole difference between hazard and safety.

    Both cases are here because both occur in the real data: ``AUD-2026-%`` has 35
    survivors above the doomed pair and is safe, while ``FND-2026-%`` has none and is
    not.
    """
    debris_db.seed()
    before = await plan(reviewed=_REVIEWED)
    by_table = {entry["table"]: entry for entry in before["reference_arithmetic"]}

    runs = by_table["audit_runs"]
    assert (runs["next_value_before"], runs["next_value_after"]) == (42, 42)
    assert runs["would_reissue_deleted_suffixes"] == []
    assert runs["verdict"].startswith("safe")

    findings = by_table["audit_findings"]
    assert (findings["next_value_before"], findings["next_value_after"]) == (2, 1)
    assert findings["would_reissue_deleted_suffixes"] == [1]

    debris_db.execute(
        "INSERT INTO audit_findings (id, run_id, reference_number, tenant_id, created_by_id) "
        "VALUES (9, 7, 'FND-2026-0009', 1, 5)"
    )
    after = await plan(reviewed=_REVIEWED)
    findings = next(e for e in after["reference_arithmetic"] if e["table"] == "audit_findings")
    assert (findings["next_value_before"], findings["next_value_after"]) == (10, 10)
    assert findings["would_reissue_deleted_suffixes"] == []
    assert findings["verdict"].startswith("safe")


# --------------------------------------------------------------------------- #
# Dry-run default, the manifest, and the CLI's own refusals
# --------------------------------------------------------------------------- #


def test_the_default_is_a_dry_run_that_writes_nothing(debris_db, capsys):
    debris_db.seed()

    exit_code = purge_main(["--json", "--accept-reference-reuse-risk"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "dry-run"
    assert payload["mode"] == "dry-run"
    assert debris_db.count("audit_runs") == 37, "a dry run must not delete anything"
    assert debris_db.count("audit_findings") == 1
    assert debris_db.count("risks_v2") == 1
    assert debris_db.count("audit_responses") == 3


def test_the_manifest_records_every_column_of_every_doomed_row(debris_db, capsys, tmp_path):
    """This file is the change record, because the deletion cannot go into the
    per-tenant hash-chained trail without inventing the tenant under review."""
    debris_db.seed()
    manifest = tmp_path / "manifest.json"

    purge_main(["--json", "--accept-reference-reuse-risk", "--manifest", str(manifest)])
    capsys.readouterr()

    recorded = json.loads(manifest.read_text(encoding="utf-8"))
    assert recorded["deletion_order"]
    assert set(recorded["rows"]) == {"audit_runs", "audit_findings", "risks_v2", "audit_responses"}
    assert {row["id"] for row in recorded["rows"]["audit_runs"]} == {5, 6}
    assert {row["id"] for row in recorded["rows"]["audit_responses"]} == {1, 2}
    # Whole rows, not a projection: this has to be enough to reconstruct from.
    assert set(recorded["rows"]["audit_findings"][0]) == {
        "id",
        "run_id",
        "reference_number",
        "tenant_id",
        "created_by_id",
    }
    assert set(recorded["rows"]["risks_v2"][0]) == {"id", "reference", "title", "tenant_id", "created_by"}
    # Captured from SELECT *, so tenant_id is recorded whether or not the model
    # declares it — and AuditResponse does not declare it.
    assert set(recorded["rows"]["audit_responses"][0]) == {
        "id",
        "run_id",
        "question_id",
        "response_value",
        "notes",
        "tenant_id",
    }
    # The provenance each delete rests on, captured alongside the rows.
    assert recorded["creators"]["audit_runs#5"]["email"] == "smoke-runner@plantexpand.com"
    # No creator entry for a response, because the table records none. The verification
    # record says so rather than leaving a reader to wonder whether it was skipped.
    assert "audit_responses#1" not in recorded["creators"]
    response_record = next(
        entry for entry in recorded["row_verification"] if entry["table"] == "audit_responses" and entry["id"] == 1
    )
    assert response_record["creator_column"] is None
    assert "no creator column" in response_record["provenance"]
    assert response_record["expected_parent"] == "audit_runs#5"
    assert response_record["marker"] == "E2E response"
    assert recorded["reference_arithmetic"]
    assert recorded["row_verification"]
    assert "audit_log_entries" in recorded["note"]


def test_a_manifest_is_written_even_when_the_run_refuses(debris_db, capsys, tmp_path):
    """The evidence behind a refusal is worth keeping too."""
    debris_db.seed()
    debris_db.execute("INSERT INTO audit_finding_risks (id, audit_finding_id, risk_id) VALUES (77, 4, 2)")
    manifest = tmp_path / "refused.json"

    assert purge_main(["--json", "--manifest", str(manifest)]) == 3
    capsys.readouterr()

    recorded = json.loads(manifest.read_text(encoding="utf-8"))
    assert recorded["blockers"]
    assert recorded["dependents_outside_reviewed_set"]


def test_the_reference_reuse_blocker_reports_the_sum_and_can_be_accepted(debris_db, capsys):
    debris_db.seed()

    assert purge_main(["--json"]) == 3
    refused = json.loads(capsys.readouterr().out)
    reuse_blockers = [blocker for blocker in refused["blockers"] if "moves the next" in blocker]
    assert len(reuse_blockers) == 2, "the finding and the risk each free their pattern's top number"
    joined = " ".join(reuse_blockers)
    assert "before: max(max_seq=1 (from 'FND-2026-0001'), count=1) + 1 = 2" in joined
    assert "--accept-reference-reuse-risk" in joined
    assert debris_db.count("audit_findings") == 1

    assert purge_main(["--json", "--accept-reference-reuse-risk"]) == 1
    accepted = json.loads(capsys.readouterr().out)
    assert accepted["outcome"] == "dry-run"


def test_a_tenant_filter_is_refused_because_every_reviewed_row_has_no_tenant(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user@localhost/whatever")
    assert purge_main(["--tenant-id", "1"]) == 2


def test_apply_on_production_without_the_acknowledgement_aborts(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user@localhost/whatever")
    with pytest.raises(SystemExit) as excinfo:
        purge_main(["--apply"])
    assert excinfo.value.code == 2


def test_apply_without_a_manifest_refuses_and_deletes_nothing(debris_db, capsys):
    debris_db.seed()

    assert purge_main(["--json", "--accept-reference-reuse-risk", "--apply"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "refused"
    assert debris_db.count("audit_runs") == 37


def test_apply_deletes_exactly_the_six_and_is_then_idempotent(debris_db, capsys, tmp_path):
    debris_db.seed()
    manifest = tmp_path / "applied.json"

    assert purge_main(["--json", "--accept-reference-reuse-risk", "--apply", "--manifest", str(manifest)]) == 0
    applied = json.loads(capsys.readouterr().out)
    assert applied["outcome"] == "applied"
    assert applied["deleted"] == {"audit_findings": 1, "audit_responses": 2, "audit_runs": 2, "risks_v2": 1}

    assert debris_db.count("audit_runs") == 35, "the 35 real runs are untouched"
    assert debris_db.count("audit_findings") == 0
    assert debris_db.count("risks_v2") == 0
    assert debris_db.count("audit_responses") == 1, "the genuine response on a surviving run remains"
    assert debris_db.count("audit_questions") == 1, "the question both answers pointed at is not debris"
    # Accounts are untouched: this purge deletes records, not users.
    assert debris_db.count("users") == 2

    assert purge_main(["--json"]) == 0
    again = json.loads(capsys.readouterr().out)
    assert again["outcome"] == "nothing-to-do"


def test_a_blocked_run_deletes_nothing_even_with_apply_and_a_manifest(debris_db, capsys, tmp_path):
    """The blockers are checked before the apply path, not alongside it."""
    debris_db.seed()
    debris_db.execute("INSERT INTO audit_finding_risks (id, audit_finding_id, risk_id) VALUES (77, 4, 2)")

    assert (
        purge_main(["--json", "--accept-reference-reuse-risk", "--apply", "--manifest", str(tmp_path / "m.json")]) == 3
    )
    capsys.readouterr()
    assert debris_db.count("audit_runs") == 37
    assert debris_db.count("audit_finding_risks") == 1


# --------------------------------------------------------------------------- #
# The apply transaction's own guards
# --------------------------------------------------------------------------- #

_ORDER: list[tuple[str, int]] = [
    ("audit_findings", 4),
    ("audit_responses", 1),
    ("audit_responses", 2),
    ("risks_v2", 2),
    ("audit_runs", 5),
    ("audit_runs", 6),
]


@pytest.mark.anyio
async def test_apply_rolls_back_when_a_precondition_moved_since_the_plan(debris_db):
    """The window between planning and applying is real, and a change committed
    inside it must not be written over."""
    debris_db.seed()
    debris_db.execute("UPDATE users SET is_active = 1 WHERE id = 4")

    with pytest.raises(PreconditionDrifted, match="is active again"):
        await apply_plan(_ORDER, reviewed=_REVIEWED)

    assert debris_db.count("audit_runs") == 37
    assert debris_db.count("audit_findings") == 1


@pytest.mark.anyio
async def test_apply_rolls_back_when_a_row_was_attributed_since_the_plan(debris_db):
    debris_db.seed()
    debris_db.execute("UPDATE audit_runs SET tenant_id = 1 WHERE id = 5")

    with pytest.raises(PreconditionDrifted, match="now holds tenant_id"):
        await apply_plan(_ORDER, reviewed=_REVIEWED)

    assert debris_db.count("audit_runs") == 37


@pytest.mark.anyio
async def test_apply_rolls_back_when_a_row_vanished_since_the_plan(debris_db):
    """What a concurrent second copy of this script looks like from the loser's side."""
    debris_db.seed()
    debris_db.execute("DELETE FROM audit_findings WHERE id = 4")

    with pytest.raises(PreconditionDrifted, match="no longer there"):
        await apply_plan(_ORDER, reviewed=_REVIEWED)

    assert debris_db.count("audit_runs") == 37
    assert debris_db.count("risks_v2") == 1


@pytest.mark.anyio
async def test_apply_refuses_a_key_that_is_not_in_the_reviewed_set(debris_db):
    """Belt and braces on the one thing that must never happen."""
    debris_db.seed()

    with pytest.raises(PreconditionDrifted, match="nobody approved"):
        await apply_plan([("audit_runs", 99)], reviewed=_REVIEWED)

    assert debris_db.count("audit_runs") == 37


class _ZeroRowDelete:
    """A database where the DELETE matches nothing, as row-level security makes it.

    This is the failure that must not read as success: PostgreSQL reports no error for
    a delete filtered to zero rows by a policy, so without a rowcount check the run
    would report "applied" having removed nothing at all.
    """

    def __init__(self) -> None:
        self.rolled_back = False
        self.committed = False

    async def run_sync(self, fn, *args):
        # Both reflection and the RLS probe are answered from this one dict; the RLS
        # keys are absent, which _blinded_on treats as "nothing determinable".
        if args:
            return {
                "audit_runs": {"exists": True, "columns": {"id", "tenant_id", "created_by_id"}},
                "users": {"exists": True, "columns": {"id", "email", "is_active", "tenant_id"}},
            }
        return "postgresql"

    async def execute(self, statement, params=None):
        sql = str(statement)
        if sql.strip().upper().startswith("DELETE"):
            return _RowCount(0)
        if " FROM users " in sql:
            return _One({"id": 4, "email": "smoke-runner@plantexpand.com", "is_active": False, "tenant_id": None})
        return _One({"id": 5, "tenant_id": None, "created_by_id": 4})

    async def rollback(self) -> None:
        self.rolled_back = True

    async def commit(self) -> None:
        self.committed = True


class _RowCount:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount


class _One:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def one_or_none(self):
        return self._row


@pytest.mark.anyio
async def test_a_delete_that_removes_no_rows_is_a_failure_not_a_no_op(monkeypatch):
    db = _ZeroRowDelete()

    async def _open_session():
        class _Ctx:
            async def __aenter__(self):
                return db

            async def __aexit__(self, *_exc):
                return False

        return _Ctx()

    monkeypatch.setattr(purge, "open_session", _open_session)

    with pytest.raises(PreconditionDrifted, match="removed 0 row"):
        await apply_plan([("audit_runs", 5)], reviewed=_REVIEWED)

    assert db.rolled_back is True
    assert db.committed is False


# --------------------------------------------------------------------------- #
# Helper behaviour that would otherwise only surface in production
# --------------------------------------------------------------------------- #


def test_a_child_table_with_no_single_column_key_is_reported_not_crashed_through(monkeypatch):
    """``dependent_ids`` used to hardcode ``id``.

    Every table in this schema has one today, but a composite-keyed junction added
    later would have raised ``UndefinedColumn`` from inside the dependency scan, which
    reads like a broken script rather than the "I cannot check this table" it is.
    """
    import scripts.ops.run025._dependencies as dependencies

    class _Insp:
        def get_table_names(self):
            return ["composite", "simple"]

        def get_pk_constraint(self, table):
            return {"constrained_columns": ["a", "b"] if table == "composite" else ["id"]}

    class _Session:
        def get_bind(self):
            return object()

    monkeypatch.setattr(dependencies.sa, "inspect", lambda _bind: _Insp())
    keys = dependencies.single_column_primary_keys(_Session(), ["composite", "simple", "absent"])

    assert keys == {"composite": None, "simple": "id", "absent": None}


def test_the_pattern_year_is_taken_from_the_clock_the_service_uses():
    """``generate()`` builds its pattern from ``datetime.now().year``, so a hardcoded
    year in a check would quietly stop meaning anything on 1 January."""
    entry = _arithmetic(pattern=f"FND-{datetime.now().year}-%")
    assert entry.pattern_year_is_current is True
