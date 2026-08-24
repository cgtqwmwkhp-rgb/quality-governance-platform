import types
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.routes import auth as auth_routes
from src.api.routes.auth import AzureTokenExchangeRequest, exchange_azure_token, login
from src.api.routes.auth import refresh_token as refresh_access_token
from src.api.schemas.auth import LoginRequest, RefreshTokenRequest
from src.core.security import create_refresh_token, decode_token


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def _stub_auth_audit(monkeypatch) -> AsyncMock:
    """Avoid real AuditLogEntry writes in route unit tests."""
    audit = AsyncMock()
    monkeypatch.setattr(auth_routes, "_record_auth_audit", audit)
    return audit


@pytest.mark.asyncio
async def test_login_embeds_user_roles_in_access_token(monkeypatch):
    user = types.SimpleNamespace(
        id=42,
        email="david.harris@plantexpand.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        tenant_id=7,
        full_name="David Harris",
        roles=[types.SimpleNamespace(name="admin")],
        last_login=None,
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(user)),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    monkeypatch.setattr("src.domain.services.auth_service.verify_password", lambda _plain, _hashed: True)
    audit = _stub_auth_audit(monkeypatch)

    response = await login(
        LoginRequest(email="david.harris@plantexpand.com", password="secret"),
        db,
    )
    payload = decode_token(response.access_token)

    assert payload is not None
    assert payload["role"] == "admin"
    assert payload["roles"] == ["admin"]
    assert payload["is_superuser"] is False
    audit.assert_awaited_once()
    assert audit.await_args.args[2] == "login"


@pytest.mark.asyncio
async def test_login_is_disabled_in_production_without_break_glass(monkeypatch):
    monkeypatch.setattr(
        auth_routes,
        "settings",
        types.SimpleNamespace(is_production=True, allow_local_password_login=False),
    )

    with pytest.raises(HTTPException) as exc_info:
        await login(LoginRequest(email="david.harris@plantexpand.com", password="secret"), AsyncMock())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "PERMISSION_DENIED"


def test_local_password_gate_honours_environment_alias(monkeypatch):
    monkeypatch.setattr(
        auth_routes,
        "settings",
        types.SimpleNamespace(is_production=False, allow_local_password_login=False),
    )
    monkeypatch.setenv("ENVIRONMENT", "production")

    assert auth_routes._local_password_login_allowed() is False


@pytest.mark.asyncio
async def test_login_allows_explicit_production_break_glass(monkeypatch):
    user = types.SimpleNamespace(
        id=42,
        email="david.harris@plantexpand.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        tenant_id=7,
        full_name="David Harris",
        roles=[],
        last_login=None,
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(user)),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    monkeypatch.setattr(
        auth_routes,
        "settings",
        types.SimpleNamespace(is_production=True, allow_local_password_login=True),
    )
    monkeypatch.setattr("src.domain.services.auth_service.verify_password", lambda _plain, _hashed: True)
    _stub_auth_audit(monkeypatch)

    response = await login(LoginRequest(email="david.harris@plantexpand.com", password="secret"), db)

    assert response.access_token


@pytest.mark.asyncio
async def test_refresh_embeds_superuser_admin_claim(monkeypatch):
    user = types.SimpleNamespace(
        id=42,
        email="david.harris@plantexpand.com",
        is_active=True,
        is_superuser=True,
        roles=[],
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(user)),
    )
    monkeypatch.setattr("src.domain.services.auth_service.is_token_revoked", AsyncMock(return_value=False))
    monkeypatch.setattr("src.domain.services.auth_service.TokenService.revoke_token", AsyncMock())

    response = await refresh_access_token(
        RefreshTokenRequest(refresh_token=create_refresh_token(subject=42)),
        db,
    )
    payload = decode_token(response.access_token)

    assert payload is not None
    assert payload["role"] == "admin"
    assert payload["roles"] == ["admin"]
    assert payload["is_superuser"] is True


@pytest.mark.asyncio
async def test_token_exchange_embeds_existing_user_roles(monkeypatch):
    user = types.SimpleNamespace(
        id=42,
        email="david.harris@plantexpand.com",
        full_name="David Harris",
        is_active=True,
        is_superuser=False,
        tenant_id=7,
        roles=[types.SimpleNamespace(name="admin"), types.SimpleNamespace(name="supervisor")],
        azure_oid="abc",
        department=None,
        job_title=None,
        last_login=None,
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(user)),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    monkeypatch.setattr("src.domain.services.auth_service.validate_azure_id_token", lambda _token: {"sub": "azure"})
    monkeypatch.setattr(
        "src.domain.services.auth_service.extract_user_info_from_azure_token",
        lambda _payload: {"email": "david.harris@plantexpand.com", "oid": "abc", "name": "David Harris"},
    )
    audit = _stub_auth_audit(monkeypatch)

    response = await exchange_azure_token(
        AzureTokenExchangeRequest(id_token="azure-token"),
        db,
    )
    payload = decode_token(response.access_token)

    assert payload is not None
    assert payload["role"] == "admin"
    assert payload["roles"] == ["admin", "supervisor"]
    assert payload["is_superuser"] is False
    audit.assert_awaited_once()
    assert audit.await_args.args[2] == "login"


@pytest.mark.asyncio
async def test_record_auth_audit_skips_without_tenant(monkeypatch):
    logged = AsyncMock()
    monkeypatch.setattr(auth_routes.AuditLogService, "log_auth", logged)
    user = types.SimpleNamespace(id=1, email="a@b.com", full_name="A", tenant_id=None)

    await auth_routes._record_auth_audit(AsyncMock(), user, "login")

    logged.assert_not_called()


@pytest.mark.asyncio
async def test_record_auth_audit_writes_log_auth(monkeypatch):
    logged = AsyncMock()

    class _FakeALS:
        def __init__(self, _db):
            pass

        log_auth = logged

    monkeypatch.setattr(auth_routes, "AuditLogService", _FakeALS)
    user = types.SimpleNamespace(id=1, email="a@b.com", full_name="A", tenant_id=9)

    await auth_routes._record_auth_audit(AsyncMock(), user, "logout")

    logged.assert_awaited_once()
    kwargs = logged.await_args.kwargs
    assert kwargs["tenant_id"] == 9
    assert kwargs["action"] == "logout"
    assert kwargs["user_id"] == 1
