"""Tests for src.domain.services.tenant_service."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.tenant_service import TenantService


def _mock_scalar(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_scalars(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


# ---------------------------------------------------------------------------
# Tenant CRUD
# ---------------------------------------------------------------------------


class TestTenantCRUD:
    @pytest.fixture
    def service(self):
        return TenantService(AsyncMock())

    @pytest.mark.asyncio
    async def test_create_tenant_duplicate_slug(self, service):
        service.db.execute.return_value = _mock_scalar(MagicMock())

        with pytest.raises(ValueError, match="already exists"):
            await service.create_tenant("T", "dup-slug", "a@b.com", 1)

    @pytest.mark.asyncio
    async def test_create_tenant_duplicate_raises_value_error(self, service):
        """Verify create_tenant raises when slug already exists."""
        service.db.execute.return_value = _mock_scalar(MagicMock())
        with pytest.raises(ValueError, match="already exists"):
            await service.create_tenant("Acme", "dup-slug", "admin@acme.com", 1)

    @pytest.mark.asyncio
    async def test_get_tenant_found(self, service):
        t = MagicMock(id=1)
        service.db.execute.return_value = _mock_scalar(t)
        assert await service.get_tenant(1) is t

    @pytest.mark.asyncio
    async def test_get_tenant_not_found(self, service):
        service.db.execute.return_value = _mock_scalar(None)
        assert await service.get_tenant(999) is None

    @pytest.mark.asyncio
    async def test_get_tenant_by_slug(self, service):
        t = MagicMock(slug="acme")
        service.db.execute.return_value = _mock_scalar(t)
        assert await service.get_tenant_by_slug("acme") is t

    @pytest.mark.asyncio
    async def test_get_tenant_by_domain(self, service):
        t = MagicMock(domain="acme.com")
        service.db.execute.return_value = _mock_scalar(t)
        assert await service.get_tenant_by_domain("acme.com") is t

    @pytest.mark.asyncio
    async def test_update_tenant_not_found(self, service):
        service.get_tenant = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await service.update_tenant(999, name="New")

    @pytest.mark.asyncio
    async def test_update_tenant_sets_attrs(self, service):
        tenant = MagicMock(id=1)
        tenant.name = "Old"
        service.get_tenant = AsyncMock(return_value=tenant)
        service.db.refresh = AsyncMock()

        updated = await service.update_tenant(1, name="New")
        assert updated.name == "New"


# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------


class TestBranding:
    @pytest.fixture
    def service(self):
        svc = TenantService(AsyncMock())
        tenant = MagicMock(id=1)
        svc.get_tenant = AsyncMock(return_value=tenant)
        svc.db.refresh = AsyncMock()
        return svc

    @pytest.mark.asyncio
    async def test_update_branding_sets_colors(self, service):
        result = await service.update_branding(1, primary_color="#ff0000")
        assert result.primary_color == "#ff0000"


# ---------------------------------------------------------------------------
# User-Tenant Management
# ---------------------------------------------------------------------------


class TestUserTenantManagement:
    @pytest.fixture
    def service(self):
        return TenantService(AsyncMock())

    @pytest.mark.asyncio
    async def test_get_user_tenants(self, service):
        service.db.execute.return_value = _mock_scalars([MagicMock(), MagicMock()])
        result = await service.get_user_tenants(1)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_add_user_duplicate_active(self, service):
        existing = MagicMock(is_active=True)
        service.db.execute.return_value = _mock_scalar(existing)

        with pytest.raises(ValueError, match="already belongs"):
            await service.add_user_to_tenant(1, 1)

    @pytest.mark.asyncio
    async def test_add_user_reactivate_inactive(self, service):
        existing = MagicMock(is_active=False, role="user")
        service.db.execute.return_value = _mock_scalar(existing)

        result = await service.add_user_to_tenant(1, 1, role="admin")
        assert result.is_active is True
        assert result.role == "admin"

    @pytest.mark.asyncio
    async def test_add_user_already_active_raises(self, service):
        """If the user-tenant mapping already exists and is active, raise."""
        existing = MagicMock(is_active=True)
        service.db.execute.return_value = _mock_scalar(existing)
        with pytest.raises(ValueError, match="already belongs"):
            await service.add_user_to_tenant(1, 2, role="user")

    @pytest.mark.asyncio
    async def test_add_user_reactivate_inactive_with_new_role(self, service):
        """If user-tenant mapping exists but is inactive, reactivate with new role."""
        existing = MagicMock(is_active=False, role="old_role")
        service.db.execute.return_value = _mock_scalar(existing)
        result = await service.add_user_to_tenant(1, 2, role="viewer")
        assert existing.is_active is True
        assert existing.role == "viewer"
        assert result is existing

    @pytest.mark.asyncio
    async def test_remove_user_not_found(self, service):
        service.db.execute.return_value = _mock_scalar(None)
        result = await service.remove_user_from_tenant(1, 999)
        assert result is False

    @pytest.mark.asyncio
    async def test_remove_last_owner_raises(self, service):
        tu = MagicMock(role="owner")
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        service.db.execute = AsyncMock(
            side_effect=[
                _mock_scalar(tu),
                count_result,
            ]
        )

        with pytest.raises(ValueError, match="last owner"):
            await service.remove_user_from_tenant(1, 1)

    @pytest.mark.asyncio
    async def test_update_user_role_not_found(self, service):
        service.db.execute.return_value = _mock_scalar(None)

        with pytest.raises(ValueError, match="not found"):
            await service.update_user_role(1, 999, "admin")

    @pytest.mark.asyncio
    async def test_set_primary_tenant_not_found(self, service):
        service.db.execute.side_effect = [
            AsyncMock(),  # update call
            _mock_scalar(None),
        ]

        with pytest.raises(ValueError, match="not found"):
            await service.set_primary_tenant(1, 999)


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------


class TestInvitations:
    @pytest.fixture
    def service(self):
        return TenantService(AsyncMock())

    @pytest.mark.asyncio
    async def test_create_invitation(self, service):
        service.db.refresh = AsyncMock()

        with patch("src.domain.services.tenant_service.TenantInvitation"):
            inv = await service.create_invitation(1, "new@user.com", 1)
        service.db.add.assert_called()
        service.db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_accept_invitation_invalid_token(self, service):
        service.db.execute.return_value = _mock_scalar(None)

        with pytest.raises(ValueError, match="Invalid"):
            await service.accept_invitation("bad-token", 1)

    @pytest.mark.asyncio
    async def test_accept_invitation_expired(self, service):
        inv = MagicMock(
            status="pending",
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        service.db.execute.return_value = _mock_scalar(inv)

        with pytest.raises(ValueError, match="expired"):
            await service.accept_invitation("token", 1)


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------


class TestFeatureFlags:
    @pytest.fixture
    def service(self):
        return TenantService(AsyncMock())

    @pytest.mark.asyncio
    async def test_is_feature_enabled_false_when_no_tenant(self, service):
        service.get_tenant = AsyncMock(return_value=None)
        assert await service.is_feature_enabled(999, "new_feature") is False

    @pytest.mark.asyncio
    async def test_is_feature_enabled_true(self, service):
        tenant = MagicMock(features_enabled={"planet_mark": True})
        service.get_tenant = AsyncMock(return_value=tenant)
        assert await service.is_feature_enabled(1, "planet_mark") is True

    @pytest.mark.asyncio
    async def test_enable_feature(self, service):
        tenant = MagicMock(features_enabled={})
        service.get_tenant = AsyncMock(return_value=tenant)
        service.db.refresh = AsyncMock()

        result = await service.enable_feature(1, "analytics")
        assert result.features_enabled["analytics"] is True

    @pytest.mark.asyncio
    async def test_disable_feature(self, service):
        tenant = MagicMock(features_enabled={"analytics": True})
        service.get_tenant = AsyncMock(return_value=tenant)
        service.db.refresh = AsyncMock()

        result = await service.disable_feature(1, "analytics")
        assert result.features_enabled["analytics"] is False


# ---------------------------------------------------------------------------
# Subscription & Limits
# ---------------------------------------------------------------------------


class TestSubscriptionLimits:
    @pytest.fixture
    def service(self):
        return TenantService(AsyncMock())

    @pytest.mark.asyncio
    async def test_check_user_limit_not_found(self, service):
        service.get_tenant = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await service.check_user_limit(999)

    @pytest.mark.asyncio
    async def test_can_add_user_within_limit(self, service):
        service.check_user_limit = AsyncMock(return_value=(5, 10))
        assert await service.can_add_user(1) is True

    @pytest.mark.asyncio
    async def test_can_add_user_at_limit(self, service):
        service.check_user_limit = AsyncMock(return_value=(10, 10))
        assert await service.can_add_user(1) is False
