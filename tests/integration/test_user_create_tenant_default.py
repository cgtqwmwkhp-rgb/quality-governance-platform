"""A user created through the admin API must land in a usable tenant.

Regression cover for a real production lockout: the admin create form omits
``tenant_id``, the route stored it verbatim, and a NULL-tenant user is refused by
``_resolve_user_tenant_context`` on every single request in production.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.domain.models.engineer import Engineer
from src.domain.models.tenant import Tenant
from src.domain.models.user import User
from src.main import app
from tests.integration.conftest import _generate_test_jwt


def _payload(**overrides):
    suffix = uuid.uuid4().hex[:10]
    body = {
        "email": f"newstarter-{suffix}@example.com",
        "first_name": "New",
        "last_name": f"Starter{suffix[:4]}",
        "auth_provider": "local",
        "password": "correct horse battery staple",
    }
    body.update(overrides)
    return body


async def _client_for(*, tenant_id, user_id="2"):
    """A superuser client whose token carries the given tenant claim (None allowed)."""
    token = _generate_test_jwt(user_id=user_id, tenant_id=tenant_id, role="superadmin", is_superuser=True)
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _fetch_user(session, email):
    return (await session.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()


@pytest.mark.asyncio
async def test_omitted_tenant_inherits_the_creating_admins_tenant(test_session):
    """AC-01: the exact payload the admin UI sends must not produce a NULL tenant."""
    body = _payload()
    async with await _client_for(tenant_id=1) as client:
        response = await client.post("/api/v1/users/", json=body)

    assert response.status_code == 201, response.text
    assert response.json()["tenant_id"] == 1

    stored = await _fetch_user(test_session, body["email"])
    assert stored is not None
    assert stored.tenant_id == 1, "a NULL tenant here is the production lockout"


@pytest.mark.asyncio
async def test_inheriting_a_tenant_also_provisions_the_person_record(test_session):
    """AC-02: the engineer link was skipped entirely while tenant_id was NULL.

    Without a linked Engineer the user cannot be selected as a case owner or
    action assignee, which is the second half of the same lockout.
    """
    body = _payload()
    async with await _client_for(tenant_id=1) as client:
        response = await client.post("/api/v1/users/", json=body)
    assert response.status_code == 201, response.text

    stored = await _fetch_user(test_session, body["email"])
    engineer = (await test_session.execute(select(Engineer).where(Engineer.user_id == stored.id))).scalar_one_or_none()
    assert engineer is not None, "no person record, so the new user is unassignable"
    assert engineer.tenant_id == 1
    assert engineer.is_active is True


@pytest.mark.asyncio
async def test_an_explicit_tenant_still_wins(test_session):
    """AC-03: inheriting must not remove a superuser's ability to place a user."""
    other = Tenant(
        name="Other Org",
        slug=f"other-{uuid.uuid4().hex[:8]}",
        admin_email="admin@other.example.com",
    )
    test_session.add(other)
    await test_session.commit()
    other_id = other.id

    body = _payload(tenant_id=other_id)
    async with await _client_for(tenant_id=1) as client:
        response = await client.post("/api/v1/users/", json=body)

    assert response.status_code == 201, response.text
    assert response.json()["tenant_id"] == other_id


@pytest.mark.asyncio
async def test_a_creator_with_no_tenant_is_refused_and_stores_nothing(test_session):
    """AC-04: fail closed rather than silently persist an unusable account."""
    body = _payload()
    async with await _client_for(tenant_id=None) as client:
        response = await client.post("/api/v1/users/", json=body)

    assert response.status_code == 400, response.text
    assert "tenant_id" in response.text
    assert await _fetch_user(test_session, body["email"]) is None, "a refused create must leave no row"


@pytest.mark.asyncio
async def test_a_nonexistent_tenant_is_a_400_not_a_500(test_session):
    """AC-05: an unvalidated FK surfaces as an unhandled IntegrityError."""
    body = _payload(tenant_id=99_999_999)
    async with await _client_for(tenant_id=1) as client:
        response = await client.post("/api/v1/users/", json=body)

    assert response.status_code == 400, response.text
    assert await _fetch_user(test_session, body["email"]) is None
