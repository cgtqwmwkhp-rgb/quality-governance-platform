"""SSO must not create an account it cannot place in an organisation.

The provisioning order was inverted: ``exchange_azure_token`` committed the ``User`` and
only then asked which tenant it belonged to. In production ``_default_tenant_for_new_user``
fails closed, so the answer was "none" — after the row was already persisted. The result
is an account that signs in successfully, receives a valid token, renders the application,
and then fails every single request, because ``_resolve_user_tenant_context`` refuses a
tenant-less user. That is the reported symptom "it let me in, but I can't see anything".

It also leaves behind precisely the tenant-less ``users`` row the RLS least-privilege
rollout has to drain before cutover, so every unprovisioned sign-in attempt added work to
a security programme.
"""

import uuid

import pytest
from sqlalchemy import select

from src.domain.models.tenant import TenantUser
from src.domain.models.user import User
from src.domain.services.auth_service import AuthService, TenantProvisioningRequiredError
from src.infrastructure.database import async_session_maker


def _assertion(email, azure_oid):
    return {
        "email": email,
        "oid": azure_oid,
        "name": "Unprovisioned Person",
        "department": "Operations",
        "job_title": "Technician",
    }


async def _exchange(session, monkeypatch, *, email, production, azure_oid=None):
    """Drive exchange_azure_token with a valid assertion and a chosen environment.

    ``azure_oid`` must be held stable across repeat sign-ins by the same person, or the
    service's identity-conflict guard correctly refuses the second one.
    """
    service = AuthService(session)
    oid = azure_oid or uuid.uuid4().hex[:32]
    monkeypatch.setattr(
        "src.domain.services.auth_service.validate_azure_id_token",
        lambda _token: {"sub": "s"},
    )
    monkeypatch.setattr(
        "src.domain.services.auth_service.extract_user_info_from_azure_token",
        lambda _claims: _assertion(email, oid),
    )
    # is_production is a read-only property derived from app_env, so drive it at the root.
    monkeypatch.setattr(
        "src.domain.services.auth_service.settings.app_env",
        "production" if production else "development",
    )
    return await service.exchange_azure_token("any-id-token")


@pytest.mark.asyncio
async def test_production_refuses_and_persists_nothing(test_session, monkeypatch):
    """AC-01: the refusal, and AC-02: no row survives it.

    The second assertion is the one that fails against the old ordering — the account was
    committed before the tenant was ever consulted.
    """
    email = f"unprovisioned-{uuid.uuid4().hex[:10]}@example.com"

    with pytest.raises(TenantProvisioningRequiredError):
        await _exchange(test_session, monkeypatch, email=email, production=True)

    await test_session.rollback()
    stored = (await test_session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    assert stored is None, "a refused sign-in must not leave a locked-out account behind"


@pytest.mark.asyncio
async def test_the_refusal_names_the_organisation_problem(test_session, monkeypatch):
    """AC-03: the message must be actionable, not 'account locked'."""
    email = f"unprovisioned-{uuid.uuid4().hex[:10]}@example.com"

    with pytest.raises(TenantProvisioningRequiredError) as excinfo:
        await _exchange(test_session, monkeypatch, email=email, production=True)

    message = str(excinfo.value).lower()
    assert "organisation" in message
    assert "administrator" in message


@pytest.mark.asyncio
async def test_non_production_still_provisions_and_records_membership(test_session, monkeypatch):
    """AC-04: the fail-closed guard must not break the environments that rely on it.

    And the new account must get its membership row, not just ``users.tenant_id`` — the
    two records of tenancy disagreeing is how accounts end up admitted but invisible.
    """
    email = f"provisioned-{uuid.uuid4().hex[:10]}@example.com"

    user, access_token, refresh_token = await _exchange(test_session, monkeypatch, email=email, production=False)

    assert access_token and refresh_token
    assert user.tenant_id is not None, "a signed-in user with no tenant is locked out"

    membership = (await test_session.execute(select(TenantUser).where(TenantUser.user_id == user.id))).scalars().all()
    assert len(membership) == 1
    assert membership[0].tenant_id == user.tenant_id
    assert membership[0].is_primary is True


@pytest.mark.asyncio
async def test_an_existing_user_signs_in_again_in_production(monkeypatch):
    """AC-05: bound the blast radius. Only brand-new accounts reach the new refusal.

    Someone who already has an account must keep signing in even in production, or this
    change would lock out every existing SSO user.

    Each sign-in gets its own session, because that is what ``get_db`` hands each request.
    Sharing one session across both is not merely unrealistic, it changes the outcome:
    ``refresh`` re-applies eager-load options only for an instance that entered the identity
    map via a query, so a shared session hands the second sign-in the INSERT-created
    instance and produces a MissingGreenlet that no real request can reach.
    """
    email = f"existing-{uuid.uuid4().hex[:10]}@example.com"
    oid = uuid.uuid4().hex[:32]

    async with async_session_maker() as first_request:
        created, first_token, _ = await _exchange(
            first_request, monkeypatch, email=email, production=False, azure_oid=oid
        )
        created_id = created.id
        assert first_token, "a brand-new user must receive a token, not a lazy-load 500"

    async with async_session_maker() as second_request:
        try:
            again, access_token, _refresh = await _exchange(
                second_request, monkeypatch, email=email, production=True, azure_oid=oid
            )
        except TenantProvisioningRequiredError:  # pragma: no cover - the regression guarded
            pytest.fail("an existing SSO user was refused by the new-user provisioning guard")

    assert again.id == created_id
    assert access_token
