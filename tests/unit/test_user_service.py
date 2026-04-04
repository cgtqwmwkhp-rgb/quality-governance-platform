"""Tests for src.domain.services.user_service.

Tests focus on business logic validation paths that don't require
SQLAlchemy mapper initialization (avoiding the dual Role class conflict).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_scalar(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_scalars(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


# ---------------------------------------------------------------------------
# delete_user (uses get_user internally, so we mock get_user)
# ---------------------------------------------------------------------------


class TestDeleteUser:
    @pytest.mark.asyncio
    @patch("src.domain.services.user_service.invalidate_tenant_cache", new_callable=AsyncMock)
    async def test_delete_self_raises(self, _cache):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        user = MagicMock(id=5)
        svc.get_user = AsyncMock(return_value=user)
        with pytest.raises(ValueError, match="Cannot delete your own"):
            await svc.delete_user(5, tenant_id=1, current_user_id=5)

    @pytest.mark.asyncio
    @patch("src.domain.services.user_service.invalidate_tenant_cache", new_callable=AsyncMock)
    async def test_delete_deactivates_user(self, _cache):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        user = MagicMock(id=5, is_active=True)
        svc.get_user = AsyncMock(return_value=user)
        await svc.delete_user(5, tenant_id=1, current_user_id=1)
        assert user.is_active is False

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        svc.get_user = AsyncMock(side_effect=LookupError("not found"))
        with pytest.raises(LookupError):
            await svc.delete_user(999, tenant_id=1, current_user_id=1)

    @pytest.mark.asyncio
    @patch("src.domain.services.user_service.invalidate_tenant_cache", new_callable=AsyncMock)
    async def test_delete_user_no_tenant_skips_cache(self, mock_cache):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        user = MagicMock(id=5, is_active=True)
        svc.get_user = AsyncMock(return_value=user)
        await svc.delete_user(5, tenant_id=None, current_user_id=1)
        mock_cache.assert_not_awaited()


# ---------------------------------------------------------------------------
# create_user (duplicate check only - avoids User() constructor)
# ---------------------------------------------------------------------------


class TestCreateUser:
    @pytest.mark.asyncio
    @patch("src.domain.services.user_service.get_password_hash", return_value="hashed")
    async def test_duplicate_email_raises(self, _hash):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        svc.db.execute.return_value = _mock_scalar(MagicMock())
        with pytest.raises(ValueError, match="email already exists"):
            await svc.create_user(
                email="dup@x.com",
                password="s",
                first_name="J",
                last_name="D",
                tenant_id=1,
            )


# ---------------------------------------------------------------------------
# update_user (tested via mock)
# ---------------------------------------------------------------------------

_user_patches = [
    patch("src.domain.services.user_service.User", MagicMock()),
    patch("src.domain.services.user_service.select", return_value=MagicMock()),
    patch("src.domain.services.user_service.selectinload", return_value=MagicMock()),
]


def _apply_user_patches(fn):
    """Stack patches that neutralise SA mapper init."""
    for p in reversed(_user_patches):
        fn = p(fn)
    return fn


class TestUpdateUser:
    @pytest.mark.asyncio
    @_apply_user_patches
    @patch("src.domain.services.user_service.apply_updates")
    @patch("src.domain.services.user_service.invalidate_tenant_cache", new_callable=AsyncMock)
    async def test_update_user_happy_path(self, _cache, _apply, *_sa):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        user = MagicMock(id=1)
        svc.db.execute.return_value = _mock_scalar(user)
        svc.db.refresh = AsyncMock()
        schema = MagicMock()
        schema.model_dump.return_value = {"first_name": "Updated"}
        result = await svc.update_user(1, 1, schema)
        assert result is user

    @pytest.mark.asyncio
    @_apply_user_patches
    async def test_update_user_not_found(self, *_sa):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        svc.db.execute.return_value = _mock_scalar(None)
        with pytest.raises(LookupError, match="not found"):
            await svc.update_user(999, 1, MagicMock())

    @pytest.mark.asyncio
    @_apply_user_patches
    @patch("src.domain.services.user_service.apply_updates")
    @patch("src.domain.services.user_service.invalidate_tenant_cache", new_callable=AsyncMock)
    async def test_update_user_with_role_ids(self, _cache, _apply, *_sa):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        user = MagicMock(id=1, roles=[])
        svc.db.execute.side_effect = [
            _mock_scalar(user),
            _mock_scalars([MagicMock(id=1)]),
        ]
        svc.db.refresh = AsyncMock()
        schema = MagicMock()
        schema.model_dump.return_value = {"role_ids": [1]}
        result = await svc.update_user(1, 1, schema)
        assert result is user


# ---------------------------------------------------------------------------
# Role operations (validation paths)
# ---------------------------------------------------------------------------


class TestRoleOperations:
    @pytest.mark.asyncio
    async def test_create_role_duplicate_name(self):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        svc.db.execute.return_value = _mock_scalar(MagicMock())
        data = MagicMock()
        data.model_dump.return_value = {"name": "admin"}
        with pytest.raises(ValueError, match="role with this name already exists"):
            await svc.create_role(data)

    @pytest.mark.asyncio
    async def test_update_role_not_found(self):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        svc.db.execute.return_value = _mock_scalar(None)
        with pytest.raises(LookupError, match="not found"):
            await svc.update_role(999, MagicMock())

    @pytest.mark.asyncio
    async def test_update_system_role_raises(self):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        role = MagicMock(is_system_role=True)
        svc.db.execute.return_value = _mock_scalar(role)
        with pytest.raises(PermissionError, match="System roles"):
            await svc.update_role(1, MagicMock())

    @pytest.mark.asyncio
    @patch("src.domain.services.user_service.apply_updates")
    async def test_update_role_happy_path(self, _apply):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        role = MagicMock(is_system_role=False, id=1)
        svc.db.execute.return_value = _mock_scalar(role)
        svc.db.refresh = AsyncMock()
        result = await svc.update_role(1, MagicMock())
        assert result is role

    @pytest.mark.asyncio
    async def test_list_roles(self):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        svc.db.execute.return_value = _mock_scalars([MagicMock(), MagicMock()])
        result = await svc.list_roles()
        assert len(list(result)) == 2

    @pytest.mark.asyncio
    @_apply_user_patches
    async def test_get_user_not_found_raises(self, *_sa):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        svc.db.execute.return_value = _mock_scalar(None)
        with pytest.raises(LookupError, match="not found"):
            await svc.get_user(999, tenant_id=1)

    @pytest.mark.asyncio
    @_apply_user_patches
    async def test_get_user_returns_user(self, *_sa):
        from src.domain.services.user_service import UserService

        svc = UserService(AsyncMock())
        user = MagicMock(id=1)
        svc.db.execute.return_value = _mock_scalar(user)
        result = await svc.get_user(1, tenant_id=1)
        assert result is user
