"""Partner bearer inbound auth + scope gates (documents/search)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.dependencies.partner import (
    require_auth_or_partner_scope,
    require_permission_or_partner_scope,
)
from src.domain.models.partner_api_token import PARTNER_SCOPE_TO_PERMISSIONS, PartnerApiToken
from src.domain.services.partner_auth_service import (
    PartnerAuthService,
    PartnerPrincipal,
    generate_partner_token,
    hash_partner_token,
    is_partner_bearer_token,
    partner_effective_permissions,
)


def test_is_partner_bearer_token():
    assert is_partner_bearer_token("qgp_pt_abc") is True
    assert is_partner_bearer_token("eyJhbGciOi") is False
    assert is_partner_bearer_token("") is False


def test_partner_scope_permission_mapping():
    assert "document:read" in PARTNER_SCOPE_TO_PERMISSIONS["documents:read"]
    assert "policy:read" in PARTNER_SCOPE_TO_PERMISSIONS["policies:read"]
    assert partner_effective_permissions(["documents:read", "search:read"]) == frozenset({"document:read"})
    assert partner_effective_permissions(["webhooks:manage"]) == frozenset()


def test_partner_principal_has_permission_from_scope():
    token = PartnerApiToken(
        id=7,
        tenant_id=3,
        token_prefix="qgp_pt_abcdef12",
        secret_hash="x",
        scopes=["documents:read", "search:read"],
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    principal = PartnerPrincipal(token)
    assert principal.tenant_id == 3
    assert principal.id is None
    assert principal.has_partner_scope("documents:read") is True
    assert principal.has_partner_scope("webhooks:manage") is False
    assert principal.has_permission("document:read") is True
    assert principal.has_permission("document:update") is False
    assert principal.has_permission("admin:manage") is False


@pytest.mark.asyncio
async def test_authenticate_accepts_valid_active_token():
    raw, secret_hash, prefix = generate_partner_token()
    stored = PartnerApiToken(
        id=1,
        tenant_id=10,
        token_prefix=prefix,
        secret_hash=secret_hash,
        scopes=["documents:read"],
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    class _Scalars:
        def all(self):
            return [stored]

    class _Result:
        def scalars(self):
            return _Scalars()

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result())
    service = PartnerAuthService(db)
    matched = await service.authenticate(raw)
    assert matched is stored
    assert matched.last_used_at is not None
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_authenticate_rejects_revoked_or_wrong_secret():
    raw, secret_hash, prefix = generate_partner_token()
    stored = PartnerApiToken(
        id=1,
        tenant_id=10,
        token_prefix=prefix,
        secret_hash=secret_hash,
        scopes=["documents:read"],
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    class _Scalars:
        def __init__(self, values):
            self._values = values

        def all(self):
            return self._values

    class _Result:
        def __init__(self, values):
            self._values = values

        def scalars(self):
            return _Scalars(self._values)

    db = AsyncMock()
    # Prefix lookup returns the row, but secret mismatches.
    db.execute = AsyncMock(return_value=_Result([stored]))
    service = PartnerAuthService(db)
    assert await service.authenticate("qgp_pt_not_the_real_secret_value_xxx") is None

    # Non-partner prefix short-circuits without DB.
    db.execute.reset_mock()
    assert await service.authenticate("not-a-partner-token") is None
    db.execute.assert_not_awaited()


def _token_row(*, scopes: list[str], raw: str | None = None) -> tuple[PartnerApiToken, str]:
    if raw is None:
        raw, secret_hash, prefix = generate_partner_token()
    else:
        secret_hash = hash_partner_token(raw)
        prefix = raw[:16]
    token = PartnerApiToken(
        id=42,
        tenant_id=99,
        name="CRM Bid Writer",
        token_prefix=prefix,
        secret_hash=secret_hash,
        scopes=scopes,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return token, raw


def _app_with_partner_routes() -> FastAPI:
    """Minimal app exercising the dual-auth dependencies."""
    from src.api.dependencies import get_current_user
    from src.infrastructure.database import get_db

    app = FastAPI()
    state: dict[str, Any] = {"token": None, "jwt_user": None}

    async def _fake_db():
        class _Scalars:
            def all(self_inner):
                return [state["token"]] if state["token"] is not None else []

        class _Result:
            def scalars(self_inner):
                return _Scalars()

        db = AsyncMock()
        db.execute = AsyncMock(return_value=_Result())
        db.flush = AsyncMock()
        yield db

    async def _fake_jwt_user():
        user = state["jwt_user"]
        if user is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
        return user

    app.dependency_overrides[get_db] = _fake_db

    # Patch JWT path used inside partner deps by overriding get_current_user is not enough —
    # partner deps call _authenticate_jwt_user directly. Monkeypatch via module after import.
    import src.api.dependencies.partner as partner_deps

    async def _jwt_stub(raw_token: str, db: Any):
        user = state["jwt_user"]
        if user is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
        return user

    partner_deps._authenticate_jwt_user = _jwt_stub  # type: ignore[attr-defined]

    @app.get("/search")
    async def search(
        user=Depends(require_auth_or_partner_scope("search:read")),
    ):
        return {"ok": True, "tenant_id": user.tenant_id, "partner": hasattr(user, "_partner_scopes")}

    @app.get("/documents/search")
    async def doc_search(
        user=Depends(require_permission_or_partner_scope("document:read", "documents:read")),
    ):
        return {
            "ok": True,
            "has_document_read": user.has_permission("document:read"),
            "partner": hasattr(user, "_partner_scopes"),
        }

    @app.get("/jwt-only")
    async def jwt_only(user=Depends(get_current_user)):
        return {"ok": True, "email": user.email}

    app.state = state  # type: ignore[attr-defined]
    return app


def test_partner_search_requires_search_read_scope():
    app = _app_with_partner_routes()
    token, raw = _token_row(scopes=["documents:read"])  # missing search:read
    app.state["token"] = token  # type: ignore[index]
    client = TestClient(app)
    res = client.get("/search", headers={"Authorization": f"Bearer {raw}"})
    assert res.status_code == 403
    assert "search:read" in res.json()["detail"]

    token2, raw2 = _token_row(scopes=["search:read"])
    app.state["token"] = token2  # type: ignore[index]
    res2 = client.get("/search", headers={"Authorization": f"Bearer {raw2}"})
    assert res2.status_code == 200
    assert res2.json()["partner"] is True
    assert res2.json()["tenant_id"] == 99


def test_partner_document_search_requires_documents_read_scope():
    app = _app_with_partner_routes()
    token, raw = _token_row(scopes=["search:read"])  # missing documents:read
    app.state["token"] = token  # type: ignore[index]
    client = TestClient(app)
    res = client.get("/documents/search", headers={"Authorization": f"Bearer {raw}"})
    assert res.status_code == 403
    assert "documents:read" in res.json()["detail"]

    token2, raw2 = _token_row(scopes=["documents:read"])
    app.state["token"] = token2  # type: ignore[index]
    res2 = client.get("/documents/search", headers={"Authorization": f"Bearer {raw2}"})
    assert res2.status_code == 200
    assert res2.json()["has_document_read"] is True


def test_partner_token_rejected_on_jwt_only_route():
    app = _app_with_partner_routes()
    token, raw = _token_row(scopes=["documents:read", "search:read"])
    app.state["token"] = token  # type: ignore[index]
    client = TestClient(app)
    res = client.get("/jwt-only", headers={"Authorization": f"Bearer {raw}"})
    assert res.status_code == 401
    assert "Partner API tokens" in res.json()["detail"]


class _JwtUser:
    def __init__(self, *, allow_document_read: bool = True):
        self.tenant_id = 5
        self.email = "ops@example.com"
        self._allow_document_read = allow_document_read

    def has_permission(self, permission: str) -> bool:
        return self._allow_document_read and permission == "document:read"


def test_jwt_caller_unchanged_on_partner_gated_routes():
    app = _app_with_partner_routes()
    app.state["jwt_user"] = _JwtUser()  # type: ignore[index]
    client = TestClient(app)

    res = client.get("/search", headers={"Authorization": "Bearer jwt-session"})
    assert res.status_code == 200
    assert res.json()["partner"] is False

    res2 = client.get("/documents/search", headers={"Authorization": "Bearer jwt-session"})
    assert res2.status_code == 200
    assert res2.json()["partner"] is False

    app.state["jwt_user"] = _JwtUser(allow_document_read=False)  # type: ignore[index]
    res3 = client.get("/documents/search", headers={"Authorization": "Bearer jwt-session"})
    assert res3.status_code == 403


@pytest.mark.asyncio
async def test_create_token_accepts_new_scopes():
    db = AsyncMock()
    service = PartnerAuthService(db)
    token, raw = await service.create_token(
        tenant_id=1,
        name="K4 CRM",
        scopes=["documents:read", "search:read"],
    )
    assert set(token.scopes) == {"documents:read", "search:read"}
    assert raw.startswith("qgp_pt_")
