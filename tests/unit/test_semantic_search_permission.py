"""``GET /api/v1/documents/search/semantic`` requires ``document:read``.

The endpoint took ``CurrentUser`` and checked nothing further, while the two
surfaces either side of it — ``list_documents`` and
``GET /documents/search/content`` — both require ``document:read``. Any
authenticated account could therefore read its tenant's non-restricted library
by phrase, which is the same capability the register list refuses, reached
through the search box instead.

Why the per-hit ACL was not already enough
------------------------------------------
``semantic_search`` resolves every hit through ``_get_document_or_404``, which
calls ``assert_library_read_access``. That is a *classification* check:
``user_can_read_library_document`` returns ``True`` for an ``all_staff``
document without consulting any permission at all, and only ``managers`` and
``restricted`` documents consult one. So the ACL narrowed the leak to the
non-restricted library rather than closing it.

What this is not
----------------
Not a tenancy change. The scoping added in #1517 (B-13) is untouched and is
still pinned by ``tests/unit/test_route_authz_tenant_scope.py``; the tenantless
403 it raises is asserted here only to keep the two 403s distinguishable, so a
future edit cannot delete the permission gate and still look green because the
tenancy guard happened to refuse the same call.

Style follows ``tests/unit/test_register_read_permissions.py`` (C-2): the
behavioural checks drive the mounted router over HTTP, so the assertion is
about the endpoint's real response rather than about ``require_permission`` in
isolation. The existing ``semantic_search`` unit tests call the handler
function directly, which bypasses the dependency graph by design — none of them
prove anything about the gate, and none of them are weakened by it.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import get_current_user
from src.api.routes import documents
from src.domain.authz.catalogue import ADMIN_ROLE_PERMISSIONS, ENFORCED_PERMISSIONS
from src.domain.authz.route_declarations import AUTHENTICATED_ONLY_DEBT, MAX_AUTHENTICATED_ONLY_DEBT
from src.infrastructure.database import get_db

REPO = Path(__file__).resolve().parents[2]

TOKEN = "document:read"
PATH = "/api/v1/documents/search/semantic"
ENDPOINT_KEY = ("GET", "/api/v1/documents/search/semantic")


class _FakeUser:
    """Stands in for an authenticated ``User`` with an exact permission set."""

    def __init__(self, *permissions: str, is_superuser: bool = False, tenant_id: int | None = 7):
        self._permissions = set(permissions)
        self.is_superuser = is_superuser
        self.tenant_id = tenant_id
        self.id = 4242
        self.email = "semantic@test.example.com"

    def has_permission(self, permission: str) -> bool:
        if self.is_superuser:
            return True
        return permission in self._permissions


def _search_db() -> SimpleNamespace:
    """A session that records the search log and finds no row for any hit."""
    return SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
        add=MagicMock(),
        commit=AsyncMock(),
    )


def _client_for(user: _FakeUser, db: SimpleNamespace) -> TestClient:
    """Mount the documents router with authentication faked and the session stubbed.

    Only ``get_current_user`` is overridden, so the real ``permission_checker``
    built by ``require_permission`` still runs and still raises its own 403. A
    fresh app per call keeps the overrides from leaking between tests.
    """
    app = FastAPI()
    app.include_router(documents.router, prefix="/api/v1/documents")

    async def _fake_user() -> _FakeUser:
        return user

    async def _fake_db() -> SimpleNamespace:
        return db

    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    return TestClient(app)


@pytest.fixture
def vector_calls(monkeypatch: pytest.MonkeyPatch) -> list:
    """Patch ``VectorSearchService`` and record every filter it is asked for.

    Recording construction as well as the query matters: a refusal that still
    embeds the phrase has paid for the call it was supposed to prevent.
    """
    calls: list = []

    async def search(query, top_k=10, filter_dict=None):
        calls.append({"query": query, "top_k": top_k, "filter": filter_dict})
        return [{"metadata": {"document_id": 5, "content_preview": "asbestos survey"}, "score": 0.91}]

    def factory():
        calls.append("constructed")
        return SimpleNamespace(search=AsyncMock(side_effect=search))

    monkeypatch.setattr(documents, "VectorSearchService", factory)
    return calls


@pytest.fixture
def resolved_document(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let the single vector hit resolve to a visible row."""

    async def _get_document(db, doc_id, user, **kwargs):
        return SimpleNamespace(id=doc_id, title="Asbestos Survey", reference_number="DOC-5", tenant_id=7)

    monkeypatch.setattr(documents, "_get_document_or_404", _get_document)


# --------------------------------------------------------------------------- #
# The gate, over HTTP, in both directions
# --------------------------------------------------------------------------- #


def test_semantic_search_is_refused_without_the_read_permission(vector_calls) -> None:
    """A caller holding every *other* enforced permission is still refused."""
    other_tokens = sorted(ENFORCED_PERMISSIONS - {TOKEN})
    db = _search_db()
    client = _client_for(_FakeUser(*other_tokens), db)

    response = client.get(PATH, params={"q": "asbestos survey"})

    assert response.status_code == 403, f"GET {PATH} returned {response.status_code} without {TOKEN}"
    # Assert on the reason, not just the code: require_tenant_id raises 403 from
    # inside this handler too, so a bare status check could pass while the
    # permission gate was absent.
    assert (
        response.json()["detail"] == f"Permission '{TOKEN}' required"
    ), f"GET {PATH} was refused, but not by the permission gate. Detail was: {response.json()['detail']!r}"


def test_a_refused_caller_never_reaches_the_vector_store(vector_calls) -> None:
    """The refusal must precede the embedding call, which is billed per request."""
    db = _search_db()
    client = _client_for(_FakeUser("incident:read"), db)

    response = client.get(PATH, params={"q": "asbestos survey"})

    assert response.status_code == 403
    assert vector_calls == [], "a caller without document:read reached the vector store"
    db.execute.assert_not_awaited()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


def test_semantic_search_is_served_with_the_read_permission(vector_calls, resolved_document) -> None:
    """The token alone is sufficient, and the caller gets real results, not an empty 200."""
    db = _search_db()
    client = _client_for(_FakeUser(TOKEN), db)

    response = client.get(PATH, params={"q": "asbestos survey"})

    assert response.status_code == 200, f"GET {PATH} returned {response.status_code} with {TOKEN}"
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["document_id"] == 5
    assert body["results"][0]["chunk_preview"] == "asbestos survey"
    assert {"query": "asbestos survey", "top_k": 10, "filter": {"tenant_id": {"$eq": 7}}} in vector_calls


def test_semantic_search_is_served_for_a_superuser_holding_no_explicit_grant(vector_calls, resolved_document) -> None:
    """``has_permission`` short-circuits for a superuser before it reads any role.

    A superuser therefore needs no ``document:read`` row to pass the new gate,
    which is what keeps this change from being an outage for the account that
    administers the platform. It buys no cross-tenant reach: the B-13 filter
    below still binds the superuser's own tenant.
    """
    db = _search_db()
    client = _client_for(_FakeUser(is_superuser=True, tenant_id=7), db)

    response = client.get(PATH, params={"q": "asbestos survey"})

    assert response.status_code == 200
    assert {"query": "asbestos survey", "top_k": 10, "filter": {"tenant_id": {"$eq": 7}}} in vector_calls


def test_a_tenantless_caller_with_the_permission_still_gets_the_tenancy_403(vector_calls) -> None:
    """#1517 is unchanged: holding the token does not buy an unscoped search."""
    db = _search_db()
    client = _client_for(_FakeUser(TOKEN, tenant_id=None), db)

    response = client.get(PATH, params={"q": "asbestos survey"})

    assert response.status_code == 403
    assert response.json()["detail"] != f"Permission '{TOKEN}' required", (
        "the tenancy guard and the permission gate returned the same detail; the two 403s must stay "
        "distinguishable or a test can no longer tell which one refused"
    )
    assert vector_calls == [], "a tenantless caller must not reach the vector store"


# --------------------------------------------------------------------------- #
# Static guardrails: the dependency is on the handler, and the declaration agrees
# --------------------------------------------------------------------------- #


def test_semantic_search_declares_the_read_dependency() -> None:
    assert f'require_permission("{TOKEN}")' in inspect.getsource(documents.semantic_search)


def test_the_sibling_search_surface_still_requires_the_same_token() -> None:
    """Guardrail: the fix is to match the sibling, not to move the gap around."""
    assert f'require_permission("{TOKEN}")' in inspect.getsource(documents.search_document_content)
    assert f'require_permission("{TOKEN}")' in inspect.getsource(documents.list_documents)


def test_the_route_is_no_longer_declared_as_authenticated_only_debt() -> None:
    """A stale debt entry is an exemption nobody checks; the ceiling must fall with it.

    ``tests/integration/test_route_authorisation_census.py`` enforces this
    against the mounted app. Repeating the declaration side here keeps the unit
    suite able to catch the half-done change — route gated, list not updated —
    without importing ``src.main``.
    """
    assert ENDPOINT_KEY not in AUTHENTICATED_ONLY_DEBT, (
        "the route is gated but still declared as authenticated-only debt. The declaration must "
        "come out in the same change, or the list claims a gap that no longer exists."
    )
    # Deliberately `<=`, matching the census test's own invariant. Pinning
    # equality here would fail a later change that closes a different gap, for
    # a reason having nothing to do with this endpoint.
    assert len(AUTHENTICATED_ONLY_DEBT) <= MAX_AUTHENTICATED_ONLY_DEBT


def test_the_gating_token_is_in_the_admin_grant() -> None:
    """Gating on a token the admin role does not hold is an outage, not a fix.

    ``document:read`` was already enforced on ``list_documents`` and
    ``search_document_content``, so this asserts a fact rather than requiring a
    grant change: nobody who can reach the library today loses semantic search.
    """
    assert TOKEN in ENFORCED_PERMISSIONS
    assert TOKEN in ADMIN_ROLE_PERMISSIONS


def test_the_tenancy_scoping_from_1517_is_still_in_the_handler() -> None:
    """The permission gate is added to the tenancy fix, not instead of it."""
    source = inspect.getsource(documents.semantic_search)
    assert "require_tenant_id" in source
    assert "allow_superuser_cross_tenant=False" in source
    tree = ast.parse(source)
    guarded = [node for node in ast.walk(tree) if isinstance(node, (ast.Try, ast.If, ast.For))]
    assert not any("require_tenant_id" in ast.dump(node) for node in guarded)
