"""Tests for src.domain.services.feature_flag_service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.feature_flag_service import FeatureFlagService, _flag_cache


def _mock_scalar(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_scalars(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.fixture(autouse=True)
def clear_cache():
    _flag_cache.clear()
    yield
    _flag_cache.clear()


# ---------------------------------------------------------------------------
# is_enabled
# ---------------------------------------------------------------------------


class TestIsEnabled:
    @pytest.fixture
    def service(self):
        return FeatureFlagService(AsyncMock())

    @pytest.mark.asyncio
    async def test_missing_flag_returns_false(self, service):
        service._get_flag = AsyncMock(return_value=None)
        assert await service.is_enabled("missing") is False

    @pytest.mark.asyncio
    async def test_disabled_flag_returns_false(self, service):
        flag = MagicMock(enabled=False)
        service._get_flag = AsyncMock(return_value=flag)
        assert await service.is_enabled("feature") is False

    @pytest.mark.asyncio
    async def test_enabled_full_rollout(self, service):
        flag = MagicMock(enabled=True, rollout_percentage=100, tenant_overrides=None)
        service._get_flag = AsyncMock(return_value=flag)
        assert await service.is_enabled("feature") is True

    @pytest.mark.asyncio
    async def test_enabled_zero_rollout(self, service):
        flag = MagicMock(enabled=True, rollout_percentage=0, tenant_overrides=None)
        service._get_flag = AsyncMock(return_value=flag)
        assert await service.is_enabled("feature") is False

    @pytest.mark.asyncio
    async def test_tenant_override_true(self, service):
        flag = MagicMock(enabled=True, rollout_percentage=0, tenant_overrides={"1": True})
        service._get_flag = AsyncMock(return_value=flag)
        assert await service.is_enabled("feature", tenant_id="1") is True

    @pytest.mark.asyncio
    async def test_tenant_override_false(self, service):
        flag = MagicMock(enabled=True, rollout_percentage=100, tenant_overrides={"1": False})
        service._get_flag = AsyncMock(return_value=flag)
        assert await service.is_enabled("feature", tenant_id="1") is False

    @pytest.mark.asyncio
    async def test_partial_rollout_deterministic(self, service):
        flag = MagicMock(enabled=True, rollout_percentage=50, tenant_overrides=None)
        service._get_flag = AsyncMock(return_value=flag)

        result1 = await service.is_enabled("feat", user_id="user1")
        result2 = await service.is_enabled("feat", user_id="user1")
        assert result1 == result2  # deterministic


# ---------------------------------------------------------------------------
# _get_flag (caching)
# ---------------------------------------------------------------------------


class TestGetFlag:
    @pytest.fixture
    def service(self):
        return FeatureFlagService(AsyncMock())

    @pytest.mark.asyncio
    async def test_caches_flag_on_first_fetch(self, service):
        flag = MagicMock(key="cached_flag")
        service.db.execute.return_value = _mock_scalar(flag)

        result = await service._get_flag("cached_flag")
        assert result is flag
        assert "cached_flag" in _flag_cache

    @pytest.mark.asyncio
    async def test_returns_cached_flag(self, service):
        cached = MagicMock(key="cached")
        _flag_cache["cached"] = cached

        result = await service._get_flag("cached")
        assert result is cached
        service.db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_none_for_missing(self, service):
        service.db.execute.return_value = _mock_scalar(None)
        result = await service._get_flag("missing")
        assert result is None
        assert "missing" not in _flag_cache


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


class TestFlagCRUD:
    @pytest.fixture
    def service(self):
        return FeatureFlagService(AsyncMock())

    @pytest.mark.asyncio
    async def test_list_flags(self, service):
        service.db.execute.return_value = _mock_scalars([MagicMock(), MagicMock()])
        flags = await service.list_flags()
        assert len(flags) == 2

    @pytest.mark.asyncio
    @patch("src.domain.services.feature_flag_service.FeatureFlag")
    async def test_create_flag(self, MockFlag, service):
        mock_flag = MagicMock(key="new_flag")
        MockFlag.return_value = mock_flag
        flag = await service.create_flag("new_flag", "New Flag", "desc")
        service.db.add.assert_called_once()
        assert "new_flag" in _flag_cache

    @pytest.mark.asyncio
    async def test_update_flag_found(self, service):
        flag = MagicMock(key="feat", enabled=False)
        service._get_flag = AsyncMock(return_value=flag)

        result = await service.update_flag("feat", enabled=True)
        assert result is flag
        assert result.enabled is True

    @pytest.mark.asyncio
    async def test_update_flag_not_found(self, service):
        service._get_flag = AsyncMock(return_value=None)
        result = await service.update_flag("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_flag_found(self, service):
        flag = MagicMock(key="old")
        service._get_flag = AsyncMock(return_value=flag)
        _flag_cache["old"] = flag

        result = await service.delete_flag("old")
        assert result is True
        assert "old" not in _flag_cache
        service.db.delete.assert_called_once_with(flag)

    @pytest.mark.asyncio
    async def test_delete_flag_not_found(self, service):
        service._get_flag = AsyncMock(return_value=None)
        result = await service.delete_flag("missing")
        assert result is False


# ---------------------------------------------------------------------------
# clear_cache
# ---------------------------------------------------------------------------


class TestClearCache:
    def test_clear_cache(self):
        _flag_cache["key"] = MagicMock()
        FeatureFlagService.clear_cache()
        assert len(_flag_cache) == 0
