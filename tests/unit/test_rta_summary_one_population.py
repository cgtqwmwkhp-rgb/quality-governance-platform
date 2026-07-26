"""PX-223: RTA total / open / closed must describe one population.

Analytics showed Open 32, Total 31, Closed 0. `total` was the executive dashboard's
`total_in_period` (RTAs created inside the selected window) while `open` and `closed`
were counted from the whole register, so Open could exceed Total. The summary now
returns register-wide total/open/closed together, with the windowed figure kept under
its own name.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from src.api.schemas.executive_dashboard import RTASummary
from src.domain.services.executive_dashboard import _EMPTY_RTA_SUMMARY, ExecutiveDashboardService


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar(self) -> int:
        return self._value


class _FakeSession:
    """Returns the queued scalars in call order."""

    def __init__(self, scalars: list[int]) -> None:
        self._scalars = list(scalars)

    async def execute(self, _query: Any) -> _ScalarResult:
        return _ScalarResult(self._scalars.pop(0))


@pytest.mark.asyncio
async def test_open_cannot_exceed_total():
    """The reported shape: a quiet window but a busy register."""
    # total_in_period, register total, closed
    service = ExecutiveDashboardService(_FakeSession([31, 32, 0]), tenant_id=1)

    summary = await service._get_rta_summary(datetime.now(timezone.utc) - timedelta(days=30))

    assert summary["total_in_period"] == 31
    assert summary["total"] == 32
    assert summary["open"] == 32
    assert summary["closed"] == 0
    assert summary["open"] <= summary["total"]


@pytest.mark.asyncio
async def test_open_plus_closed_always_reconciles_to_total():
    service = ExecutiveDashboardService(_FakeSession([0, 887, 120]), tenant_id=1)

    summary = await service._get_rta_summary(datetime.now(timezone.utc) - timedelta(days=30))

    assert summary["open"] + summary["closed"] == summary["total"] == 887
    assert summary["total_in_period"] == 0, "an empty window must not shrink the register"


@pytest.mark.asyncio
async def test_windowed_total_is_reported_separately_from_the_register():
    service = ExecutiveDashboardService(_FakeSession([5, 40, 10]), tenant_id=1)

    summary = await service._get_rta_summary(datetime.now(timezone.utc) - timedelta(days=7))

    assert summary["total_in_period"] != summary["total"]
    assert set(summary) == {"total_in_period", "total", "open", "closed"}


def test_degraded_summary_still_reconciles():
    """The fallback used when the RTA queries fail must not imply open > total."""
    fallback = RTASummary.model_validate(_EMPTY_RTA_SUMMARY)

    assert fallback.open + fallback.closed == fallback.total == 0
