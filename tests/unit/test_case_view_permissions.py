"""SEC-02: incident / near_miss / complaint read endpoints require a view permission.

Wave 0 H&S rich reporting hardening: list/get/detail read endpoints for these
three case types previously only required authentication (``CurrentUser``),
letting any authenticated user in a tenant browse every case regardless of
role. They now mirror the existing ``require_permission(...)`` decorator
style already used for write routes, gated on ``<entity>:read`` — the
permission suffix already established elsewhere in the codebase (e.g.
``audit:read`` in ``src/api/routes/audit_trail.py``, and the ``incident:read`` /
``near_miss:read`` / ``complaint:read`` grants baked into the integration and
e2e test fixtures) rather than inventing a new ``:view`` suffix.

Write routes (create/update/delete) are intentionally untouched and are
covered by ``tests/unit/test_require_permission_modules.py``.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.dependencies import require_permission
from src.api.routes import complaints, incidents, near_miss

REPO = Path(__file__).resolve().parents[2]


def _permission_depends(path: Path) -> set[str]:
    """Collect literal string args passed to ``require_permission(...)`` calls."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_require_permission = (isinstance(func, ast.Name) and func.id == "require_permission") or (
            isinstance(func, ast.Attribute) and func.attr == "require_permission"
        )
        if is_require_permission and node.args and isinstance(node.args[0], ast.Constant):
            if isinstance(node.args[0].value, str):
                found.add(node.args[0].value)
    return found


class _FakeUser:
    def __init__(self, permission: str | None = None, is_superuser: bool = False):
        self._permission = permission
        self.is_superuser = is_superuser

    def has_permission(self, permission: str) -> bool:
        if self.is_superuser:
            return True
        return permission == self._permission


# ---------------------------------------------------------------------------
# Behavioral: require_permission("<entity>:read") is the exact dependency
# wired onto read routes and it fails closed with 403.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("permission", ["incident:read", "near_miss:read", "complaint:read"])
async def test_read_permission_denies_user_without_it(permission):
    checker = require_permission(permission)
    user_without_permission = _FakeUser(permission="something:else")

    with pytest.raises(HTTPException) as exc:
        await checker(current_user=user_without_permission)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("permission", ["incident:read", "near_miss:read", "complaint:read"])
async def test_read_permission_allows_user_with_it(permission):
    checker = require_permission(permission)
    user_with_permission = _FakeUser(permission=permission)

    result = await checker(current_user=user_with_permission)

    assert result is user_with_permission


@pytest.mark.asyncio
@pytest.mark.parametrize("permission", ["incident:read", "near_miss:read", "complaint:read"])
async def test_read_permission_allows_superuser_regardless_of_granted_permissions(permission):
    checker = require_permission(permission)
    superuser = _FakeUser(permission=None, is_superuser=True)

    result = await checker(current_user=superuser)

    assert result is superuser


# ---------------------------------------------------------------------------
# Static guardrails: the read endpoints actually declare the dependency.
# Mirrors the existing write-route guardrail in test_require_permission_modules.py.
# ---------------------------------------------------------------------------


def test_incident_read_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/incidents.py")
    assert "incident:read" in perms

    for fn in (
        incidents.get_incident,
        incidents.list_incidents,
        incidents.list_incident_investigations,
        incidents.list_incident_running_sheet_entries,
    ):
        assert 'require_permission("incident:read")' in inspect.getsource(fn), fn.__name__


def test_near_miss_read_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/near_miss.py")
    assert "near_miss:read" in perms

    for fn in (
        near_miss.list_near_misses,
        near_miss.get_near_miss,
        near_miss.list_near_miss_investigations,
        near_miss.list_near_miss_running_sheet_entries,
    ):
        assert 'require_permission("near_miss:read")' in inspect.getsource(fn), fn.__name__


def test_complaint_read_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/complaints.py")
    assert "complaint:read" in perms

    for fn in (
        complaints.get_complaint,
        complaints.list_complaints,
        complaints.list_complaint_investigations,
        complaints.list_complaint_running_sheet_entries,
    ):
        assert 'require_permission("complaint:read")' in inspect.getsource(fn), fn.__name__


def test_write_routes_are_untouched_by_this_wave():
    """Guardrail: this lane only adds read gating; write permissions must be unchanged."""
    incident_perms = _permission_depends(REPO / "src/api/routes/incidents.py")
    assert {"incident:create", "incident:update", "incident:delete"} <= incident_perms

    near_miss_perms = _permission_depends(REPO / "src/api/routes/near_miss.py")
    assert {"near_miss:create", "near_miss:update"} <= near_miss_perms

    complaint_perms = _permission_depends(REPO / "src/api/routes/complaints.py")
    assert {"complaint:create", "complaint:update"} <= complaint_perms


# ---------------------------------------------------------------------------
# Cross-tenant denial stays intact independent of the new permission gate:
# a user with the right permission but wrong tenant still gets a clean 404.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_incident_with_permission_still_denies_cross_tenant():
    from unittest.mock import AsyncMock

    from src.domain.exceptions import NotFoundError

    svc = SimpleNamespace(get_incident=AsyncMock(side_effect=LookupError("Incident 501 not found")))
    original = incidents.IncidentService
    incidents.IncidentService = lambda db: svc
    try:
        user = SimpleNamespace(id=1, tenant_id=23, is_superuser=False)
        with pytest.raises(NotFoundError):
            await incidents.get_incident(incident_id=501, db=SimpleNamespace(), current_user=user)
    finally:
        incidents.IncidentService = original
