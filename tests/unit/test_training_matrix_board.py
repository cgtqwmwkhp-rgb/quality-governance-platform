"""Unit tests for the manager Training Matrix board helpers (horizon-first view)."""

from datetime import date, timedelta

from src.domain.services.training_matrix_board import (
    BOARD_ROLES,
    build_status_briefings,
    horizon_for_row,
    normalize_board_role,
    resolve_board_role,
)

TODAY = date(2026, 7, 20)


def test_board_roles_order():
    assert BOARD_ROLES == ("Engineer", "Workshop", "Office", "Management")


def test_resolve_board_role_substring_match():
    assert resolve_board_role("Mobile Engineers") == "Engineer"
    assert resolve_board_role("Workshop") == "Workshop"
    assert resolve_board_role("Head Office") == "Office"
    assert resolve_board_role("Senior Management") == "Management"


def test_resolve_board_role_no_match():
    assert resolve_board_role("Sales") is None
    assert resolve_board_role(None) is None
    assert resolve_board_role("") is None


def test_normalize_board_role():
    assert normalize_board_role("office") == "Office"
    assert normalize_board_role("Engineer") == "Engineer"
    assert normalize_board_role("Sales") is None
    assert normalize_board_role(None) is None


def test_resolve_board_role_prefers_override():
    assert resolve_board_role("IT", "Office") == "Office"
    assert resolve_board_role("Mobile Engineers", "Management") == "Management"
    assert resolve_board_role("IT", None) is None
    assert resolve_board_role("IT", "") is None
    assert resolve_board_role("IT", "Sales") is None


def test_horizon_overdue_status_without_due_date():
    for status in ("overdue", "missing", "pending", "failed"):
        assert horizon_for_row(status, None, TODAY) == "overdue"


def test_horizon_overdue_past_due_date():
    assert horizon_for_row("compliant", TODAY - timedelta(days=1), TODAY) == "overdue"
    assert horizon_for_row("due_soon", TODAY - timedelta(days=400), TODAY) == "overdue"


def test_horizon_buckets_future_due_dates():
    assert horizon_for_row("compliant", TODAY, TODAY) == "d30"
    assert horizon_for_row("compliant", TODAY + timedelta(days=30), TODAY) == "d30"
    assert horizon_for_row("compliant", TODAY + timedelta(days=31), TODAY) == "d60"
    assert horizon_for_row("compliant", TODAY + timedelta(days=60), TODAY) == "d60"
    assert horizon_for_row("compliant", TODAY + timedelta(days=61), TODAY) == "d180"
    assert horizon_for_row("compliant", TODAY + timedelta(days=180), TODAY) == "d180"
    assert horizon_for_row("compliant", TODAY + timedelta(days=181), TODAY) == "ok"


def test_horizon_ok_when_no_due_date_and_not_overdue_status():
    assert horizon_for_row("compliant", None, TODAY) == "ok"
    assert horizon_for_row(None, None, TODAY) == "ok"


def _row(atlas_name, course, status, due_days=None):
    due = None if due_days is None else TODAY + timedelta(days=due_days)
    return {
        "atlas_name": atlas_name,
        "course_display_name": course,
        "status": status,
        "qgp_due_on": due,
    }


def test_build_status_briefings_highest_risk_module_and_due30():
    rows = [
        _row("Alice", "Asbestos Awareness", "overdue", due_days=-5),
        _row("Bob", "Asbestos Awareness", "overdue", due_days=-2),
        _row("Carl", "GDPR", "overdue", due_days=-1),
        _row("Dana", "GDPR", "compliant", due_days=10),
    ]
    role_stats = {
        "Engineer": {"pct": 40.0, "total": 10},
        "Workshop": {"pct": 90.0, "total": 5},
        "Office": {"pct": 70.0, "total": 4},
        "Management": {"pct": 60.0, "total": 2},
    }
    briefings = build_status_briefings(rows, role_stats, today=TODAY)
    titles = [b["title"] for b in briefings]
    assert "Highest-risk module" in titles
    highest = next(b for b in briefings if b["title"] == "Highest-risk module")
    assert "Asbestos Awareness" in highest["detail"]
    assert "2" in highest["detail"]

    due30 = next(b for b in briefings if b["title"] == "Due in 30 days")
    assert "1" in due30["detail"]


def test_build_status_briefings_new_starters_heuristic():
    rows = [
        _row("Eve", "Module A", "missing"),
        _row("Eve", "Module B", "missing"),
        _row("Frank", "Module A", "compliant", due_days=90),
    ]
    role_stats = {"Engineer": {"pct": 50.0, "total": 2}}
    briefings = build_status_briefings(rows, role_stats, today=TODAY)
    starters = next((b for b in briefings if b["title"] == "Likely new starters"), None)
    assert starters is not None
    assert "Eve" in starters["detail"]
    assert "Frank" not in starters["detail"]


def test_build_status_briefings_weakest_and_strongest_role():
    rows = [_row("Alice", "Module A", "compliant", due_days=90)]
    role_stats = {
        "Engineer": {"pct": 30.0, "total": 10},
        "Workshop": {"pct": 95.0, "total": 5},
        "Office": {"pct": 70.0, "total": 4},
        "Management": {"pct": 60.0, "total": 2},
        "Overall": {"pct": 65.0, "total": 21},
    }
    briefings = build_status_briefings(rows, role_stats, today=TODAY)
    weakest = next(b for b in briefings if b["title"] == "Weakest role")
    strongest = next(b for b in briefings if b["title"] == "Strongest role")
    assert "Engineer" in weakest["detail"]
    assert "Workshop" in strongest["detail"]


def test_build_status_briefings_caps_at_five():
    rows = [
        _row("Alice", "Asbestos Awareness", "overdue", due_days=-5),
        _row("Bob", "Asbestos Awareness", "overdue", due_days=-2),
        _row("Eve", "Module A", "missing"),
    ]
    role_stats = {
        "Engineer": {"pct": 30.0, "total": 10},
        "Workshop": {"pct": 95.0, "total": 5},
        "Office": {"pct": 70.0, "total": 4},
        "Management": {"pct": 60.0, "total": 2},
    }
    briefings = build_status_briefings(rows, role_stats, today=TODAY)
    assert len(briefings) <= 5
    assert all({"title", "detail"} <= set(b.keys()) for b in briefings)


def test_build_status_briefings_empty_rows_no_role_stats():
    briefings = build_status_briefings([], {}, today=TODAY)
    assert len(briefings) == 1
    assert briefings[0]["title"] == "Due in 30 days"
