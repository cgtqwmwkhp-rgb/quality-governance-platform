"""AUD-DEV-3 catalogue caller gate."""

from types import SimpleNamespace

from src.domain.services.audit_catalogue_access import is_audit_catalogue_caller


def test_field_worker_cannot_list_organisation_runs():
    user = SimpleNamespace(is_superuser=False, roles=[], has_permission=lambda _p: False)
    assert is_audit_catalogue_caller(user) is False


def test_supervisor_role_and_audit_read_can_list():
    supervisor = SimpleNamespace(
        is_superuser=False,
        roles=[SimpleNamespace(name="supervisor")],
        has_permission=lambda _p: False,
    )
    reader = SimpleNamespace(
        is_superuser=False,
        roles=[],
        has_permission=lambda p: p == "audit:read",
    )
    superuser = SimpleNamespace(is_superuser=True, roles=[], has_permission=lambda _p: False)
    assert is_audit_catalogue_caller(supervisor) is True
    assert is_audit_catalogue_caller(reader) is True
    assert is_audit_catalogue_caller(superuser) is True
