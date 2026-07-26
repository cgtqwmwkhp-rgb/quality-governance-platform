"""PX-149: the Actions KPI tile and the filter chip must share one aggregation.

Before the fix, `/actions/summary` derived "overdue" from the status histogram, so it
only ever counted CAPA rows whose stored status is literally ``overdue``. `/view-counts`
derived it from the due-date predicate. The Actions page renders both at once, which is
how the same screen showed "Overdue 0" in the tile and "Overdue 10" in the chip.

The same histogram also omitted RCA ``CAPAItem`` rows, which the list endpoint and
view-counts both include — so the Total tile under-counted the register beneath it.
"""

from typing import Any

import pytest

from src.api.routes import actions as actions_module
from src.api.routes.actions import ActionsSummaryResponse, _compute_actions_summary


class _FakeResult:
    def __init__(self, rows: list[tuple[Any, int]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[Any, int]]:
        return self._rows


class _FakeSession:
    """Returns one canned group-by result per status-histogram query, in call order."""

    def __init__(self, batches: list[list[tuple[Any, int]]]) -> None:
        self._batches = list(batches)
        self.calls = 0

    async def execute(self, _query: Any) -> _FakeResult:
        self.calls += 1
        rows = self._batches.pop(0) if self._batches else []
        return _FakeResult(rows)


# incident, rta, complaint, investigation, capa, capa_item
_NO_ROWS: list[list[tuple[Any, int]]] = [[] for _ in range(6)]


@pytest.mark.asyncio
async def test_overdue_is_the_due_date_predicate_not_the_capa_status(monkeypatch):
    """A CAPA row stored as status='overdue' must not become the reported overdue KPI."""
    captured: list[bool] = []

    async def fake_count(_db, *_args, **kwargs) -> int:
        overdue = bool(kwargs.get("overdue", False))
        captured.append(overdue)
        return 10 if overdue else 57

    monkeypatch.setattr(actions_module, "_count_for_source", fake_count)

    # One CAPA row literally stored as "overdue" — the only thing the old histogram saw.
    batches = [[], [], [], [], [("overdue", 1)], []]
    summary = await _compute_actions_summary(_FakeSession(batches), tenant_id=1)

    assert summary.overdue == 10, "overdue must come from the shared due-date aggregate"
    assert summary.by_display_status["overdue"] == 1, "histogram still reports raw status"
    assert summary.overdue != summary.by_display_status["overdue"]
    assert captured == [False, True], "total and overdue both go through _count_for_source"


@pytest.mark.asyncio
async def test_total_matches_the_aggregate_behind_the_list_and_view_counts(monkeypatch):
    """Total must be the same population the register lists, not a histogram sum."""

    async def fake_count(_db, *_args, **kwargs) -> int:
        return 3 if kwargs.get("overdue", False) else 42

    monkeypatch.setattr(actions_module, "_count_for_source", fake_count)

    # Histogram sums to 5; the shared aggregate says 42. Total must follow the aggregate.
    batches = [[("open", 2)], [], [], [], [("closed", 2)], [("open", 1)]]
    summary = await _compute_actions_summary(_FakeSession(batches), tenant_id=1)

    assert summary.total == 42
    assert sum(summary.by_display_status.values()) == 5


@pytest.mark.asyncio
async def test_capa_item_rows_reach_the_status_histogram(monkeypatch):
    """RCA CAPAItem rows appear in the list, so they must appear in the breakdown."""

    async def fake_count(_db, *_args, **kwargs) -> int:
        return 0 if kwargs.get("overdue", False) else 1

    monkeypatch.setattr(actions_module, "_count_for_source", fake_count)

    batches = [[], [], [], [], [], [("in_progress", 4)]]
    summary = await _compute_actions_summary(_FakeSession(batches), tenant_id=1)

    assert summary.by_display_status.get("in_progress") == 4


def test_summary_response_exposes_overdue_alongside_the_histogram():
    body = ActionsSummaryResponse(total=9, by_display_status={"open": 9}, overdue=4)
    dumped = body.model_dump()

    assert dumped["overdue"] == 4
    assert set(dumped.keys()) == {"total", "by_display_status", "overdue"}
