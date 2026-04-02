from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.dependencies import _resolve_user_tenant_context
from src.domain.models.tenant import TenantUser
from src.domain.models.user import User


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
async def test_resolve_user_tenant_context_leaves_user_unchanged_without_membership_or_tenant() -> None:
    """When no TenantUser membership AND no active Tenant exist, tenant_id stays None."""
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

    assert user.tenant_id is None


@pytest.mark.asyncio
async def test_resolve_user_tenant_context_auto_assigns_tenant_when_no_membership() -> None:
    """When no TenantUser membership exists but an active Tenant does, auto-assign it."""
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
