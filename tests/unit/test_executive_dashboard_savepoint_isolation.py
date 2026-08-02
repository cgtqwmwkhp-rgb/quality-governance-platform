"""C-8: dashboard recovery must unwind a savepoint, not the caller's transaction.

``ExecutiveDashboardService`` swallows a failed sub-query so one drifted table
cannot 500 the page, and then keeps querying — which on PostgreSQL only works if
something unwinds the aborted transaction first (#1388). It used to do that with
``Session.rollback()``.

That is the wrong tool on a shared request session. A full rollback ends the
request's transaction and expires every instance in its identity map, including
the ``current_user`` ``get_current_user`` loaded on the very same session; the
next attribute read off it emits a lazy refresh, and a lazy refresh over an async
session raises MissingGreenlet. ``/api/v1/analytics/kpis`` 500'd on exactly that
and still carries a defensive ``tenant_id`` read from it. Rolling back to a
savepoint costs the failed aggregate and nothing else.

The abort semantics are PostgreSQL's and this tier has no database, so the
session double below *models* them, in the same shape as the C-53 suite in
``test_actions_summary_savepoint_isolation.py``. The identity-map half is checked
against a real SQLAlchemy async session instead of being modelled.
"""

from __future__ import annotations

from typing import Any, List, Optional

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.models.user import User
from src.domain.services.executive_dashboard import _TREND_SERIES, ExecutiveDashboardService
from src.domain.services.session_savepoint import read_savepoint


class _Result:
    """Enough of the SQLAlchemy Result surface for the dashboard's aggregates."""

    def scalar(self) -> int:
        return 0

    def scalars(self) -> "_Result":
        return self

    def all(self) -> List[Any]:
        return []

    def first(self) -> None:
        return None

    def one_or_none(self) -> None:
        return None

    def scalar_one_or_none(self) -> None:
        return None


class _Savepoint:
    """What ``AsyncSession.begin_nested()`` gives back: release or roll back.

    Exiting with an exception rolls back to the savepoint, which on PostgreSQL
    puts the transaction back into a usable state, then re-raises so the caller's
    ``except`` still sees the failure.
    """

    def __init__(self, session: "_AbortSemanticsSession") -> None:
        self._session = session

    async def __aenter__(self) -> "_Savepoint":
        self._session.savepoints_opened += 1
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if exc_type is not None:
            self._session.savepoint_rollbacks += 1
            self._session.aborted = False
        return False


class _AbortSemanticsSession:
    """An async session double that enforces PostgreSQL's abort rule.

    One statement fails; every statement after it in the same transaction raises
    until the transaction is rolled back or unwound to a savepoint. Nothing here
    is specific to this repository — it is the behaviour PostgreSQL documents for
    a transaction block that hits an error.

    ``rollback()`` is recorded as well as honoured, because a full session
    rollback expires the identity map the request shares and is therefore the
    wrong tool on this path.
    """

    def __init__(self, *, fail_on: int = 1) -> None:
        self.fail_on = fail_on
        self.calls = 0
        self.aborted = False
        self.refused = 0
        self.rollbacks = 0
        self.savepoints_opened = 0
        self.savepoint_rollbacks = 0

    async def execute(self, *_args: Any, **_kwargs: Any) -> _Result:
        self.calls += 1
        if self.aborted:
            self.refused += 1
            raise RuntimeError("current transaction is aborted, commands ignored until end of transaction block")
        if self.calls == self.fail_on:
            self.aborted = True
            raise RuntimeError("column legacy_key_risk_indicators.created_by_id does not exist")
        return _Result()

    async def scalar(self, *_args: Any, **_kwargs: Any) -> int:
        """``AsyncSession.scalar`` is a statement like any other — same abort rule.

        The audit aggregate reaches the session through ``AuditAnalyticsService``,
        which counts with ``scalar`` rather than ``execute``. Without it here the
        audit tile fails for want of a method and the double reports a broken
        dashboard on the healthy path.
        """
        return (await self.execute()).scalar()

    def begin_nested(self) -> _Savepoint:
        return _Savepoint(self)

    async def rollback(self) -> None:
        self.rollbacks += 1
        self.aborted = False


class _NoSavepointSession(_AbortSemanticsSession):
    """A session that cannot open a savepoint at all (test doubles, odd dialects)."""

    begin_nested = None  # type: ignore[assignment]


class _BrokenUnwindSavepoint(_Savepoint):
    """A savepoint whose rollback fails, leaving the transaction as broken as it was."""

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if exc_type is not None:
            raise RuntimeError("ROLLBACK TO SAVEPOINT failed")
        return False


class _BrokenUnwindSession(_AbortSemanticsSession):
    def begin_nested(self) -> _Savepoint:
        return _BrokenUnwindSavepoint(self)


@pytest.mark.asyncio
async def test_a_failed_aggregate_unwinds_its_savepoint_not_the_transaction() -> None:
    """The C-8 assertion: recovery must stay scoped to the failed aggregate."""
    session = _AbortSemanticsSession(fail_on=1)

    payload = await ExecutiveDashboardService(session, tenant_id=7).get_full_dashboard(30)

    assert session.rollbacks == 0, "the dashboard must not roll back the session the request shares"
    assert session.savepoint_rollbacks >= 1, "the failed aggregate must unwind to its savepoint"
    assert payload["unavailable"] == ["incidents"], "only the aggregate that failed may be reported unavailable"


@pytest.mark.asyncio
async def test_the_savepoint_unwind_still_lets_every_later_aggregate_run() -> None:
    """The #1388 guarantee has to survive the change of mechanism."""
    session = _AbortSemanticsSession(fail_on=1)

    payload = await ExecutiveDashboardService(session, tenant_id=7).get_full_dashboard(30)

    assert session.refused == 0, "no statement may run on an aborted transaction"
    assert payload["trends"]["unavailable"] == [], "trends run after the failure and must still be served"


@pytest.mark.asyncio
async def test_a_session_that_cannot_open_a_savepoint_still_gets_the_transaction_back() -> None:
    """Degrading to "unscoped" here would re-introduce the dashboard of zeros.

    ``actions.py`` can let an unscoped read simply fail, because nothing depends
    on the transaction surviving it. This service queries for another twenty
    statements afterwards, so the blunt rollback stays as the fallback.

    Not a regression test: it passes on the pre-C-8 code too, which rolled back
    unconditionally. It is here so the fallback cannot be dropped as dead code.
    """
    session = _NoSavepointSession(fail_on=1)

    payload = await ExecutiveDashboardService(session, tenant_id=7).get_full_dashboard(30)

    assert session.rollbacks >= 1, "with no savepoint available the fallback rollback must fire"
    assert payload["trends"]["unavailable"] == []


@pytest.mark.asyncio
async def test_a_failed_savepoint_unwind_escalates_to_the_full_rollback() -> None:
    """A savepoint that could not be rolled back has recovered nothing.

    Reporting it as recovery would leave the transaction aborted and hand back the
    page of zeros, so the scope reports the failure and the fallback takes over.

    Also passes pre-C-8, for the same reason as the test above; it exists to pin
    the one shape where a savepoint is opened and still recovers nothing.
    """
    session = _BrokenUnwindSession(fail_on=1)

    payload = await ExecutiveDashboardService(session, tenant_id=7).get_full_dashboard(30)

    assert session.rollbacks >= 1, "a failed unwind must escalate rather than leave the transaction aborted"
    assert payload["trends"]["unavailable"] == []


@pytest.mark.asyncio
async def test_a_healthy_session_opens_no_rollback_of_either_kind() -> None:
    """Baseline: the double itself does not distort a dashboard that works."""
    session = _AbortSemanticsSession(fail_on=0)

    payload = await ExecutiveDashboardService(session, tenant_id=7).get_full_dashboard(30)

    assert session.rollbacks == 0
    assert session.savepoint_rollbacks == 0
    assert payload["unavailable"] == []
    assert sorted(payload["trends"]) == sorted([*_TREND_SERIES, "unavailable"])


@pytest.mark.asyncio
async def test_a_failed_aggregate_leaves_the_shared_current_user_usable() -> None:
    """The identity-map claim, checked against a real SQLAlchemy async session.

    ``Session.rollback()`` expires everything in the identity map, so the
    ``current_user`` loaded on the request's session would need a lazy refresh —
    and a lazy refresh over an async session raises MissingGreenlet rather than
    returning a user. Unwinding to a savepoint must not do that.

    SQLite is used because this tier has no database, and SQLite does not abort a
    transaction on a failed statement the way PostgreSQL does. So this test
    verifies the *expiry* half on a real session; the abort half is modelled by
    :class:`_AbortSemanticsSession` above.
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

            service = ExecutiveDashboardService(session, tenant_id=7)

            async def _drifted_aggregate() -> dict:
                await session.execute(text("SELECT no_such_column FROM users"))
                raise AssertionError("unreachable: the statement above must fail")

            sentinel = {"unmeasured": True}
            unavailable: List[str] = []
            result = await service._safe_call(_drifted_aggregate(), sentinel, name="incidents", unavailable=unavailable)

            assert result is sentinel, "the failed aggregate must fall back to its empty default"
            assert unavailable == ["incidents"], "and must be named as unavailable rather than measured"
            assert not inspect(current_user).expired, "a savepoint unwind must not expire the caller's instances"
            # Reads the attribute without I/O; an expired instance would need a
            # lazy refresh here, which is the production 500 this avoids.
            assert current_user.tenant_id == 7
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_scope_reports_recovery_only_when_the_unwind_succeeded() -> None:
    """The contract ``_recover_session`` reads to decide whether to escalate."""
    healthy = _AbortSemanticsSession()
    with pytest.raises(RuntimeError):
        async with read_savepoint(healthy) as scope:
            raise RuntimeError("boom")
    assert scope.recovered is True

    broken = _BrokenUnwindSession()
    caught: Optional[BaseException] = None
    try:
        async with read_savepoint(broken) as broken_scope:
            raise RuntimeError("boom")
    except BaseException as exc:  # noqa: B036 - the unwind's error replaces the body's
        caught = exc
    assert isinstance(caught, RuntimeError)
    assert str(caught) == "ROLLBACK TO SAVEPOINT failed"
    assert broken_scope.recovered is False

    absent = _NoSavepointSession()
    with pytest.raises(RuntimeError):
        async with read_savepoint(absent) as absent_scope:
            raise RuntimeError("boom")
    assert absent_scope.recovered is False
