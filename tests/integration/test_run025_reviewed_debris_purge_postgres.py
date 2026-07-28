"""What an application role sees of the four debris rows, against real PostgreSQL RLS.

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

#: The production policy, copied from ``20260222_add_row_level_security`` and
#: ``20260719_rls_gt_exp``. Reproduced verbatim rather than approximated, because the
#: whole question is how it treats a NULL ``tenant_id``.
POLICY_PREDICATE = "tenant_id = current_setting('app.current_tenant_id', true)::int"

#: Only the tables this purge reads or writes. ``users`` is included because
#: provenance is re-verified through it and it is under FORCE RLS in production too: a
#: role that can see an audit run but not the account that created it still cannot
#: establish that the row is debris.
RLS_TABLES: tuple[str, ...] = ("users", "audit_runs", "audit_findings", "risks_v2")

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
    """A private schema holding the four debris rows under production's RLS."""

    def __init__(self, engine: Any, schema: str, role: str):
        self._engine = engine
        self.schema = schema
        self.role = role
        self.run_ids: tuple[int, ...] = ()
        self.finding_id = 0
        self.risk_id = 0

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
        )

    def session(self, *, as_app_role: bool, tenant: Optional[int] = None) -> _ProbeSession:
        return _ProbeSession(self._engine, self.role if as_app_role else None, tenant)

    async def rows_visible(self, *, as_app_role: bool, tenant: Optional[int] = None) -> dict[str, int]:
        """How many of the four reviewed rows each table yields to this role."""
        wanted = {
            "audit_runs": list(self.run_ids),
            "audit_findings": [self.finding_id],
            "risks_v2": [self.risk_id],
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


ALL_FOUR_VISIBLE = {"audit_runs": 2, "audit_findings": 1, "risks_v2": 1}
NONE_VISIBLE = {"audit_runs": 0, "audit_findings": 0, "risks_v2": 0}


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


async def test_a_bypass_role_sees_all_four_rows_and_an_app_role_sees_none(probe):
    """The measured difference, on the same four rows, in one test.

    This is the answer to "``tables_hidden_by_rls`` came back empty for my
    connection": it was empty because that connection bypasses RLS, and that says
    nothing at all about an application role.
    """
    assert await probe.rows_visible(as_app_role=False) == ALL_FOUR_VISIBLE
    assert await probe.rows_visible(as_app_role=True) == NONE_VISIBLE


async def test_no_tenant_setting_reveals_a_row_that_has_no_tenant(probe):
    """There is no value of ``app.current_tenant_id`` that helps.

    ``NULL = 1`` is NULL, not true, so the policy filters these rows for every tenant.
    An operator cannot work around the blindness by setting the session variable, which
    is why the refusal names ``rolsuper``/``rolbypassrls`` specifically.
    """
    for tenant in (1, 2, 99):
        assert (
            await probe.rows_visible(as_app_role=True, tenant=tenant) == NONE_VISIBLE
        ), f"tenant {tenant} should reveal nothing"


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
    assert result["rows_present"] == 4
    assert result["row_level_security"]["bypasses_rls"] is True


async def test_an_app_role_refuses_instead_of_reporting_nothing_to_do(probe, monkeypatch):
    """The worst outcome available here, and the one that must not happen.

    Blind to all four rows, the script would otherwise see an empty result set and
    report "nothing to do" — which an operator would read as the purge already having
    been done and the migration as unblocked, while all four rows are still there.
    """
    _run_scripts_as(probe, monkeypatch, app_role=True)

    result = await plan(reviewed=probe.reviewed)

    assert result["rows_present"] == 0
    assert result["rows_already_absent"] == [], "absence must not be recorded as absence when it cannot be trusted"
    assert len(result["blockers"]) == 4
    assert all("absence cannot be distinguished from being hidden" in blocker for blocker in result["blockers"])
    assert all("rolsuper or rolbypassrls" in blocker for blocker in result["blockers"])
    assert sorted(result["row_level_security"]["subject_to_rls"]) == sorted(RLS_TABLES)


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
        await probe.rows_visible(as_app_role=False) == ALL_FOUR_VISIBLE
    ), "the row is still there; the delete simply did nothing"


async def test_apply_as_an_app_role_rolls_back_rather_than_reporting_success(probe, monkeypatch):
    """Belt and braces: even handed a plan, the apply path re-checks and refuses."""
    _run_scripts_as(probe, monkeypatch, app_role=True)

    with pytest.raises(PreconditionDrifted, match="row-level security"):
        await apply_plan([("audit_runs", probe.run_ids[0])], reviewed=probe.reviewed)

    assert await probe.rows_visible(as_app_role=False) == ALL_FOUR_VISIBLE


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

    assert await probe.rows_visible(as_app_role=True, tenant=1) == {**NONE_VISIBLE, "audit_runs": 1}

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
