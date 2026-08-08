"""C-2: register collection lists require a read permission.

These endpoints previously took ``CurrentUser`` and nothing else, so any
authenticated account in a tenant could read the whole register. They now use
the same ``require_permission(...)`` dependency their sibling write routes in
the same modules already use.

Sequencing
----------
``action:read`` and ``risk:read`` were promoted from ``RESERVED_PERMISSIONS``
into ``ENFORCED_PERMISSIONS`` in the same change that gates their lists, which
grows ``ADMIN_ROLE_PERMISSIONS`` 75→77. Live databases still hold the 75-token
grant until a human applies the upgrade in
``docs/data/admin-role-permissions-grant.md``. Merging the gate before that
upgrade 403s non-superuser admins out of the actions and operational-risk
registers. ``test_newly_gated_tokens_are_in_the_admin_grant`` holds the
catalogue side of that line; applying the grant is an ops step, not a merge.

Style follows ``tests/unit/test_case_view_permissions.py`` (SEC-02). The
behavioural checks drive the mounted router over HTTP so the assertion is about
the endpoint's real response, not only about the ``require_permission`` factory
in isolation.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.dependencies import get_current_user, require_permission
from src.api.routes import actions, documents, risks, rtas
from src.domain.authz.catalogue import ADMIN_ROLE_PERMISSIONS, ENFORCED_PERMISSIONS
from src.infrastructure.database import get_db

REPO = Path(__file__).resolve().parents[2]

#: The registers this change gates, with the token each is gated on.
GATED_REGISTERS = {
    "rta:read": ("/api/v1/rtas/",),
    # list_documents / list_actions / list_risks carry both @router.get("") and
    # @router.get("/"), so the app serves each on two paths.
    "document:read": ("/api/v1/documents", "/api/v1/documents/"),
    "action:read": ("/api/v1/actions", "/api/v1/actions/"),
    "risk:read": ("/api/v1/risks", "/api/v1/risks/"),
}


class _FakeUser:
    """Stands in for an authenticated ``User`` with an exact permission set."""

    def __init__(self, *permissions: str, is_superuser: bool = False, tenant_id: int | None = 1):
        self._permissions = set(permissions)
        self.is_superuser = is_superuser
        self.tenant_id = tenant_id
        self.id = 4242
        self.email = "gated@test.example.com"

    def has_permission(self, permission: str) -> bool:
        if self.is_superuser:
            return True
        return permission in self._permissions


class _EmptyResult:
    """Enough of a SQLAlchemy ``Result`` for a list handler that finds no rows."""

    def scalar(self) -> int:
        return 0

    def scalars(self) -> "_EmptyResult":
        return self

    def all(self) -> list:
        return []


class _EmptySession:
    """A session that answers every query with nothing.

    The list handlers are being driven for their authorisation behaviour, not
    their SQL, so an empty result is all that is needed for the allowed case to
    reach a real 200 through the response model.
    """

    async def execute(self, *_args, **_kwargs) -> _EmptyResult:
        return _EmptyResult()

    async def scalar(self, *_args, **_kwargs) -> int:
        return 0


def _client_for(user: _FakeUser) -> TestClient:
    """Mount the gated registers with authentication faked and the database emptied.

    Only ``get_current_user`` is overridden, so the real ``permission_checker``
    built by ``require_permission`` still runs and still raises its own 403. A
    fresh app per call keeps the overrides from leaking between tests.
    """
    app = FastAPI()
    app.include_router(rtas.router, prefix="/api/v1/rtas")
    app.include_router(documents.router, prefix="/api/v1/documents")
    app.include_router(actions.router, prefix="/api/v1/actions")
    app.include_router(risks.router, prefix="/api/v1/risks")

    async def _fake_user() -> _FakeUser:
        return user

    async def _fake_db() -> _EmptySession:
        return _EmptySession()

    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    return TestClient(app)


@pytest.fixture
def client_factory():
    return _client_for


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


# --------------------------------------------------------------------------- #
# The gate, over HTTP, in both directions
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "token,path",
    [(token, path) for token, paths in GATED_REGISTERS.items() for path in paths],
)
def test_register_list_is_refused_without_the_read_permission(client_factory, token, path):
    """A user holding every *other* permission still cannot read the register."""
    other_tokens = sorted(ENFORCED_PERMISSIONS - {token})
    client = client_factory(_FakeUser(*other_tokens))

    response = client.get(path)

    assert response.status_code == 403, f"GET {path} returned {response.status_code} without {token}"
    # Assert on the reason, not just the code: require_tenant_id also raises 403
    # from inside these handlers, so a bare status check could pass while the
    # permission gate was absent.
    assert (
        response.json()["detail"] == f"Permission '{token}' required"
    ), f"GET {path} was refused, but not by the permission gate. Detail was: {response.json()['detail']!r}"


@pytest.mark.parametrize(
    "token,path",
    [(token, path) for token, paths in GATED_REGISTERS.items() for path in paths],
)
def test_register_list_is_served_with_the_read_permission(client_factory, token, path):
    """The token alone is sufficient: no other permission is needed to read."""
    client = client_factory(_FakeUser(token))

    response = client.get(path)

    assert response.status_code == 200, f"GET {path} returned {response.status_code} with {token}"
    assert response.json()["items"] == []


@pytest.mark.parametrize(
    "token,path",
    [(token, path) for token, paths in GATED_REGISTERS.items() for path in paths],
)
def test_register_list_is_served_for_a_superuser(client_factory, token, path):
    """``has_permission`` short-circuits for a superuser before reading roles."""
    client = client_factory(_FakeUser(is_superuser=True))

    response = client.get(path)

    assert response.status_code == 200


# --------------------------------------------------------------------------- #
# The trap: never gate on a token the admin role does not hold
# --------------------------------------------------------------------------- #


def test_newly_gated_tokens_are_in_the_admin_grant():
    """Gating on a token outside the admin grant is an outage, not a fix.

    ``User.has_permission`` does exact set-membership with no glob expansion, so
    a register gated on a token the admin role was never granted returns 403 to
    administrators. Live DBs must receive the 84-token grant before this PR merges.
    """
    for token in GATED_REGISTERS:
        assert token in ENFORCED_PERMISSIONS, f"{token} is gating a route but is not catalogued as enforced"
        assert token in ADMIN_ROLE_PERMISSIONS, (
            f"{token} now gates a register list, but it is not in the admin grant "
            f"(ADMIN_ROLE_PERMISSIONS, {len(ADMIN_ROLE_PERMISSIONS)} tokens). Administrators would "
            "get 403 on that register. Add the token to the grant and apply it to roles.permissions "
            "before enforcing it, not after."
        )
    assert len(ADMIN_ROLE_PERMISSIONS) == 84
    assert "action:delete" in ADMIN_ROLE_PERMISSIONS
    assert "action:read" in ADMIN_ROLE_PERMISSIONS
    assert "risk:read" in ADMIN_ROLE_PERMISSIONS
    assert "job:read" in ADMIN_ROLE_PERMISSIONS
    assert "job:author" in ADMIN_ROLE_PERMISSIONS


# --------------------------------------------------------------------------- #
# Static guardrails: the dependency is on the handler, not merely importable.
# Mirrors tests/unit/test_case_view_permissions.py.
# --------------------------------------------------------------------------- #


def test_rta_list_declares_the_read_dependency():
    assert "rta:read" in _permission_depends(REPO / "src/api/routes/rtas.py")
    assert 'require_permission("rta:read")' in inspect.getsource(rtas.list_rtas)


def test_document_list_declares_the_read_dependency():
    assert "document:read" in _permission_depends(REPO / "src/api/routes/documents.py")
    assert 'require_permission("document:read")' in inspect.getsource(documents.list_documents)


def test_actions_list_declares_the_read_dependency():
    assert "action:read" in _permission_depends(REPO / "src/api/routes/actions.py")
    assert 'require_permission("action:read")' in inspect.getsource(actions.list_actions)


def test_risks_list_declares_the_read_dependency():
    assert "risk:read" in _permission_depends(REPO / "src/api/routes/risks.py")
    assert 'require_permission("risk:read")' in inspect.getsource(risks.list_risks)


def test_write_routes_are_untouched_by_this_change():
    """Guardrail: C-2 is read-side only; the write gates must be unchanged."""
    rta_perms = _permission_depends(REPO / "src/api/routes/rtas.py")
    assert {"rta:create", "rta:update", "rta:delete"} <= rta_perms

    document_perms = _permission_depends(REPO / "src/api/routes/documents.py")
    assert {"document:create", "document:update"} <= document_perms

    action_perms = _permission_depends(REPO / "src/api/routes/actions.py")
    assert {"action:create", "action:update"} <= action_perms

    risk_perms = _permission_depends(REPO / "src/api/routes/risks.py")
    assert {"risk:create", "risk:update"} <= risk_perms


@pytest.mark.asyncio
@pytest.mark.parametrize("token", sorted(GATED_REGISTERS))
async def test_the_checker_itself_fails_closed(token):
    """The dependency raises 403 rather than returning a falsey user."""
    checker = require_permission(token)

    with pytest.raises(HTTPException) as exc:
        await checker(current_user=_FakeUser("something:else"))

    assert exc.value.status_code == 403

    permitted = _FakeUser(token)
    assert await checker(current_user=permitted) is permitted
