"""AUD-DEV-3: senior list is whole-tenant; field workers keep 200 on own runs."""

from types import SimpleNamespace

from src.domain.services.audit_catalogue_access import effective_assigned_to_filter, is_audit_senior


def test_field_worker_is_not_senior_and_is_forced_to_self():
    user = SimpleNamespace(id=7, is_superuser=False, roles=[])
    assert is_audit_senior(user) is False
    assert effective_assigned_to_filter(user, 99) == 7
    assert effective_assigned_to_filter(user, None) == 7


def test_supervisor_and_superuser_honour_requested_assignee():
    supervisor = SimpleNamespace(
        id=3,
        is_superuser=False,
        roles=[SimpleNamespace(name="supervisor")],
    )
    superuser = SimpleNamespace(id=1, is_superuser=True, roles=[])
    assert is_audit_senior(supervisor) is True
    assert is_audit_senior(superuser) is True
    assert effective_assigned_to_filter(supervisor, 99) == 99
    assert effective_assigned_to_filter(supervisor, None) is None
    assert effective_assigned_to_filter(superuser, None) is None
