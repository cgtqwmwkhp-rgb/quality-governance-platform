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
async def test_resolve_user_tenant_context_leaves_user_unchanged_without_membership() -> None:
    user = User(
        id=7,
        email="auditor@example.com",
        hashed_password="hashed",
        first_name="Audit",
        last_name="User",
        tenant_id=None,
    )
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    db = AsyncMock()
    db.execute.return_value = result

    await _resolve_user_tenant_context(db, user)

    assert user.tenant_id is None
