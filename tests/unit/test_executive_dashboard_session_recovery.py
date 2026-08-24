"""One failed sub-query must not turn the whole dashboard into zeros.

PostgreSQL aborts the enclosing transaction on the first failing statement and
rejects every statement after it until the transaction ends. The dashboard
swallows sub-query errors so that a single unavailable table does not 500 the
page — but without a rollback that tolerance spreads the failure to every later
aggregate, and each one reports its empty default. An executive then reads a
page of zeros that is indistinguishable from real data.

This was found in CI rather than in review: `legacy_key_risk_indicators` is
missing `created_by_id` on a migrated PostgreSQL database, and that one drifted
column was enough to zero every tile and every trend series that ran after it.

Scope note (C-8): the session double here has no ``begin_nested``, so what these
two tests now pin is the *fallback* — the full rollback the service keeps for a
session that cannot open a savepoint. Production sessions can, and that path is
covered by ``test_executive_dashboard_savepoint_isolation.py``. Both must hold:
this file says recovery happens at all, that one says it stays scoped.
"""

from typing import Any, List

import pytest

from src.domain.services.executive_dashboard import _TREND_SERIES, ExecutiveDashboardService


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


class _PoisonedSession:
    """Fails the nth statement, then rejects everything until a rollback."""

    def __init__(self, fail_on: int = 1) -> None:
        self.fail_on = fail_on
        self.calls = 0
        self.aborted = False
        self.rollbacks = 0

    async def execute(self, *_args: Any, **_kwargs: Any) -> _Result:
        self.calls += 1
        if self.aborted:
            raise RuntimeError("current transaction is aborted, commands ignored until end of transaction block")
        if self.calls == self.fail_on:
            self.aborted = True
            raise RuntimeError("column legacy_key_risk_indicators.created_by_id does not exist")
        return _Result()

    async def rollback(self) -> None:
        self.rollbacks += 1
        self.aborted = False


class _UnrecoverableSession(_PoisonedSession):
    """The behaviour before the fix: the abort is never cleared."""

    async def rollback(self) -> None:
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_one_failed_subquery_does_not_zero_the_later_aggregates():
    session = _PoisonedSession(fail_on=1)

    payload = await ExecutiveDashboardService(session, tenant_id=7).get_full_dashboard(30)

    assert session.rollbacks >= 1, "a failed sub-query must end the aborted transaction"
    assert payload["trends"]["unavailable"] == [], "trends run after the failure and must still be served"


@pytest.mark.asyncio
async def test_without_recovery_a_single_failure_takes_out_every_trend():
    """Proves the assertion above has teeth rather than passing by construction."""
    session = _UnrecoverableSession(fail_on=1)

    payload = await ExecutiveDashboardService(session, tenant_id=7).get_full_dashboard(30)

    assert sorted(payload["trends"]["unavailable"]) == sorted(_TREND_SERIES)
