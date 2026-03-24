import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from src.api.routes.users import (
    _ensure_user_management_enabled,
    create_user,
    update_user,
)
from src.api.schemas.user import UserCreate, UserUpdate
from src.domain.models.user import Role


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return types.SimpleNamespace(all=lambda: self._value)


@pytest.mark.asyncio
async def test_create_user_supports_sso_without_password(monkeypatch):
    now = datetime.now(timezone.utc)
    role = Role(name="manager", permissions='["users:read"]')
    role.id = 1
    role.is_system_role = False
    role.created_at = now
    role.updated_at = now

    async def _refresh(entity):
        entity.id = 101
        entity.created_at = now
        entity.updated_at = now

    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(None), _FakeResult([role])]),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(side_effect=_refresh),
    )
    current_user = types.SimpleNamespace(id=1, email="admin@example.com", is_superuser=True)
    monkeypatch.setattr("src.api.routes.users._ensure_user_management_enabled", AsyncMock())

    await create_user(
        UserCreate(
            email="sso.user@example.com",
            first_name="SSO",
            last_name="User",
            auth_provider="microsoft_sso",
            role_ids=[1],
        ),
        db,
        current_user,
    )

    created_user = db.add.call_args.args[0]
    assert created_user.email == "sso.user@example.com"
    assert created_user.hashed_password == ""
    assert created_user.roles[0].name == "manager"


@pytest.mark.asyncio
async def test_update_user_blocks_removing_last_active_superuser(monkeypatch):
    user = types.SimpleNamespace(
        id=99,
        email="last.superuser@example.com",
        is_active=True,
        is_superuser=True,
        roles=[],
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(user)),
    )
    current_user = types.SimpleNamespace(id=1, email="admin@example.com", is_superuser=True)
    monkeypatch.setattr("src.api.routes.users._active_superuser_count", AsyncMock(return_value=1))
    monkeypatch.setattr("src.api.routes.users._ensure_user_management_enabled", AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        await update_user(
            99,
            UserUpdate(is_active=False),
            db,
            current_user,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "INVALID_STATE_TRANSITION"


@pytest.mark.asyncio
async def test_user_management_flag_fails_open_when_feature_flag_table_missing(monkeypatch):
    db = types.SimpleNamespace()
    monkeypatch.setattr(
        "src.api.routes.users.FeatureFlagService._get_flag",
        AsyncMock(side_effect=OperationalError("select 1", {}, Exception("missing table"))),
    )

    await _ensure_user_management_enabled(db)


@pytest.mark.asyncio
async def test_user_management_flag_can_disable_surface(monkeypatch):
    db = types.SimpleNamespace()
    disabled_flag = types.SimpleNamespace(enabled=False)
    monkeypatch.setattr(
        "src.api.routes.users.FeatureFlagService._get_flag",
        AsyncMock(return_value=disabled_flag),
    )

    with pytest.raises(HTTPException) as exc_info:
        await _ensure_user_management_enabled(db)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "CONFIGURATION_ERROR"
