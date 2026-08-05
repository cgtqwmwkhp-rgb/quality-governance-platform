"""Roles assigned at user creation must belong to the user's own organisation.

``Role.name`` is globally unique and parts of the authorisation surface read role
*names* without re-checking tenancy — ``routes/engineers.py:_is_workforce_manager``
treats any role called ``admin`` or ``supervisor`` as workforce management. So ticking
another organisation's ``supervisor`` role onto a new account granted authority in the
wrong organisation. The create route accepted arbitrary ``role_ids`` with no check.

Also covers the tenant membership row, which the route did not write: tenancy is read
from ``users.tenant_id`` to admit a request and from ``tenant_users`` to list an
organisation's members, so writing one without the other leaves them disagreeing.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.domain.models.tenant import Tenant, TenantUser
from src.domain.models.user import Role, User
from src.main import app
from tests.integration.conftest import _generate_test_jwt


def _payload(**overrides):
    suffix = uuid.uuid4().hex[:10]
    body = {
        "email": f"rolecheck-{suffix}@example.com",
        "first_name": "Role",
        "last_name": f"Check{suffix[:4]}",
        "auth_provider": "local",
        "password": "correct horse battery staple",
    }
    body.update(overrides)
    return body


async def _superuser_client(tenant_id=1):
    token = _generate_test_jwt(user_id="2", tenant_id=tenant_id, role="superadmin", is_superuser=True)
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _make_role(session, *, tenant_id):
    role = Role(name=f"supervisor-{uuid.uuid4().hex[:8]}", permissions='["incidents:read"]', tenant_id=tenant_id)
    session.add(role)
    await session.commit()
    return role.id


async def _make_tenant(session):
    tenant = Tenant(
        name="Rival Org",
        slug=f"rival-{uuid.uuid4().hex[:8]}",
        admin_email="admin@rival.example.com",
    )
    session.add(tenant)
    await session.commit()
    return tenant.id


@pytest.mark.asyncio
async def test_a_role_from_another_tenant_is_refused(test_session):
    """AC-01: the cross-organisation grant. Must not be a 201."""
    other_tenant_id = await _make_tenant(test_session)
    foreign_role_id = await _make_role(test_session, tenant_id=other_tenant_id)

    body = _payload(role_ids=[foreign_role_id])
    async with await _superuser_client(tenant_id=1) as client:
        response = await client.post("/api/v1/users/", json=body)

    assert response.status_code == 400, response.text
    assert "different organisation" in response.text
    stored = (await test_session.execute(select(User).where(User.email == body["email"]))).scalar_one_or_none()
    assert stored is None, "a refused create must leave no account behind"


@pytest.mark.asyncio
async def test_a_role_in_the_users_own_tenant_is_accepted(test_session):
    """AC-02: the guard must not break the ordinary case it exists to protect."""
    own_role_id = await _make_role(test_session, tenant_id=1)

    body = _payload(role_ids=[own_role_id])
    async with await _superuser_client(tenant_id=1) as client:
        response = await client.post("/api/v1/users/", json=body)

    assert response.status_code == 201, response.text
    assert [r["id"] for r in response.json()["roles"]] == [own_role_id]


@pytest.mark.asyncio
async def test_a_global_role_stays_assignable(test_session):
    """AC-03: a NULL tenant_id means the role is global, not foreign."""
    global_role_id = await _make_role(test_session, tenant_id=None)

    body = _payload(role_ids=[global_role_id])
    async with await _superuser_client(tenant_id=1) as client:
        response = await client.post("/api/v1/users/", json=body)

    assert response.status_code == 201, response.text
    assert [r["id"] for r in response.json()["roles"]] == [global_role_id]


@pytest.mark.asyncio
async def test_an_unknown_role_id_is_refused_rather_than_ignored(test_session):
    """AC-04: it silently dropped unknown ids, so a typo produced a role-less account."""
    body = _payload(role_ids=[98_765_432])
    async with await _superuser_client(tenant_id=1) as client:
        response = await client.post("/api/v1/users/", json=body)

    assert response.status_code == 400, response.text
    assert "Unknown role" in response.text


@pytest.mark.asyncio
async def test_creation_records_tenant_membership(test_session):
    """AC-05: both sources of tenancy must agree, not just the one that admits requests."""
    body = _payload()
    async with await _superuser_client(tenant_id=1) as client:
        response = await client.post("/api/v1/users/", json=body)
    assert response.status_code == 201, response.text

    stored = (await test_session.execute(select(User).where(User.email == body["email"]))).scalar_one()
    membership = (await test_session.execute(select(TenantUser).where(TenantUser.user_id == stored.id))).scalars().all()

    assert len(membership) == 1, "exactly one membership row, or the member list double-counts"
    assert membership[0].tenant_id == stored.tenant_id, "the two records of tenancy must not disagree"
    assert membership[0].is_active is True
    assert membership[0].is_primary is True, "tenant resolution orders by is_primary first"
