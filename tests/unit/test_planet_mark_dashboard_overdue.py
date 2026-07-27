"""Planet Mark overdue comparisons must not 500 on naive TIMESTAMP deadlines."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.routes.planet_mark import (
    _is_overdue,
    _naive_utc_now,
    get_actions_summary,
    get_carbon_dashboard,
    list_improvement_actions,
)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


def _year(*, year_id: int = 3) -> SimpleNamespace:
    return SimpleNamespace(
        id=year_id,
        year_label="YE2025",
        year_number=2025,
        tenant_id=1,
        total_emissions=100.0,
        emissions_per_fte=1.0,
        average_fte=100.0,
        scope_1_total=10.0,
        scope_2_market=20.0,
        scope_3_total=70.0,
        scope_1_data_quality=2,
        scope_2_data_quality=2,
        scope_3_data_quality=2,
        certification_status="draft",
        expiry_date=None,
        reduction_target_percent=5.0,
        target_emissions_per_fte=0.9,
    )


def _action(
    *,
    status: str = "in_progress",
    time_bound: datetime | None = None,
    action_id: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=action_id,
        action_id=f"ACT-{action_id}",
        action_title="Reduce diesel",
        achievable_owner="Ops",
        time_bound=time_bound if time_bound is not None else datetime.utcnow() - timedelta(days=10),
        scheduled_month=None,
        status=status,
        progress_percent=40,
        target_scope="scope_1",
        expected_reduction_pct=2.0,
        tenant_id=1,
        reporting_year_id=3,
    )


@pytest.mark.parametrize(
    ("status", "deadline", "expected"),
    [
        ("in_progress", datetime(2020, 1, 1), True),
        ("completed", datetime(2020, 1, 1), False),
        ("in_progress", None, False),
        (
            "in_progress",
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            True,
        ),
        ("planned", datetime(2099, 1, 1), False),
    ],
)
def test_is_overdue_table(status, deadline, expected):
    now = datetime(2026, 7, 27, 12, 0, 0)
    assert _is_overdue(status, deadline, now) is expected


def test_naive_utc_now_is_naive():
    assert _naive_utc_now().tzinfo is None


@pytest.mark.asyncio
async def test_dashboard_naive_time_bound_does_not_500():
    """Regression: aware now vs naive DB deadline previously TypeError → 500."""
    year = _year()
    action = _action(time_bound=datetime.utcnow() - timedelta(days=10))
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult([year]), _FakeResult([action])]),
    )
    user = SimpleNamespace(tenant_id=1, id=1)
    request = SimpleNamespace()

    result = await get_carbon_dashboard(request=request, db=db, current_user=user)

    assert result["actions"]["total"] == 1
    assert result["actions"]["overdue"] == 1
    assert result["current_year"]["label"] == "YE2025"


@pytest.mark.asyncio
async def test_list_actions_naive_time_bound_does_not_500():
    action = _action(time_bound=datetime.utcnow() - timedelta(days=3))
    db = SimpleNamespace(execute=AsyncMock(return_value=_FakeResult([action])))
    user = SimpleNamespace(tenant_id=1, id=1)

    result = await list_improvement_actions(year_id=3, db=db, current_user=user)

    assert result["summary"]["overdue"] == 1
    assert result["actions"][0]["is_overdue"] is True


@pytest.mark.asyncio
async def test_actions_summary_naive_time_bound_does_not_500():
    action = _action(time_bound=datetime.utcnow() - timedelta(days=3))
    db = SimpleNamespace(execute=AsyncMock(return_value=_FakeResult([action])))
    user = SimpleNamespace(tenant_id=1, id=1)

    result = await get_actions_summary(year_id=3, db=db, current_user=user)

    assert result["overdue"] == 1


@pytest.mark.asyncio
async def test_dashboard_empty_actions_ok():
    year = _year()
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult([year]), _FakeResult([])]),
    )
    user = SimpleNamespace(tenant_id=1, id=1)
    request = SimpleNamespace()

    result = await get_carbon_dashboard(request=request, db=db, current_user=user)

    assert result["actions"] == {"total": 0, "completed": 0, "overdue": 0}
