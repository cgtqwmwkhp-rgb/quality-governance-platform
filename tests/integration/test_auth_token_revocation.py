"""Integration tests for access-token revocation and production tenant fail-closed."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from src.core.security import create_access_token, create_refresh_token, decode_token
from src.domain.models.tenant import Tenant, TenantUser
from src.domain.models.token_blacklist import TokenBlacklist
from src.domain.services.auth_service import AuthService
from src.domain.services.token_service import TokenService


@pytest.mark.asyncio
async def test_logout_revokes_access_and_refresh_tokens(test_session, test_user):
    """Logout must blacklist the presented access token and optional refresh token."""
    access = create_access_token(subject=test_user.id)
    refresh = create_refresh_token(subject=test_user.id)
    access_jti = decode_token(access)["jti"]
    refresh_jti = decode_token(refresh)["jti"]

    service = AuthService(test_session)
    await service.logout(access, refresh_token=refresh)

    assert await TokenService.is_revoked(test_session, access_jti) is True
    assert await TokenService.is_revoked(test_session, refresh_jti) is True


@pytest.mark.asyncio
async def test_revoked_access_token_rejected_by_me_endpoint(client, test_session, test_user):
    """After blacklist, authenticated REST endpoints return 401 TOKEN_REVOKED."""
    access = create_access_token(subject=test_user.id)
    payload = decode_token(access)
    assert payload is not None

    await TokenService.revoke_token(
        db=test_session,
        jti=payload["jti"],
        user_id=test_user.id,
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        reason="logout",
    )

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 401
    body = response.json()
    error = body.get("error") or body.get("detail") or body
    if isinstance(error, dict) and "error" in error:
        error = error["error"]
    code = error.get("code") if isinstance(error, dict) else None
    assert code == "TOKEN_REVOKED"


@pytest.mark.asyncio
async def test_auth_service_skips_silent_tenant_assignment_in_production(
    monkeypatch: pytest.MonkeyPatch,
):
    """Production Azure/user bootstrap must not silently assign the first tenant."""
    monkeypatch.setattr("src.domain.services.auth_service.settings.app_env", "production")

    user = MagicMock()
    user.id = 42
    user.tenant_id = None

    no_membership = MagicMock()
    no_membership.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute.return_value = no_membership

    service = AuthService(db)
    result = await service._resolve_default_tenant(user)

    assert result is None
    assert user.tenant_id is None
    db.add.assert_not_called()
    # Must not query tenants / commit when production fail-closed.
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_integration_override_honours_blacklist(client, test_session, test_user):
    """Integration auth override must not bypass jti blacklist checks."""
    access = create_access_token(subject=1)  # seeded default user id=1
    payload = decode_token(access)
    assert payload is not None

    test_session.add(
        TokenBlacklist(
            jti=payload["jti"],
            user_id=1,
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            reason="logout",
        )
    )
    await test_session.commit()

    response = await client.get(
        "/api/v1/auth/whoami",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 401
    body = response.json()
    error = body.get("error") or {}
    assert error.get("code") == "TOKEN_REVOKED" or (
        isinstance(body.get("detail"), dict) and body["detail"].get("code") == "TOKEN_REVOKED"
    )


@pytest.mark.asyncio
async def test_production_dependencies_do_not_create_default_organisation(
    monkeypatch: pytest.MonkeyPatch,
    test_session,
):
    """Fail-closed: production path never inserts Default Organisation."""
    from fastapi import HTTPException

    from src.api.dependencies import _resolve_user_tenant_context
    from src.core.security import get_password_hash
    from tests.factories import UserFactory

    monkeypatch.setattr("src.api.dependencies.settings.app_env", "production")

    # Ensure no active tenants so non-prod would have bootstrapped.
    existing = (await test_session.execute(select(Tenant))).scalars().all()
    for tenant in existing:
        tenant.is_active = False
    await test_session.commit()

    user = UserFactory.build(
        email=f"orphan-{datetime.now(timezone.utc).timestamp()}@example.com",
        hashed_password=get_password_hash("testpassword123"),
        is_active=True,
        is_superuser=False,
        tenant_id=None,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    user_id = user.id

    with pytest.raises(HTTPException) as exc_info:
        await _resolve_user_tenant_context(test_session, user)

    assert exc_info.value.status_code == 403
    await test_session.rollback()

    defaults = await test_session.execute(select(Tenant).where(Tenant.slug == "default", Tenant.is_active == True))
    assert defaults.scalar_one_or_none() is None
    memberships = await test_session.execute(select(TenantUser).where(TenantUser.user_id == user_id))
    assert memberships.scalars().first() is None
