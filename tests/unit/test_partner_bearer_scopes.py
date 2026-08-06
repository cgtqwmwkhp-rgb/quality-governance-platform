"""Inbound partner bearer auth: the scope allowlist, and the gates on real routes.

Why these drive the mounted routers
-----------------------------------
The first version of this change was proved by a synthetic app with two
hand-written endpoints. Every one of those assertions passed while the four
endpoints the integration actually calls returned 401 to a valid session user,
because the change had taken ``get_current_user`` out of their dependency graphs.
A test that mounts its own routes cannot notice that. So the gate assertions here
mount ``documents.router`` and ``global_search.router`` and go over HTTP against
the real paths.

``tests/unit/test_semantic_search_permission.py`` is the other half of this and is
deliberately untouched: it pins that a *session* caller still needs
``document:read`` on the same endpoints. Partner support had to be additive
enough to leave it passing as written.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies.partner import (
    PARTNER_SCOPE_OPENAPI_KEY,
    is_partner_caller,
    partner_readable,
    required_partner_scope,
)
from src.api.routes import documents, global_search
from src.domain.models.partner_api_token import (
    PARTNER_API_SCOPES,
    PARTNER_SCOPE_TO_PERMISSIONS,
    PartnerApiToken,
)
from src.domain.services.partner_auth_service import (
    PartnerAuthService,
    PartnerPrincipal,
    generate_partner_token,
    is_partner_bearer_token,
    partner_effective_permissions,
)
from src.domain.services.search_service import PARTNER_VISIBLE_MODULES, SearchService
from src.infrastructure.database import get_db

TENANT_ID = 99


# --------------------------------------------------------------------------- #
# The scope allowlist and what each scope actually grants
# --------------------------------------------------------------------------- #


def test_the_new_scopes_are_allowlisted_and_the_old_ones_kept() -> None:
    """Additive: an existing token's scopes must still be mintable."""
    assert "documents:read" in PARTNER_API_SCOPES
    assert "search:read" in PARTNER_API_SCOPES
    assert "webhooks:manage" in PARTNER_API_SCOPES
    assert "inspections:read" in PARTNER_API_SCOPES


def test_only_documents_read_maps_onto_an_rbac_permission() -> None:
    """A scope absent from the mapping must grant no platform permission.

    ``search:read`` gates the routes that name it and nothing else, and
    ``policies:read`` is allowlisted for a surface that does not exist yet.
    Mapping either onto an RBAC token would grant it on every route that already
    checks that token, which is the whole estate rather than an opt-in.
    """
    assert PARTNER_SCOPE_TO_PERMISSIONS["documents:read"] == frozenset({"document:read"})
    assert "search:read" not in PARTNER_SCOPE_TO_PERMISSIONS
    assert "policies:read" not in PARTNER_SCOPE_TO_PERMISSIONS
    assert partner_effective_permissions(["search:read", "policies:read"]) == frozenset()
    assert partner_effective_permissions(["documents:read", "search:read"]) == frozenset({"document:read"})


def test_is_partner_bearer_token() -> None:
    assert is_partner_bearer_token("qgp_pt_abc") is True
    assert is_partner_bearer_token("eyJhbGciOi") is False
    assert is_partner_bearer_token("") is False


# --------------------------------------------------------------------------- #
# The principal
# --------------------------------------------------------------------------- #


def _token(*, scopes: list[str], token_id: int = 42) -> tuple[PartnerApiToken, str]:
    raw_token, secret_hash, prefix = generate_partner_token()
    token = PartnerApiToken(
        id=token_id,
        tenant_id=TENANT_ID,
        name="CRM Bid Writer",
        token_prefix=prefix,
        secret_hash=secret_hash,
        scopes=scopes,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return token, raw_token


def test_principal_carries_the_tokens_tenant_and_no_user_identity() -> None:
    principal = PartnerPrincipal(_token(scopes=["documents:read", "search:read"])[0])

    assert principal.tenant_id == TENANT_ID
    assert principal.id is None, "a partner caller must not claim a user id in the audit trail"
    assert principal.is_superuser is False
    assert principal.is_active is True
    assert principal.has_partner_scope("documents:read") is True
    assert principal.has_partner_scope("webhooks:manage") is False


def test_principal_permissions_come_only_from_its_scopes() -> None:
    principal = PartnerPrincipal(_token(scopes=["documents:read"])[0])

    assert principal.has_permission("document:read") is True
    # The tokens that open the managers/restricted tiers of the library, and the
    # one that opens everything. All must stay shut.
    assert principal.has_permission("document:update") is False
    assert principal.has_permission("admin:manage") is False


def test_a_search_only_principal_holds_no_permission_at_all() -> None:
    principal = PartnerPrincipal(_token(scopes=["search:read"])[0])

    assert principal.has_permission("document:read") is False
    assert principal.partner_scopes == frozenset({"search:read"})


def test_the_principal_refuses_to_impersonate_a_user_row() -> None:
    """``__slots__`` makes an unconsidered attribute raise instead of lying."""
    principal = PartnerPrincipal(_token(scopes=["documents:read"])[0])

    with pytest.raises(AttributeError):
        _ = principal.hashed_password  # type: ignore[attr-defined]
    assert principal.email.endswith("@qgp.invalid"), "a partner email must never be deliverable"


def test_is_partner_caller_distinguishes_the_two_kinds_of_caller() -> None:
    assert is_partner_caller(PartnerPrincipal(_token(scopes=["search:read"])[0])) is True
    assert is_partner_caller(SimpleNamespace(id=1, tenant_id=TENANT_ID, is_superuser=False)) is False


# --------------------------------------------------------------------------- #
# Token verification
# --------------------------------------------------------------------------- #


def _db(token: Optional[PartnerApiToken] = None) -> SimpleNamespace:
    """A session that answers the token lookup and records what it was asked.

    The candidate lookup filters ``is_active`` in SQL, so this stub honours that
    predicate rather than handing back every row. Otherwise the revocation test
    below would pass because the token was never found at all, which is a
    different fact and a worthless assertion.
    """
    statements: list[Any] = []
    candidates = [token] if token is not None and token.is_active else []

    class _Result:
        def scalars(self) -> SimpleNamespace:
            return SimpleNamespace(all=lambda: list(candidates))

        def scalar_one_or_none(self) -> None:
            return None

    async def execute(statement: Any, *args: Any, **kwargs: Any) -> _Result:
        statements.append(statement)
        return _Result()

    return SimpleNamespace(
        execute=execute,
        statements=statements,
        add=MagicMock(),
        commit=AsyncMock(),
        flush=AsyncMock(),
        # Keeps apply_tenant_guc on its non-PostgreSQL no-op path.
        get_bind=MagicMock(return_value=SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))),
    )


@pytest.mark.asyncio
async def test_authenticate_accepts_a_valid_active_token_without_writing() -> None:
    token, raw = _token(scopes=["documents:read"])
    db = _db(token)

    matched = await PartnerAuthService(db).authenticate(raw)

    assert matched is token
    db.flush.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_authenticate_only_considers_active_tokens() -> None:
    """Revocation clears ``is_active``, so the predicate is the revocation check."""
    token, raw = _token(scopes=["documents:read"])
    db = _db(token)

    await PartnerAuthService(db).authenticate(raw)

    compiled = str(db.statements[0]).lower()
    assert "is_active" in compiled, "the candidate lookup no longer filters revoked tokens"
    assert "token_prefix" in compiled


@pytest.mark.asyncio
async def test_authenticate_refuses_a_prefix_match_with_the_wrong_secret() -> None:
    """A colliding prefix must be decided by the hash, not by the prefix."""
    token, raw = _token(scopes=["documents:read"])
    forged = f"{raw[:16]}_not_the_real_secret"
    db = _db(token)

    assert await PartnerAuthService(db).authenticate(forged) is None


@pytest.mark.asyncio
async def test_authenticate_does_not_query_for_a_non_partner_credential() -> None:
    db = _db()

    assert await PartnerAuthService(db).authenticate("eyJhbGciOiJIUzI1NiJ9.x.y") is None
    assert db.statements == []


# --------------------------------------------------------------------------- #
# The route opt-in marker
# --------------------------------------------------------------------------- #


#: Every route a partner token can reach, and the scope it needs. This is the
#: authorisation decision for the inbound API, so it is pinned exhaustively: a
#: sixth route cannot be opened without editing this list.
EXPECTED_PARTNER_ROUTES = {
    ("GET", "/api/v1/search", "search:read"),
    ("GET", "/api/v1/search/", "search:read"),
    ("GET", "/api/v1/documents/{document_id}", "documents:read"),
    ("GET", "/api/v1/documents/{document_id}/signed-url", "documents:read"),
    ("GET", "/api/v1/documents/search/content", "documents:read"),
    ("GET", "/api/v1/documents/search/semantic", "documents:read"),
}


def _marked_routes(node: Any, seen: Optional[set] = None) -> set:
    found: set = set()
    seen = seen if seen is not None else set()
    if id(node) in seen:
        return found
    seen.add(id(node))
    extra = getattr(node, "openapi_extra", None)
    if isinstance(extra, dict) and PARTNER_SCOPE_OPENAPI_KEY in extra:
        for method in sorted(getattr(node, "methods", None) or ()):
            found.add((method, getattr(node, "path", "?"), extra[PARTNER_SCOPE_OPENAPI_KEY]))
    for child in getattr(node, "routes", None) or ():
        found |= _marked_routes(child, seen)
    for attribute in ("original_router", "original_route", "app"):
        nested = getattr(node, attribute, None)
        if nested is not None:
            found |= _marked_routes(nested, seen)
    return found


def test_exactly_the_intended_routes_accept_a_partner_token() -> None:
    from src.main import app

    assert _marked_routes(app) == EXPECTED_PARTNER_ROUTES


def test_the_interpret_endpoint_is_not_partner_callable() -> None:
    """It is a POST that bills an LLM call, and the integration does not need it."""
    marked_paths = {path for _, path, _ in EXPECTED_PARTNER_ROUTES}
    assert "/api/v1/search/interpret" not in marked_paths


@pytest.mark.asyncio
async def test_an_unmarked_route_yields_no_scope_so_the_token_is_refused() -> None:
    """``required_partner_scope`` is the default-deny, and ``None`` is how it denies."""
    unmarked = SimpleNamespace(openapi_extra=None)
    marked = SimpleNamespace(openapi_extra=partner_readable("documents:read"))

    assert await required_partner_scope(SimpleNamespace(scope={})) is None
    assert await required_partner_scope(SimpleNamespace(scope={"route": unmarked})) is None
    assert await required_partner_scope(SimpleNamespace(scope={"route": marked})) == "documents:read"


# --------------------------------------------------------------------------- #
# The gates, over HTTP, on the real routes
# --------------------------------------------------------------------------- #


def _client(token: Optional[PartnerApiToken]) -> TestClient:
    """Mount the real routers with only the DB session stubbed."""
    app = FastAPI()
    app.include_router(documents.router, prefix="/api/v1/documents")
    app.include_router(global_search.router, prefix="/api/v1/search")

    db = _db(token)

    async def _fake_db() -> Any:
        return db

    app.dependency_overrides[get_db] = _fake_db
    return TestClient(app)


def _auth(raw: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw}"}


@pytest.fixture
def served_semantic_search(monkeypatch: pytest.MonkeyPatch) -> list:
    """Let semantic search complete, recording the tenant filter it asked for."""
    calls: list = []

    async def search(query: str, top_k: int = 10, filter_dict: Any = None) -> list:
        calls.append(filter_dict)
        return [{"metadata": {"document_id": 5, "content_preview": "asbestos survey"}, "score": 0.9}]

    monkeypatch.setattr(documents, "VectorSearchService", lambda: SimpleNamespace(search=AsyncMock(side_effect=search)))

    async def _get_document(db: Any, doc_id: int, user: Any, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(id=doc_id, title="Asbestos Survey", reference_number="DOC-5", tenant_id=TENANT_ID)

    monkeypatch.setattr(documents, "_get_document_or_404", _get_document)
    return calls


SEMANTIC = "/api/v1/documents/search/semantic"


def test_a_partner_token_with_the_scope_is_served(served_semantic_search) -> None:
    token, raw = _token(scopes=["documents:read"])

    response = _client(token).get(SEMANTIC, params={"q": "asbestos survey"}, headers=_auth(raw))

    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["document_id"] == 5


def test_the_vector_filter_is_scoped_to_the_tokens_tenant(served_semantic_search) -> None:
    """Tenant isolation for a partner caller rests on the token row.

    The filter is the only thing that stops another tenant's chunk text being
    returned as a preview, because the vector store — not the database — is the
    source of those strings.
    """
    token, raw = _token(scopes=["documents:read"])

    response = _client(token).get(SEMANTIC, params={"q": "asbestos survey"}, headers=_auth(raw))

    assert response.status_code == 200, response.text
    assert served_semantic_search == [{"tenant_id": {"$eq": TENANT_ID}}]


def test_a_partner_token_without_the_scope_is_refused_with_403(served_semantic_search) -> None:
    token, raw = _token(scopes=["search:read"])

    response = _client(token).get(SEMANTIC, params={"q": "asbestos survey"}, headers=_auth(raw))

    assert response.status_code == 403
    assert response.json()["detail"] == "Partner scope 'documents:read' required"
    assert served_semantic_search == [], "a refused caller must not reach the billed vector store"


def test_an_unknown_partner_token_is_refused_with_401(served_semantic_search) -> None:
    _, raw = _token(scopes=["documents:read"])

    response = _client(None).get(SEMANTIC, params={"q": "asbestos survey"}, headers=_auth(raw))

    assert response.status_code == 401
    assert served_semantic_search == []


def test_a_revoked_token_is_refused_with_401(served_semantic_search) -> None:
    """``is_active`` false is what revocation leaves behind, and it must fail closed.

    The row is present and its secret still verifies — only ``is_active`` has
    changed, which is exactly the state ``revoke_token`` leaves.
    """
    token, raw = _token(scopes=["documents:read"])
    token.is_active = False

    response = _client(token).get(SEMANTIC, params={"q": "asbestos survey"}, headers=_auth(raw))

    assert response.status_code == 401
    assert served_semantic_search == []


def test_a_partner_token_is_refused_on_a_route_that_did_not_opt_in() -> None:
    """The default-deny: ``documents:read`` does not open the library list.

    ``GET /api/v1/documents/`` requires the same ``document:read`` the marked
    search endpoints do, so this is the assertion that the opt-in — and not the
    scope-to-permission mapping — is what decides reachability.
    """
    token, raw = _token(scopes=["documents:read", "search:read", "policies:read"])

    response = _client(token).get("/api/v1/documents/", headers=_auth(raw))

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_a_bare_prefix_with_no_secret_is_refused() -> None:
    """The prefix alone is not a credential; only the hash comparison decides."""
    response = _client(None).get(SEMANTIC, params={"q": "asbestos"}, headers=_auth("qgp_pt_"))

    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# Global search: a partner reaches the document modules only
# --------------------------------------------------------------------------- #

_MODULE_SEARCHES = (
    "_search_incidents",
    "_search_near_misses",
    "_search_rtas",
    "_search_complaints",
    "_search_risks",
    "_search_audits",
    "_search_actions",
    "_search_documents",
    "_search_document_content",
    "_search_compliance_requirements",
)


def _recording_service() -> tuple[SearchService, list[str]]:
    service = SearchService(_db())
    called: list[str] = []

    def recorder(name: str):
        async def _run(*args: Any, **kwargs: Any) -> list:
            called.append(name)
            return []

        return _run

    for name in _MODULE_SEARCHES:
        setattr(service, name, recorder(name))
    return service, called


@pytest.mark.asyncio
async def test_a_partner_search_never_queries_the_confidential_registers() -> None:
    """Not filtered afterwards — not queried at all."""
    service, called = _recording_service()

    await service.search(
        query="fire risk",
        tenant_id=TENANT_ID,
        user=PartnerPrincipal(_token(scopes=["search:read"])[0]),
        allowed_modules=PARTNER_VISIBLE_MODULES,
    )

    assert called == ["_search_documents", "_search_document_content"]


@pytest.mark.asyncio
async def test_a_session_callers_search_is_unchanged() -> None:
    """``allowed_modules=None`` is the default and must search everything."""
    service, called = _recording_service()

    await service.search(query="fire risk", tenant_id=TENANT_ID, user=SimpleNamespace(tenant_id=TENANT_ID))

    assert called == list(_MODULE_SEARCHES)


@pytest.mark.asyncio
async def test_the_route_restricts_partner_callers_and_only_partner_callers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The handler is what connects the principal to the module allowlist."""
    recorded: list[Any] = []

    async def fake_search(**kwargs: Any) -> dict:
        recorded.append(kwargs["allowed_modules"])
        return {"results": [], "total": 0, "query": kwargs["query"], "facets": {}}

    monkeypatch.setattr(
        global_search,
        "SearchService",
        lambda _db_arg: SimpleNamespace(search=fake_search),
    )

    partner = PartnerPrincipal(_token(scopes=["search:read"])[0])
    session_user = SimpleNamespace(tenant_id=TENANT_ID, id=1, is_superuser=False)

    for caller in (partner, session_user):
        await global_search.global_search(
            current_user=caller,  # type: ignore[arg-type]
            db=_db(),  # type: ignore[arg-type]
            q="fire risk",
            module=None,
            status=None,
            date_from=None,
            date_to=None,
            page=1,
            page_size=20,
            request_id="test",
        )

    assert recorded == [PARTNER_VISIBLE_MODULES, None]
