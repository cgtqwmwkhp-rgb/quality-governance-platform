from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.api.dependencies import (
    _resolve_user_tenant_context,
    get_current_user,
    get_optional_current_user,
)
from src.core.security import create_access_token, create_refresh_token, decode_token
from src.domain.exceptions import TokenRevokedError
from src.domain.models.tenant import TenantUser
from src.domain.models.user import User


def _auth_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _user_query_result(user: User | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    return result


@pytest.mark.asyncio
async def test_resolve_user_tenant_context_uses_primary_membership() -> None:
    user = User(
        id=7,
        email="auditor@example.com",
        hashed_password="hashed",
        first_name="Audit",
        last_name="User",
        tenant_id=None,
    )
    primary_membership = TenantUser(id=3, tenant_id=42, user_id=7, is_active=True, is_primary=True)
    result = MagicMock()
    result.scalars.return_value.first.return_value = primary_membership
    db = AsyncMock()
    db.execute.return_value = result

    await _resolve_user_tenant_context(db, user)

    assert user.tenant_id == 42


@pytest.mark.asyncio
async def test_resolve_user_tenant_context_bootstraps_default_org_in_non_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-production may bootstrap Default Organisation when no tenants exist."""
    monkeypatch.setattr("src.api.dependencies.settings.app_env", "development")

    user = User(
        id=7,
        email="auditor@example.com",
        hashed_password="hashed",
        first_name="Audit",
        last_name="User",
        tenant_id=None,
    )
    no_membership_result = MagicMock()
    no_membership_result.scalars.return_value.first.return_value = None
    no_tenant_result = MagicMock()
    no_tenant_result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute.side_effect = [no_membership_result, no_tenant_result]

    await _resolve_user_tenant_context(db, user)

    # Tenant + TenantUser rows are staged; id may still be None until DB flush assigns it.
    assert db.add.call_count >= 2
    added_names = [getattr(call.args[0], "name", None) for call in db.add.call_args_list]
    assert "Default Organisation" in added_names


@pytest.mark.asyncio
async def test_resolve_user_tenant_context_auto_assigns_tenant_when_no_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no TenantUser membership exists but an active Tenant does, auto-assign it (non-prod)."""
    monkeypatch.setattr("src.api.dependencies.settings.app_env", "development")

    user = User(
        id=7,
        email="auditor@example.com",
        hashed_password="hashed",
        first_name="Audit",
        last_name="User",
        tenant_id=None,
    )
    no_membership_result = MagicMock()
    no_membership_result.scalars.return_value.first.return_value = None
    tenant_mock = MagicMock()
    tenant_mock.id = 99
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant_mock
    db = AsyncMock()
    db.execute.side_effect = [no_membership_result, tenant_result]

    await _resolve_user_tenant_context(db, user)

    assert user.tenant_id == 99
    db.add.assert_called_once()
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_resolve_user_tenant_context_fail_closed_in_production_without_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production must not auto-create Default Organisation or assign first tenant."""
    monkeypatch.setattr("src.api.dependencies.settings.app_env", "production")

    user = User(
        id=7,
        email="auditor@example.com",
        hashed_password="hashed",
        first_name="Audit",
        last_name="User",
        tenant_id=None,
    )
    no_membership_result = MagicMock()
    no_membership_result.scalars.return_value.first.return_value = None
    db = AsyncMock()
    db.execute.return_value = no_membership_result

    with pytest.raises(HTTPException) as exc_info:
        await _resolve_user_tenant_context(db, user)

    assert exc_info.value.status_code == 403
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "TENANT_ACCESS_DENIED"
    assert user.tenant_id is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_current_user_rejects_revoked_access_token() -> None:
    token = create_access_token(subject="7")
    payload = decode_token(token)
    assert payload is not None

    db = AsyncMock()
    credentials = _auth_credentials(token)

    with patch(
        "src.api.dependencies.ensure_access_token_not_revoked",
        new_callable=AsyncMock,
        side_effect=TokenRevokedError("Access token has been revoked"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, db)

    assert exc_info.value.status_code == 401
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "TOKEN_REVOKED"
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_current_user_accepts_valid_access_token() -> None:
    token = create_access_token(subject="7")
    user = User(
        id=7,
        email="auditor@example.com",
        hashed_password="hashed",
        first_name="Audit",
        last_name="User",
        is_active=True,
        tenant_id=1,
    )
    db = AsyncMock()
    db.execute.return_value = _user_query_result(user)
    credentials = _auth_credentials(token)

    with patch(
        "src.api.dependencies.ensure_access_token_not_revoked",
        new_callable=AsyncMock,
    ) as ensure_not_revoked:
        result = await get_current_user(credentials, db)

    assert result is user
    ensure_not_revoked.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_optional_current_user_rejects_revoked_access_token() -> None:
    token = create_access_token(subject="7")
    db = AsyncMock()
    credentials = _auth_credentials(token)

    with patch(
        "src.api.dependencies.ensure_access_token_not_revoked",
        new_callable=AsyncMock,
        side_effect=TokenRevokedError("Access token has been revoked"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_optional_current_user(credentials, db)

    assert exc_info.value.status_code == 401
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "TOKEN_REVOKED"


@pytest.mark.asyncio
async def test_get_optional_current_user_returns_none_without_credentials() -> None:
    db = AsyncMock()
    result = await get_optional_current_user(None, db)
    assert result is None
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_current_user_rejects_refresh_token_type() -> None:
    token = create_refresh_token(subject="7")
    db = AsyncMock()
    credentials = _auth_credentials(token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials, db)

    assert exc_info.value.status_code == 401
    db.execute.assert_not_called()
