"""Unit tests for realtime WebSocket authentication hardening."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.realtime import (
    WS_CLOSE_FORBIDDEN,
    WS_CLOSE_UNAUTHORIZED,
    authenticate_websocket_connection,
)
from src.core.security import create_access_token, create_refresh_token
from src.domain.exceptions import TokenRevokedError
from src.domain.models.user import User


def _session_cm(db: AsyncMock):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.asyncio
async def test_websocket_auth_rejects_missing_or_invalid_token() -> None:
    user, code = await authenticate_websocket_connection("not-a-jwt", path_user_id=1)
    assert user is None
    assert code == WS_CLOSE_UNAUTHORIZED


@pytest.mark.asyncio
async def test_websocket_auth_rejects_refresh_token_type() -> None:
    token = create_refresh_token(subject="1")
    user, code = await authenticate_websocket_connection(token, path_user_id=1)
    assert user is None
    assert code == WS_CLOSE_UNAUTHORIZED


@pytest.mark.asyncio
async def test_websocket_auth_rejects_sub_mismatch() -> None:
    token = create_access_token(subject="1")
    user, code = await authenticate_websocket_connection(token, path_user_id=99)
    assert user is None
    assert code == WS_CLOSE_FORBIDDEN


@pytest.mark.asyncio
async def test_websocket_auth_rejects_revoked_access_token() -> None:
    token = create_access_token(subject="7")
    db = AsyncMock()

    with (
        patch(
            "src.api.routes.realtime.async_session_maker",
            return_value=_session_cm(db),
        ),
        patch(
            "src.api.routes.realtime.ensure_access_token_not_revoked",
            new_callable=AsyncMock,
            side_effect=TokenRevokedError("Access token has been revoked"),
        ),
    ):
        user, code = await authenticate_websocket_connection(token, path_user_id=7)

    assert user is None
    assert code == WS_CLOSE_UNAUTHORIZED
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_websocket_auth_rejects_inactive_user() -> None:
    token = create_access_token(subject="7")
    inactive = User(
        id=7,
        email="inactive@example.com",
        hashed_password="hashed",
        first_name="In",
        last_name="Active",
        is_active=False,
        tenant_id=1,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = inactive
    db = AsyncMock()
    db.execute.return_value = result

    with (
        patch(
            "src.api.routes.realtime.async_session_maker",
            return_value=_session_cm(db),
        ),
        patch(
            "src.api.routes.realtime.ensure_access_token_not_revoked",
            new_callable=AsyncMock,
        ),
    ):
        user, code = await authenticate_websocket_connection(token, path_user_id=7)

    assert user is None
    assert code == WS_CLOSE_UNAUTHORIZED


@pytest.mark.asyncio
async def test_websocket_auth_requires_tenant_membership_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.api.routes.realtime.settings.app_env", "production")

    token = create_access_token(subject="7")
    orphan = User(
        id=7,
        email="orphan@example.com",
        hashed_password="hashed",
        first_name="Or",
        last_name="Phan",
        is_active=True,
        tenant_id=None,
    )
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = orphan
    membership_result = MagicMock()
    membership_result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute.side_effect = [user_result, membership_result]

    with (
        patch(
            "src.api.routes.realtime.async_session_maker",
            return_value=_session_cm(db),
        ),
        patch(
            "src.api.routes.realtime.ensure_access_token_not_revoked",
            new_callable=AsyncMock,
        ),
    ):
        user, code = await authenticate_websocket_connection(token, path_user_id=7)

    assert user is None
    assert code == WS_CLOSE_FORBIDDEN


@pytest.mark.asyncio
async def test_websocket_auth_accepts_valid_token_with_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.api.routes.realtime.settings.app_env", "production")

    token = create_access_token(subject="7")
    active = User(
        id=7,
        email="ok@example.com",
        hashed_password="hashed",
        first_name="Ok",
        last_name="User",
        is_active=True,
        tenant_id=3,
        roles=[],
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = active
    db = AsyncMock()
    db.execute.return_value = result
    db.expunge = MagicMock()

    with (
        patch(
            "src.api.routes.realtime.async_session_maker",
            return_value=_session_cm(db),
        ),
        patch(
            "src.api.routes.realtime.ensure_access_token_not_revoked",
            new_callable=AsyncMock,
        ),
    ):
        user, code = await authenticate_websocket_connection(token, path_user_id=7)

    assert code == 0
    assert user is active
    db.expunge.assert_called_once_with(active)
