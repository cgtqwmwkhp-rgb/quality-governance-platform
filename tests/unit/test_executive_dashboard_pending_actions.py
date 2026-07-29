"""The executive summary's `pending_actions` must count actions, not cases (C-66).

Before this suite existed, `pending_actions` was
``incidents["open"] + complaints["open"]`` — two case counts under a name that
promises outstanding remedial work. Staging returned `pending_actions 9` while
`/actions/summary` returned `total 0` on the same token in the same minute.

These tests pin three properties the old code could not satisfy:
  * the number is sourced from the action stores, so it does not move when case
    volume moves;
  * the case figure survives under an honest name (`open_cases`);
  * an unreadable action aggregate reports `null`, not `0`.
"""

from typing import Optional

import pytest

from src.api.routes._action_unified import TERMINAL_DISPLAY_STATUSES, pending_action_count
from src.api.routes.actions import ActionsSummaryResponse
from src.api.schemas.executive_dashboard import DashboardSummaryResponse


def _dashboard(*, open_incidents: int, open_complaints: int) -> dict:
    return {
        "health_score": {"score": 80.0, "status": "healthy"},
        "incidents": {"open": open_incidents},
        "complaints": {"open": open_complaints},
        "compliance": {"overdue": 4},
        "kris": {"pending_alerts": 2},
    }


class _StubService:
    """Stands in for ExecutiveDashboardService: only get_full_dashboard is used."""

    def __init__(self, payload: dict):
        self._payload = payload

    async def get_full_dashboard(self, _period_days: int) -> dict:
        return self._payload


class _User:
    tenant_id: Optional[int] = 7


async def _call_summary(monkeypatch, *, dashboard: dict, summary_result):
    """Invoke the route function with the service and action aggregate stubbed."""
    from src.api.routes import executive_dashboard as route_mod

    monkeypatch.setattr(
        route_mod,
        "ExecutiveDashboardService",
        lambda _db, tenant_id=None: _StubService(dashboard),
    )

    async def _fake_compute(_db, _tenant_id):
        if isinstance(summary_result, Exception):
            raise summary_result
        return summary_result

    monkeypatch.setattr(route_mod, "_compute_actions_summary", _fake_compute)
    return await route_mod.get_dashboard_summary(db=object(), current_user=_User())


# ---------------------------------------------------------------------------
# pending_action_count — the display-status vocabulary
# ---------------------------------------------------------------------------


def test_pending_count_excludes_terminal_statuses():
    histogram = {"open": 3, "in_progress": 2, "completed": 40, "cancelled": 5, "closed": 6}
    assert pending_action_count(histogram) == 5


def test_pending_verification_is_still_outstanding_work():
    """Done-but-unverified is work somebody still owes; it must not read as finished."""
    assert "pending_verification" not in TERMINAL_DISPLAY_STATUSES
    assert pending_action_count({"pending_verification": 4, "completed": 9}) == 4


def test_unrecognised_status_counts_as_outstanding():
    """A status this vocabulary has never seen must over-report, never silently vanish."""
    assert pending_action_count({"awaiting_signoff": 3, "completed": 1}) == 3


def test_empty_histogram_is_zero_not_error():
    assert pending_action_count({}) == 0


# ---------------------------------------------------------------------------
# The route
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pending_actions_comes_from_actions_not_cases(monkeypatch):
    """The regression: 8 open incidents + 1 open complaint must not read as 9 actions."""
    result = await _call_summary(
        monkeypatch,
        dashboard=_dashboard(open_incidents=8, open_complaints=1),
        summary_result=ActionsSummaryResponse(total=0, by_display_status={}, overdue=0),
    )
    assert isinstance(result, DashboardSummaryResponse)
    assert result.pending_actions == 0, "an empty action register must report 0 pending actions"
    assert result.open_cases == 9, "the case figure survives under its honest name"
    assert result.open_incidents == 8


@pytest.mark.asyncio
async def test_pending_actions_does_not_move_with_case_volume(monkeypatch):
    """Opening cases created no action, so the action tile must not rise."""
    aggregate = ActionsSummaryResponse(
        total=7,
        by_display_status={"open": 2, "in_progress": 1, "completed": 4},
        overdue=0,
    )
    quiet = await _call_summary(
        monkeypatch, dashboard=_dashboard(open_incidents=0, open_complaints=0), summary_result=aggregate
    )
    busy = await _call_summary(
        monkeypatch, dashboard=_dashboard(open_incidents=40, open_complaints=13), summary_result=aggregate
    )
    assert quiet.pending_actions == busy.pending_actions == 3
    assert (quiet.open_cases, busy.open_cases) == (0, 53)


@pytest.mark.asyncio
async def test_unreadable_action_aggregate_reports_null_not_zero(monkeypatch):
    """PX-216: a query that never returned is not a measurement of zero."""
    result = await _call_summary(
        monkeypatch,
        dashboard=_dashboard(open_incidents=8, open_complaints=1),
        summary_result=RuntimeError("simulated action store failure"),
    )
    assert result.pending_actions is None
    assert result.open_cases == 9, "the case figure is independent and must still be reported"


@pytest.mark.asyncio
async def test_null_pending_actions_is_representable_in_the_response_schema():
    """Fail-honest is only honest if the contract can carry it."""
    validated = DashboardSummaryResponse.model_validate(
        {
            "health_score": 80.0,
            "health_status": "healthy",
            "open_incidents": 8,
            "open_cases": 9,
            "pending_actions": None,
            "overdue_items": 4,
            "kri_alerts": 2,
        }
    )
    assert validated.pending_actions is None
    assert "pending_actions" in validated.model_dump()
