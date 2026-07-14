"""Unit tests for portal → staff golden-thread response fields."""

from types import SimpleNamespace

from src.api.routes.employee_portal import staff_golden_thread_fields


def test_anonymous_submit_returns_tracking_only() -> None:
    fields = staff_golden_thread_fields(None, entity_type="near_miss", entity_id=42)
    assert fields["can_open_staff_record"] is False
    assert fields["staff_href"] is None
    assert fields["entity_id"] is None


def test_authenticated_staff_gets_deep_link() -> None:
    user = SimpleNamespace(id=1, is_superuser=False, has_permission=lambda _p: False)
    fields = staff_golden_thread_fields(user, entity_type="near_miss", entity_id=42)
    assert fields["can_open_staff_record"] is True
    assert fields["staff_href"] == "/near-misses/42"
    assert fields["entity_id"] == 42
    assert fields["entity_type"] == "near_miss"


def test_incident_staff_href() -> None:
    user = SimpleNamespace(id=1, is_superuser=True, has_permission=lambda _p: True)
    fields = staff_golden_thread_fields(user, entity_type="incident", entity_id=7)
    assert fields["staff_href"] == "/incidents/7"
