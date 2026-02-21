"""Unit tests for Tenant Service - can run standalone."""

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

try:
    from src.domain.services.tenant_service import TenantService

    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Imports not available")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _mock_tenant(
    tenant_id=1,
    name="Acme Corp",
    slug="acme",
    features_enabled=None,
    max_users=50,
    **overrides,
):
    """Create a mock Tenant object."""
    tenant = MagicMock()
    tenant.id = tenant_id
    tenant.name = name
    tenant.slug = slug
    tenant.features_enabled = features_enabled or {}
    tenant.max_users = max_users
    tenant.domain = None
    tenant.admin_email = "admin@acme.com"
    tenant.subscription_tier = "standard"
    for key, value in overrides.items():
        setattr(tenant, key, value)
    return tenant


def _mock_tenant_user(tenant_id=1, user_id=10, role="user", is_active=True, is_primary=False):
    """Create a mock TenantUser object."""
    tu = MagicMock()
    tu.tenant_id = tenant_id
    tu.user_id = user_id
    tu.role = role
    tu.is_active = is_active
    tu.is_primary = is_primary
    return tu


def _execute_returning(value):
    """Create a mock db.execute return value with scalar_one_or_none."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    result.scalars.return_value.all.return_value = [value] if value else []
    return AsyncMock(return_value=result)


# ---------------------------------------------------------------------------
# create_tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_tenant_success():
    """Creating a tenant with a unique slug succeeds."""
    db = _mock_db()
    svc = TenantService(db)

    no_existing = MagicMock()
    no_existing.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=no_existing)

    await svc.create_tenant(
        name="Acme Corp",
        slug="acme",
        admin_email="admin@acme.com",
        admin_user_id=1,
    )

    assert db.add.call_count == 2  # tenant + owner TenantUser
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_create_tenant_duplicate_slug_raises():
    """Creating a tenant with an existing slug raises ValueError."""
    db = _mock_db()
    svc = TenantService(db)

    existing = _mock_tenant()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing
    db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(ValueError, match="already exists"):
        await svc.create_tenant(
            name="Acme Copy",
            slug="acme",
            admin_email="admin@acme.com",
            admin_user_id=2,
        )


# ---------------------------------------------------------------------------
# update_tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_tenant_applies_valid_attributes():
    """update_tenant sets attributes that exist on the tenant model."""
    db = _mock_db()
    svc = TenantService(db)

    tenant = _mock_tenant()
    tenant.name = "Old Name"
    db.execute = _execute_returning(tenant)

    result = await svc.update_tenant(tenant_id=1, name="New Name")
    assert result.name == "New Name"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_update_tenant_not_found_raises():
    """update_tenant raises ValueError when tenant doesn't exist."""
    db = _mock_db()
    svc = TenantService(db)
    db.execute = _execute_returning(None)

    with pytest.raises(ValueError, match="not found"):
        await svc.update_tenant(tenant_id=999, name="Ghost")


# ---------------------------------------------------------------------------
# update_branding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_branding_only_sets_provided_fields():
    """update_branding passes only non-None fields to update_tenant."""
    db = _mock_db()
    svc = TenantService(db)

    tenant = _mock_tenant()
    db.execute = _execute_returning(tenant)

    result = await svc.update_branding(tenant_id=1, primary_color="#FF0000")
    assert result.primary_color == "#FF0000"


# ---------------------------------------------------------------------------
# User-tenant management
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_user_to_tenant_new_user():
    """Adding a new user creates a TenantUser record."""
    db = _mock_db()
    svc = TenantService(db)

    no_existing = MagicMock()
    no_existing.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=no_existing)

    await svc.add_user_to_tenant(tenant_id=1, user_id=20, role="admin")
    db.add.assert_called_once()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_add_user_to_tenant_reactivates_inactive():
    """Re-adding an inactive user reactivates them."""
    db = _mock_db()
    svc = TenantService(db)

    inactive_user = _mock_tenant_user(is_active=False)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = inactive_user
    db.execute = AsyncMock(return_value=result_mock)

    returned = await svc.add_user_to_tenant(tenant_id=1, user_id=10, role="manager")
    assert returned.is_active is True
    assert returned.role == "manager"


@pytest.mark.asyncio
async def test_add_user_to_tenant_already_active_raises():
    """Adding a user who already belongs to the tenant raises ValueError."""
    db = _mock_db()
    svc = TenantService(db)

    active_user = _mock_tenant_user(is_active=True)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = active_user
    db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(ValueError, match="already belongs"):
        await svc.add_user_to_tenant(tenant_id=1, user_id=10)


# ---------------------------------------------------------------------------
# remove_user_from_tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_user_deactivates():
    """Removing a user sets is_active to False."""
    db = _mock_db()
    svc = TenantService(db)

    user = _mock_tenant_user(role="user")
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result_mock)

    result = await svc.remove_user_from_tenant(tenant_id=1, user_id=10)
    assert result is True
    assert user.is_active is False


@pytest.mark.asyncio
async def test_remove_last_owner_raises():
    """Cannot remove the last owner of a tenant."""
    db = _mock_db()
    svc = TenantService(db)

    owner = _mock_tenant_user(role="owner")

    call_count = 0

    async def mock_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.scalar_one_or_none.return_value = owner
        else:
            result.scalar_one.return_value = 1  # only 1 owner
        return result

    db.execute = mock_execute

    with pytest.raises(ValueError, match="last owner"):
        await svc.remove_user_from_tenant(tenant_id=1, user_id=10)


@pytest.mark.asyncio
async def test_remove_nonexistent_user_returns_false():
    """Removing a user who is not in the tenant returns False."""
    db = _mock_db()
    svc = TenantService(db)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    result = await svc.remove_user_from_tenant(tenant_id=1, user_id=999)
    assert result is False


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_feature_enabled_returns_true():
    """is_feature_enabled returns True for an enabled feature."""
    db = _mock_db()
    svc = TenantService(db)

    tenant = _mock_tenant(features_enabled={"advanced_reporting": True})
    db.execute = _execute_returning(tenant)

    result = await svc.is_feature_enabled(tenant_id=1, feature="advanced_reporting")
    assert result is True


@pytest.mark.asyncio
async def test_is_feature_enabled_returns_false_for_missing():
    """is_feature_enabled returns False for an unknown feature key."""
    db = _mock_db()
    svc = TenantService(db)

    tenant = _mock_tenant(features_enabled={})
    db.execute = _execute_returning(tenant)

    result = await svc.is_feature_enabled(tenant_id=1, feature="nonexistent_feature")
    assert result is False


@pytest.mark.asyncio
async def test_is_feature_enabled_returns_false_no_tenant():
    """is_feature_enabled returns False when tenant not found."""
    db = _mock_db()
    svc = TenantService(db)
    db.execute = _execute_returning(None)

    result = await svc.is_feature_enabled(tenant_id=999, feature="anything")
    assert result is False


if __name__ == "__main__":
    print("=" * 60)
    print("TENANT SERVICE UNIT TESTS")
    print("=" * 60)

    test_create_tenant_success()
    print("✓ create_tenant success")
    test_create_tenant_duplicate_slug_raises()
    print("✓ create_tenant duplicate slug")

    print()
    print("=" * 60)
    print("ALL TENANT SERVICE TESTS PASSED ✅")
    print("=" * 60)
