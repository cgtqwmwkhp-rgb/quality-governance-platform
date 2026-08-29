"""Honesty rules for AUDIT_SCHEDULED notify and the portal device queue."""

from types import SimpleNamespace

from src.domain.services.audit_assignment_notify import (
    is_device_queue_run,
    portal_audit_action_url,
    should_notify_assignee_change,
)


def test_action_url_is_portal_not_staff_execute():
    url = portal_audit_action_url()
    assert url.startswith("/portal/")
    assert "/audits/" not in url or url == "/portal/audits"
    assert "/execute" not in url


def test_notify_on_new_assignee_not_on_same_person():
    assert should_notify_assignee_change(previous_id=None, new_id=7) is True
    assert should_notify_assignee_change(previous_id=4, new_id=7) is True
    assert should_notify_assignee_change(previous_id=7, new_id=7) is False
    assert should_notify_assignee_change(previous_id=7, new_id=None) is False


def test_device_queue_excludes_serializer_fallbacks_and_closed_work():
    assert is_device_queue_run(SimpleNamespace(reference_number="AUD-1", status="scheduled"))
    assert not is_device_queue_run(SimpleNamespace(reference_number="???", status="scheduled"))
    assert not is_device_queue_run(SimpleNamespace(reference_number="AUD-1", status="unknown"))
    assert not is_device_queue_run(SimpleNamespace(reference_number="", status="scheduled"))
    assert not is_device_queue_run(SimpleNamespace(reference_number="AUD-1", status="completed"))
    assert not is_device_queue_run(SimpleNamespace(reference_number="AUD-1", status="cancelled"))
