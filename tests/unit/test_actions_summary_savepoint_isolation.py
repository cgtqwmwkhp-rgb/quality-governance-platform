"""C-53: one broken action store must not take the other five down with it.

``/actions/summary`` runs six aggregate queries, one per action store, each in its
own ``try / except``. On PostgreSQL a failed statement aborts the whole
transaction and every later statement raises ``InFailedSqlTransaction`` until
something rolls back, so swallowing the first error without rolling back turns
one broken store into six — and then into whatever the two trailing
``_count_for_source`` calls do on a dead transaction.

The abort semantics are PostgreSQL's, and the project's unit tier runs without a
database, so the session double below *models* those semantics explicitly:
``execute`` refuses everything after the first failure until a savepoint (or the
transaction) is rolled back. That is a model of documented behaviour, not an
observation of a live PostgreSQL — see the docstring on
:class:`_PostgresAbortSemanticsSession`.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import InternalError, OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.routes.actions import _compute_actions_summary, _read_savepoint
from src.domain.models.user import User

# Table name → the canned status histogram that store would return when healthy.
_HEALTHY_HISTOGRAM: dict[str, list[tuple[str, int]]] = {
    "incident_actions": [("open", 3)],
    "rta_actions": [("open", 5)],
    "complaint_actions": [("in_progress", 2)],
    "investigation_actions": [("open", 1)],
    "capa_actions": [("closed", 4)],
    "capa_items": [("verified", 6)],
}

# Table name → the row count that store contributes to total / overdue.
_HEALTHY_COUNT: dict[str, int] = {
    "incident_actions": 3,
    "rta_actions": 5,
    "complaint_actions": 2,
    "investigation_actions": 1,
    "capa_actions": 4,
    "capa_items": 6,
}


class _FakeResult:
    """Serves both the group-by histogram reads and the scalar count reads."""

    def __init__(self, rows: list[tuple[Any, int]], scalar: int) -> None:
        self._rows = rows
        self._scalar = scalar

    def all(self) -> list[tuple[Any, int]]:
        return self._rows

    def scalar(self) -> int:
        return self._scalar


class _SavepointRollback:
    """What ``AsyncSession.begin_nested()`` gives back: release or roll back.

    Exiting with an exception rolls back to the savepoint, which on PostgreSQL
    puts the transaction back into a usable state, then re-raises so the caller's
    ``except`` still sees the failure.
    """

    def __init__(self, session: "_PostgresAbortSemanticsSession") -> None:
        self._session = session

    async def __aenter__(self) -> "_SavepointRollback":
        self._session.savepoints_opened += 1
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if exc_type is not None:
            self._session.savepoint_rollbacks += 1
            self._session.aborted = False
        return False


class _PostgresAbortSemanticsSession:
    """An async session double that enforces PostgreSQL's abort rule.

    One statement fails; every statement after it in the same transaction raises
    until the transaction is rolled back or unwound to a savepoint. Nothing here
    is specific to this repository — it is the behaviour PostgreSQL documents for
    a transaction block that hits an error.

    ``rollback()`` is recorded as well as honoured, because a full session
    rollback expires every instance in the identity map (including the
    ``current_user`` authentication loaded on the same session) and is therefore
    the wrong tool on a read path. Tests assert it is never reached.
    """

    def __init__(self, *, failing_table: Optional[str] = None) -> None:
        self.failing_table = failing_table
        self.aborted = False
        self.executed: list[str] = []
        self.refused: list[str] = []
        self.rollbacks = 0
        self.savepoints_opened = 0
        self.savepoint_rollbacks = 0

    @staticmethod
    def _table_of(query: Any) -> str:
        sql = str(query)
        for table in _HEALTHY_HISTOGRAM:
            if table in sql:
                return table
        raise AssertionError(f"query touched no known action table: {sql}")

    async def execute(self, query: Any) -> _FakeResult:
        table = self._table_of(query)
        if self.aborted:
            self.refused.append(table)
            raise InternalError(
                "SELECT ...",
                {},
                Exception("current transaction is aborted, commands ignored until end of transaction block"),
            )
        if table == self.failing_table:
            self.aborted = True
            raise ProgrammingError("SELECT ...", {}, Exception(f'column "{table}.status" does not exist'))
        self.executed.append(table)
        return _FakeResult(_HEALTHY_HISTOGRAM[table], _HEALTHY_COUNT[table])

    def begin_nested(self) -> _SavepointRollback:
        return _SavepointRollback(self)

    async def rollback(self) -> None:
        self.rollbacks += 1
        self.aborted = False


_ALL_HEALTHY_TOTAL = sum(_HEALTHY_COUNT.values())


@pytest.mark.asyncio
async def test_every_store_reports_when_nothing_is_broken() -> None:
    """Baseline: the double itself does not distort a healthy read."""
    session = _PostgresAbortSemanticsSession()

    summary = await _compute_actions_summary(session, tenant_id=1)

    assert summary.total == _ALL_HEALTHY_TOTAL
    assert summary.overdue == _ALL_HEALTHY_TOTAL
    assert sum(summary.by_display_status.values()) == _ALL_HEALTHY_TOTAL
    assert session.refused == []


@pytest.mark.parametrize("broken", sorted(_HEALTHY_HISTOGRAM))
@pytest.mark.asyncio
async def test_one_broken_store_does_not_silence_the_others(broken: str) -> None:
    """A failure in any one store must cost exactly that store's rows."""
    session = _PostgresAbortSemanticsSession(failing_table=broken)

    summary = await _compute_actions_summary(session, tenant_id=1)

    expected = _ALL_HEALTHY_TOTAL - _HEALTHY_COUNT[broken]
    assert summary.total == expected, f"{broken} failing must not zero the other five"
    assert summary.overdue == expected
    assert sum(summary.by_display_status.values()) == expected
    assert session.refused == [], "no statement may run on an aborted transaction"


@pytest.mark.asyncio
async def test_the_trailing_totals_are_not_run_on_a_dead_transaction() -> None:
    """The two ``_count_for_source`` calls sit after the six aggregates.

    They used to run outside every ``try`` on whatever state the aggregates left
    behind. Whatever else changes, they must still see a live transaction.
    """
    session = _PostgresAbortSemanticsSession(failing_table="incident_actions")

    summary = await _compute_actions_summary(session, tenant_id=1)

    assert summary.total > 0, "total must not collapse to a fabricated zero"
    assert summary.overdue > 0


@pytest.mark.asyncio
async def test_recovery_never_expires_the_identity_map() -> None:
    """A full ``Session.rollback()`` would expire ``current_user`` mid-request.

    That is a real 500 this repository has already paid for (MissingGreenlet on a
    lazy refresh of ``current_user.tenant_id`` over an async session). Recovery
    here must stay scoped to a savepoint.
    """
    session = _PostgresAbortSemanticsSession(failing_table="capa_actions")

    await _compute_actions_summary(session, tenant_id=1)

    assert session.rollbacks == 0, "summary must not roll back the session the caller shares"
    assert session.savepoint_rollbacks >= 1, "the failed aggregate must unwind to its savepoint"


@pytest.mark.asyncio
async def test_a_savepoint_rollback_leaves_a_loaded_user_usable() -> None:
    """The identity-map claim, checked against a real SQLAlchemy async session.

    ``Session.rollback()`` expires everything in the identity map, so the
    ``current_user`` authentication loaded on the request's session would need a
    lazy refresh — and a lazy refresh over an async session raises MissingGreenlet
    rather than returning a user. Unwinding to a savepoint must not do that.

    SQLite is used because the unit tier has no database, and SQLite does not
    abort a transaction on a failed statement the way PostgreSQL does. So this
    test verifies the *expiry* half on a real session; the abort half is modelled
    by :class:`_PostgresAbortSemanticsSession` above.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(User.__table__.create)
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        async with factory() as session:
            session.add(
                User(
                    email="auth@example.com",
                    hashed_password="x",
                    first_name="Auth",
                    last_name="User",
                    tenant_id=7,
                )
            )
            await session.commit()
            current_user = (await session.execute(select(User))).scalars().one()
            assert current_user.tenant_id == 7

            with pytest.raises(OperationalError):
                async with _read_savepoint(session):
                    await session.execute(text("SELECT no_such_column FROM users"))

            assert not inspect(current_user).expired, "a savepoint unwind must not expire the caller's instances"
            # Reads the attribute without I/O; an expired instance would need a
            # lazy refresh here, which is the production 500 this avoids.
            assert current_user.tenant_id == 7
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_summary_still_answers_when_every_store_is_broken() -> None:
    """Total honesty is not on offer here, but a 500 is not either."""

    class _AllBroken(_PostgresAbortSemanticsSession):
        async def execute(self, query: Any) -> _FakeResult:
            table = self._table_of(query)
            if self.aborted:
                self.refused.append(table)
                raise InternalError("SELECT ...", {}, Exception("current transaction is aborted"))
            self.aborted = True
            raise ProgrammingError("SELECT ...", {}, Exception("relation does not exist"))

    session = _AllBroken()

    summary = await _compute_actions_summary(session, tenant_id=1)

    assert summary.total == 0
    assert summary.by_display_status == {}
