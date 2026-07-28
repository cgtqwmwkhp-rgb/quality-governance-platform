"""What an application role sees of the six debris rows, against real PostgreSQL RLS.

Why this cannot be a unit test
------------------------------
Row-level security does not exist in SQLite, and it is the most dangerous thing about
this purge. ``audit_runs``, ``audit_findings``, ``risks_v2`` and ``users`` are all
under ``FORCE ROW LEVEL SECURITY`` in production, with a ``tenant_isolation`` policy
of::

    USING (tenant_id = current_setting('app.current_tenant_id', true)::int)

For a row whose ``tenant_id`` is NULL that predicate evaluates to NULL, never to true
— so a role subject to the policy sees *none* of the rows this script exists to
delete, whatever tenant it sets. Two consequences, both silent:

* ``SELECT`` returns nothing, which reads exactly like "already deleted".
* ``DELETE`` removes nothing and raises no error, so a run could report success having
  destroyed nothing and left the migration still blocked.

Task 5 was to establish what an application role actually sees rather than to accept
that a bypass role saw everything, so both roles are exercised here against the same
rows.

``audit_responses`` is the interesting exception and is reproduced as the exception it
is. Measured on a database built by the full alembic chain, ``audit_runs``,
``audit_findings``, ``risks_v2`` and ``users`` all have ``relrowsecurity`` and
``relforcerowsecurity`` true with one ``tenant_isolation`` policy each, while
``audit_responses``, ``audit_questions`` and ``audit_sections`` have neither and no
policy at all — they carry a ``tenant_id`` that nothing enforces. So an application
role sees the two reviewed responses perfectly well while being blind to the four rows
around them, which is a worse starting position than being blind to all six: two thirds
of the set looks already-deleted and the visible third looks ready to delete. The
refusal has to come from the four it cannot see, and
:func:`test_an_app_role_sees_the_responses_but_not_their_parents_and_still_refuses`
is that case.

Why a private schema and ``SET ROLE``
-------------------------------------
The integration database is shared with every other test in the job, and its schema
comes from ``Base.metadata.create_all``, which creates no policies at all — enabling
RLS on the real ``public`` tables would change what every other test can see. So this
builds production's RLS configuration in a schema of its own, and changes identity
with ``SET ROLE`` rather than a second login: a superuser that has ``SET ROLE``d to a
non-bypass role *is* subject to RLS, which is precisely the condition under test, and
it needs no password or ``pg_hba`` cooperation.

Everything created here is dropped in teardown, including on failure.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from scripts.ops.run025 import purge_reviewed_debris_rows as purge
from scripts.ops.run025.purge_reviewed_debris_rows import PreconditionDrifted, ReviewedRow, apply_plan, plan

SMOKE_EMAIL = "smoke-runner@plantexpand.com"

#: The marker the smoke test wrote into ``audit_responses.notes``.
RESPONSE_MARKER = "E2E response"

#: The production policy, copied from ``20260222_add_row_level_security`` and
#: ``20260719_rls_gt_exp``. Reproduced verbatim rather than approximated, because the
#: whole question is how it treats a NULL ``tenant_id``.
POLICY_PREDICATE = "tenant_id = current_setting('app.current_tenant_id', true)::int"

#: The tables this purge touches that are under FORCE RLS in production. ``users`` is
#: included because provenance is re-verified through it and it is under FORCE RLS
#: there too: a role that can see an audit run but not the account that created it
#: still cannot establish that the row is debris.
#:
#: ``audit_responses`` and ``audit_questions`` are deliberately *not* here. Neither has
#: RLS enabled in production and neither has a policy, so putting them under one would
#: make this fixture prove something production does not do.
RLS_TABLES: tuple[str, ...] = ("users", "audit_runs", "audit_findings", "risks_v2")

#: Reviewed tables with a ``tenant_id`` and nothing enforcing it.
UNPROTECTED_TABLES: tuple[str, ...] = ("audit_responses", "audit_questions")

_DDL: tuple[str, ...] = (
    "CREATE TABLE users ("
    " id SERIAL PRIMARY KEY,"
    " email VARCHAR(200) NOT NULL UNIQUE,"
    " is_active BOOLEAN NOT NULL DEFAULT true,"
    " tenant_id INTEGER"
    " )",
    "CREATE TABLE audit_runs ("
    " id SERIAL PRIMARY KEY,"
    " reference_number VARCHAR(50) NOT NULL UNIQUE,"
    " title VARCHAR(200),"
    " tenant_id INTEGER,"
    " created_by_id INTEGER,"
    " CONSTRAINT audit_runs_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES users(id)"
    " )",
    "CREATE TABLE audit_findings ("
    " id SERIAL PRIMARY KEY,"
    " run_id INTEGER NOT NULL,"
    " reference_number VARCHAR(50) NOT NULL UNIQUE,"
    " tenant_id INTEGER,"
    " created_by_id INTEGER,"
    " CONSTRAINT audit_findings_run_id_fkey FOREIGN KEY (run_id) REFERENCES audit_runs(id) ON DELETE CASCADE,"
    " CONSTRAINT audit_findings_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES users(id)"
    " )",
    "CREATE TABLE risks_v2 ("
    " id SERIAL PRIMARY KEY,"
    " reference VARCHAR(50) NOT NULL UNIQUE,"
    " title VARCHAR(255) NOT NULL,"
    " tenant_id INTEGER,"
    " created_by INTEGER,"
    " CONSTRAINT risks_v2_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(id)"
    " )",
    "CREATE TABLE audit_finding_risks ("
    " id SERIAL PRIMARY KEY,"
    " audit_finding_id INTEGER NOT NULL,"
    " risk_id INTEGER NOT NULL,"
    " CONSTRAINT audit_finding_risks_finding_fkey"
    " FOREIGN KEY (audit_finding_id) REFERENCES audit_findings(id) ON DELETE CASCADE,"
    " CONSTRAINT audit_finding_risks_risk_fkey"
    " FOREIGN KEY (risk_id) REFERENCES risks_v2(id) ON DELETE CASCADE"
    " )",
    "CREATE TABLE audit_questions ("
    " id SERIAL PRIMARY KEY,"
    " question_text TEXT NOT NULL,"
    " tenant_id INTEGER"
    " )",
    # No created_by_id, as production has none. That is what makes the parent run and
    # the notes marker the only provenance available for these two rows.
    "CREATE TABLE audit_responses ("
    " id SERIAL PRIMARY KEY,"
    " run_id INTEGER NOT NULL,"
    " question_id INTEGER NOT NULL,"
    " response_value VARCHAR(500),"
    " notes TEXT,"
    " tenant_id INTEGER,"
    " CONSTRAINT audit_responses_run_id_fkey FOREIGN KEY (run_id) REFERENCES audit_runs(id) ON DELETE CASCADE,"
    " CONSTRAINT audit_responses_question_id_fkey FOREIGN KEY (question_id) REFERENCES audit_questions(id)"
    " )",
)


class _ProbeSession:
    """A session on the probe schema, optionally wearing the application role.

    A new session per call, so ``SET ROLE`` cannot leak into a connection a later
    assertion reuses as superuser.
    """

    def __init__(self, engine: Any, role: Optional[str], tenant: Optional[int] = None):
        self._engine = engine
        self._role = role
        self._tenant = tenant

    async def __aenter__(self) -> AsyncSession:
        self._session = AsyncSession(self._engine, expire_on_commit=False)
        if self._tenant is not None:
            await self._session.execute(
                sa.text("SELECT set_config('app.current_tenant_id', :tenant, false)"),
                {"tenant": str(self._tenant)},
            )
        if self._role is not None:
            await self._session.execute(sa.text(f"SET ROLE {self._role}"))
        return self._session

    async def __aexit__(self, *_exc: Any) -> bool:
        try:
            if self._role is not None:
                # Best effort: after a rollback the connection may already be clean,
                # and a failure here must not mask the test's own outcome.
                try:
                    await self._session.execute(sa.text("RESET ROLE"))
                except Exception:  # noqa: BLE001
                    pass
        finally:
            await self._session.close()
        return False


class _Probe:
    """A private schema holding the six debris rows under production's RLS."""

    def __init__(self, engine: Any, schema: str, role: str):
        self._engine = engine
        self.schema = schema
        self.role = role
        self.run_ids: tuple[int, ...] = ()
        self.finding_id = 0
        self.risk_id = 0
        self.response_ids: tuple[int, ...] = ()

    @property
    def reviewed(self) -> tuple[ReviewedRow, ...]:
        return (
            ReviewedRow(
                table="audit_runs",
                row_id=self.run_ids[0],
                creator_column="created_by_id",
                creator_email=SMOKE_EMAIL,
                evidence="E2E smoke audit run",
            ),
            ReviewedRow(
                table="audit_runs",
                row_id=self.run_ids[1],
                creator_column="created_by_id",
                creator_email=SMOKE_EMAIL,
                evidence="E2E smoke audit run",
            ),
            ReviewedRow(
                table="audit_findings",
                row_id=self.finding_id,
                creator_column="created_by_id",
                creator_email=SMOKE_EMAIL,
                evidence="finding raised inside that run",
            ),
            ReviewedRow(
                table="risks_v2",
                row_id=self.risk_id,
                creator_column="created_by",
                creator_email=SMOKE_EMAIL,
                evidence="escalation of that finding",
            ),
            ReviewedRow(
                table="audit_responses",
                row_id=self.response_ids[0],
                parent_column="run_id",
                parent_table="audit_runs",
                parent_row_id=self.run_ids[0],
                marker_column="notes",
                marker_value=RESPONSE_MARKER,
                evidence="sole response of the first smoke run",
            ),
            ReviewedRow(
                table="audit_responses",
                row_id=self.response_ids[1],
                parent_column="run_id",
                parent_table="audit_runs",
                parent_row_id=self.run_ids[1],
                marker_column="notes",
                marker_value=RESPONSE_MARKER,
                evidence="sole response of the second smoke run",
            ),
        )

    def session(self, *, as_app_role: bool, tenant: Optional[int] = None) -> _ProbeSession:
        return _ProbeSession(self._engine, self.role if as_app_role else None, tenant)

    async def rows_visible(self, *, as_app_role: bool, tenant: Optional[int] = None) -> dict[str, int]:
        """How many of the six reviewed rows each table yields to this role."""
        wanted = {
            "audit_runs": list(self.run_ids),
            "audit_findings": [self.finding_id],
            "risks_v2": [self.risk_id],
            "audit_responses": list(self.response_ids),
        }
        counts: dict[str, int] = {}
        async with self.session(as_app_role=as_app_role, tenant=tenant) as db:
            for table, ids in wanted.items():
                counts[table] = int(
                    (
                        await db.execute(
                            sa.text(f"SELECT COUNT(*) FROM {table} WHERE id = ANY(:ids)"),  # noqa: S608
                            {"ids": ids},
                        )
                    ).scalar()
                    or 0
                )
        return counts


ALL_SIX_VISIBLE = {"audit_runs": 2, "audit_findings": 1, "risks_v2": 1, "audit_responses": 2}

#: What an application role sees. The four protected rows disappear; the two responses
#: do not, because nothing enforces their tenant column.
ONLY_THE_RESPONSES_VISIBLE = {"audit_runs": 0, "audit_findings": 0, "risks_v2": 0, "audit_responses": 2}


def _database_url() -> str:
    return os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI") or ""


@pytest.fixture
async def probe():
    url = _database_url()
    if "postgresql" not in url:
        pytest.skip(
            "row-level security is a PostgreSQL feature; this needs a postgresql DATABASE_URL, "
            f"which CI supplies, rather than {url.split('://')[0] or '(unset)'}"
        )

    suffix = os.getpid()
    schema = f"run025_rls_probe_{suffix}"
    role = f"run025_app_probe_{suffix}"

    # search_path is a connection parameter rather than a statement so the dialect
    # resolves its default schema to the probe schema on first connect. A later SET
    # would leave the inspector reflecting public, and every reflection in the script
    # would describe the wrong tables.
    engine = create_async_engine(url, poolclass=NullPool, connect_args={"server_settings": {"search_path": schema}})
    admin = create_async_engine(url, poolclass=NullPool, isolation_level="AUTOCOMMIT")

    async with admin.connect() as conn:
        await conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await conn.execute(sa.text(f"CREATE SCHEMA {schema}"))
        await conn.execute(sa.text(f"SET search_path TO {schema}"))
        for statement in _DDL:
            await conn.execute(sa.text(statement))
        for table in RLS_TABLES:
            await conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            await conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
            await conn.execute(sa.text(f"CREATE POLICY tenant_isolation ON {table} USING ({POLICY_PREDICATE})"))
        await conn.execute(sa.text(f"DROP ROLE IF EXISTS {role}"))
        # NOBYPASSRLS is the property under test. NOLOGIN because identity is taken
        # with SET ROLE, so no credential for this role ever exists.
        await conn.execute(sa.text(f"CREATE ROLE {role} NOLOGIN NOBYPASSRLS"))
        await conn.execute(sa.text(f"GRANT USAGE ON SCHEMA {schema} TO {role}"))
        await conn.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO {role}"))

    fixture = _Probe(engine, schema, role)

    async with fixture.session(as_app_role=False) as db:
        smoke_id = (
            await db.execute(
                sa.text("INSERT INTO users (email, is_active, tenant_id) VALUES (:email, false, NULL) RETURNING id"),
                {"email": SMOKE_EMAIL},
            )
        ).scalar()
        run_ids = []
        for offset in range(2):
            run_ids.append(
                (
                    await db.execute(
                        sa.text(
                            "INSERT INTO audit_runs (reference_number, title, tenant_id, created_by_id) "
                            "VALUES (:ref, 'E2E Audit', NULL, :creator) RETURNING id"
                        ),
                        {"ref": f"AUD-2026-{5 + offset:04d}", "creator": smoke_id},
                    )
                ).scalar()
            )
        fixture.run_ids = tuple(run_ids)
        fixture.finding_id = (
            await db.execute(
                sa.text(
                    "INSERT INTO audit_findings (run_id, reference_number, tenant_id, created_by_id) "
                    "VALUES (:run_id, 'FND-2026-0001', NULL, :creator) RETURNING id"
                ),
                {"run_id": fixture.run_ids[1], "creator": smoke_id},
            )
        ).scalar()
        fixture.risk_id = (
            await db.execute(
                sa.text(
                    "INSERT INTO risks_v2 (reference, title, tenant_id, created_by) "
                    "VALUES ('RSK-2026-0002', :title, NULL, :creator) RETURNING id"
                ),
                {"title": "Audit escalation: AUD-2026-0006 / FND-2026-0001", "creator": smoke_id},
            )
        ).scalar()
        question_id = (
            await db.execute(
                sa.text("INSERT INTO audit_questions (question_text, tenant_id) VALUES ('Ok?', NULL) RETURNING id")
            )
        ).scalar()
        fixture.response_ids = tuple(
            [
                (
                    await db.execute(
                        sa.text(
                            "INSERT INTO audit_responses (run_id, question_id, response_value, notes, tenant_id) "
                            "VALUES (:run_id, :question_id, 'yes', :notes, NULL) RETURNING id"
                        ),
                        {"run_id": run_id, "question_id": question_id, "notes": RESPONSE_MARKER},
                    )
                ).scalar()
                for run_id in fixture.run_ids
            ]
        )
        await db.commit()

    try:
        yield fixture
    finally:
        await engine.dispose()
        async with admin.connect() as conn:
            await conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            await conn.execute(sa.text(f"DROP OWNED BY {role} CASCADE"))
            await conn.execute(sa.text(f"DROP ROLE IF EXISTS {role}"))
        await admin.dispose()


def _run_scripts_as(probe: _Probe, monkeypatch, *, app_role: bool, tenant: Optional[int] = None) -> None:
    """Point the script's session factory at the probe, wearing the chosen role."""

    async def _open_session():
        return probe.session(as_app_role=app_role, tenant=tenant)

    monkeypatch.setattr(purge, "open_session", _open_session)


# --------------------------------------------------------------------------- #
# What each role can see
# --------------------------------------------------------------------------- #


async def test_a_bypass_role_sees_all_six_rows_and_an_app_role_sees_only_the_responses(probe):
    """The measured difference, on the same six rows, in one test.

    This is the answer to "``tables_hidden_by_rls`` came back empty for my
    connection": it was empty because that connection bypasses RLS, and that says
    nothing at all about an application role.

    The two responses stay visible because nothing protects them, which is worse than
    total blindness rather than better — see the module docstring.
    """
    assert await probe.rows_visible(as_app_role=False) == ALL_SIX_VISIBLE
    assert await probe.rows_visible(as_app_role=True) == ONLY_THE_RESPONSES_VISIBLE


async def test_the_reviewed_response_table_has_no_policy_protecting_it(probe):
    """Reproduced from production rather than assumed, and asserted so that a future
    migration adding a policy here shows up as a changed fact rather than as a test
    that quietly starts proving something else."""
    async with probe.session(as_app_role=False) as db:
        rows = (
            await db.execute(
                sa.text(
                    "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
                    "(SELECT count(*) FROM pg_policies p WHERE p.schemaname = :schema "
                    " AND p.tablename = c.relname) AS policies "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = :schema AND c.relname = ANY(:tables)"
                ),
                {"schema": probe.schema, "tables": list(UNPROTECTED_TABLES)},
            )
        ).all()

    assert {row[0] for row in rows} == set(UNPROTECTED_TABLES)
    assert all((row[1], row[2], row[3]) == (False, False, 0) for row in rows), rows


async def test_no_tenant_setting_reveals_a_protected_row_that_has_no_tenant(probe):
    """There is no value of ``app.current_tenant_id`` that helps.

    ``NULL = 1`` is NULL, not true, so the policy filters these rows for every tenant.
    An operator cannot work around the blindness by setting the session variable, which
    is why the refusal names ``rolsuper``/``rolbypassrls`` specifically.
    """
    for tenant in (1, 2, 99):
        assert (
            await probe.rows_visible(as_app_role=True, tenant=tenant) == ONLY_THE_RESPONSES_VISIBLE
        ), f"tenant {tenant} should reveal nothing that is under a policy"


async def test_rls_exposure_classifies_the_two_roles_differently(probe):
    """The classification every refusal below rests on, against real catalogues."""
    async with probe.session(as_app_role=False) as db:
        bypass = await db.run_sync(purge.rls_exposure, list(RLS_TABLES))
    assert bypass["bypasses_rls"] is True
    assert bypass["subject_to_rls"] == []

    async with probe.session(as_app_role=True) as db:
        app = await db.run_sync(purge.rls_exposure, list(RLS_TABLES))
    assert app["role"] == probe.role
    assert app["bypasses_rls"] is False
    assert sorted(app["subject_to_rls"]) == sorted(RLS_TABLES)
    assert app["per_table"]["audit_runs"]["rls_forced"] is True
    assert app["per_table"]["audit_runs"]["role_has_owner_privileges"] is False


# --------------------------------------------------------------------------- #
# What the script does about it
# --------------------------------------------------------------------------- #


async def test_a_bypass_role_plans_the_delete_cleanly(probe, monkeypatch):
    """The control. Without it, the refusal below could just be a broken fixture."""
    _run_scripts_as(probe, monkeypatch, app_role=False)

    result = await plan(reviewed=probe.reviewed)

    assert result["blockers"] == []
    assert result["rows_present"] == 6
    assert result["row_level_security"]["bypasses_rls"] is True
    order = result["deletion_order"]
    for index, run_id in enumerate(probe.run_ids):
        assert order.index(f"audit_responses#{probe.response_ids[index]}") < order.index(f"audit_runs#{run_id}")


async def test_an_app_role_sees_the_responses_but_not_their_parents_and_still_refuses(probe, monkeypatch):
    """The worst outcome available here, and the one that must not happen.

    An application role reads two of the six rows and nothing of the other four. Left
    to itself that is a coherent-looking story — "the runs, the finding and the risk
    have already been purged, here are the two leftover responses" — and a script that
    believed it would delete two rows, report success, and leave the four rows the
    migration is actually blocked on exactly where they were.

    So the four unreadable rows are refusals rather than absences, and the two readable
    ones do not soften that: the set was reviewed whole.
    """
    _run_scripts_as(probe, monkeypatch, app_role=True)

    result = await plan(reviewed=probe.reviewed)

    assert result["rows_present"] == 2, "only the two unprotected responses are readable"
    assert result["rows_already_absent"] == [], "absence must not be recorded as absence when it cannot be trusted"
    hidden = [blocker for blocker in result["blockers"] if "absence cannot be distinguished" in blocker]
    assert len(hidden) == 4
    assert all("rolsuper or rolbypassrls" in blocker for blocker in hidden)
    assert sorted(result["row_level_security"]["subject_to_rls"]) == sorted(RLS_TABLES)
    # The responses themselves verified cleanly, which is exactly why the refusal has
    # to come from elsewhere.
    responses = [entry for entry in result["row_verification"] if entry["table"] == "audit_responses"]
    assert len(responses) == 2
    assert all(entry["problems"] == [] for entry in responses), responses


async def test_the_delete_an_app_role_issues_removes_nothing_and_says_nothing(probe):
    """Why absence has to be a refusal rather than a warning.

    PostgreSQL raises no error for a DELETE its policy filters to zero rows. This is
    the raw behaviour the ``rowcount != 1`` guard in ``apply_plan`` exists to catch.
    """
    async with probe.session(as_app_role=True) as db:
        result = await db.execute(
            sa.text("DELETE FROM audit_runs WHERE id = :row_id AND tenant_id IS NULL"),
            {"row_id": probe.run_ids[0]},
        )
        assert result.rowcount == 0
        await db.commit()

    assert (
        await probe.rows_visible(as_app_role=False) == ALL_SIX_VISIBLE
    ), "the row is still there; the delete simply did nothing"


async def test_apply_as_an_app_role_rolls_back_rather_than_reporting_success(probe, monkeypatch):
    """Belt and braces: even handed a plan, the apply path re-checks and refuses."""
    _run_scripts_as(probe, monkeypatch, app_role=True)

    with pytest.raises(PreconditionDrifted, match="row-level security"):
        await apply_plan([("audit_runs", probe.run_ids[0])], reviewed=probe.reviewed)

    assert await probe.rows_visible(as_app_role=False) == ALL_SIX_VISIBLE


async def test_an_app_role_that_can_see_a_run_but_not_its_creator_still_refuses(probe, monkeypatch):
    """The partial-sight case, which is the subtle one.

    Attribute one audit run to tenant 1 and an app role on tenant 1 can see it. But
    ``users`` is under the same policy and the smoke account holds no tenant, so the
    account that proves the row is debris stays invisible. Provenance is the entire
    basis for the delete, so a row that can be *seen* but not *attributed* is still a
    refusal — and for a different reason than blindness to the row itself.
    """
    async with probe.session(as_app_role=False) as db:
        await db.execute(
            sa.text("UPDATE audit_runs SET tenant_id = 1 WHERE id = :row_id"), {"row_id": probe.run_ids[0]}
        )
        await db.commit()

    assert await probe.rows_visible(as_app_role=True, tenant=1) == {**ONLY_THE_RESPONSES_VISIBLE, "audit_runs": 1}

    _run_scripts_as(probe, monkeypatch, app_role=True, tenant=1)
    result = await plan(reviewed=probe.reviewed)

    problems = [
        entry["problems"]
        for entry in result["row_verification"]
        if entry["table"] == "audit_runs" and entry["id"] == probe.run_ids[0]
    ][0]
    # Attributed, which is itself outside what was reviewed...
    assert any("now holds tenant_id" in problem for problem in problems)
    # ...and its creator is unreadable, which is the point of this test.
    assert any("could not be read" in problem for problem in problems)
    assert any("smoke-runner account holds" in problem for problem in problems)
    assert result["blockers"]
