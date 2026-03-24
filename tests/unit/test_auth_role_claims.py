import types
from unittest.mock import AsyncMock

import pytest

from src.api.routes.auth import AzureTokenExchangeRequest, exchange_azure_token, login
from src.api.routes.auth import refresh_token as refresh_access_token
from src.api.schemas.auth import LoginRequest, RefreshTokenRequest
from src.core.security import create_refresh_token, decode_token


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_login_embeds_user_roles_in_access_token(monkeypatch):
    user = types.SimpleNamespace(
        id=42,
        email="david.harris@plantexpand.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        roles=[types.SimpleNamespace(name="admin")],
        last_login=None,
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(user)),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    monkeypatch.setattr("src.domain.services.auth_service.verify_password", lambda _plain, _hashed: True)

    response = await login(
        LoginRequest(email="david.harris@plantexpand.com", password="secret"),
        db,
    )
    payload = decode_token(response.access_token)

    assert payload is not None
    assert payload["role"] == "admin"
    assert payload["roles"] == ["admin"]
    assert payload["is_superuser"] is False


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

    response = await exchange_azure_token(
        AzureTokenExchangeRequest(id_token="azure-token"),
        db,
    )
    payload = decode_token(response.access_token)

    assert payload is not None
    assert payload["role"] == "admin"
    assert payload["roles"] == ["admin", "supervisor"]
    assert payload["is_superuser"] is False
