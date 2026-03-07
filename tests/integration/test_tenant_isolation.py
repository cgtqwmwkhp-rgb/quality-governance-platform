"""Integration tests for multi-tenant data isolation.

Tests verify that:
1. Users can only see data from their own tenant
2. Cross-tenant access attempts are denied (403 or empty results)
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import get_password_hash
from src.domain.models.incident import IncidentSeverity, IncidentStatus, IncidentType
from src.domain.models.user import User
from tests.factories import IncidentFactory, TenantFactory, UserFactory


@pytest.mark.asyncio
async def test_user_cannot_see_other_tenant_data(
    client: AsyncClient,
    test_session: AsyncSession,
):
    """Test that a user from tenant A cannot see data from tenant B."""
    tenant_a = TenantFactory.build(
        name="Tenant A",
        slug=f"tenant-a-{uuid.uuid4().hex[:8]}",
        admin_email="admin@tenanta.example.com",
        is_active=True,
    )
    tenant_b = TenantFactory.build(
        name="Tenant B",
        slug=f"tenant-b-{uuid.uuid4().hex[:8]}",
        admin_email="admin@tenantb.example.com",
        is_active=True,
    )
    test_session.add(tenant_a)
    test_session.add(tenant_b)
    await test_session.flush()
    await test_session.refresh(tenant_a)
    await test_session.refresh(tenant_b)

    user_a = UserFactory.build(
        email=f"user-a-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("password123"),
        first_name="User",
        last_name="A",
        is_active=True,
        tenant_id=tenant_a.id,
    )
    user_b = UserFactory.build(
        email=f"user-b-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("password123"),
        first_name="User",
        last_name="B",
        is_active=True,
        tenant_id=tenant_b.id,
    )
    test_session.add(user_a)
    test_session.add(user_b)
    await test_session.flush()
    await test_session.refresh(user_a)
    await test_session.refresh(user_b)

    incident_a1 = IncidentFactory.build(
        title="Tenant A Incident 1",
        description="First incident for tenant A",
        incident_type=IncidentType.QUALITY,
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.REPORTED,
        incident_date=datetime.now(timezone.utc),
        reported_date=datetime.now(timezone.utc),
        tenant_id=tenant_a.id,
        reporter_id=user_a.id,
        created_by_id=user_a.id,
        updated_by_id=user_a.id,
    )
    incident_a2 = IncidentFactory.build(
        title="Tenant A Incident 2",
        description="Second incident for tenant A",
        incident_type=IncidentType.QUALITY,
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.REPORTED,
        incident_date=datetime.now(timezone.utc),
        reported_date=datetime.now(timezone.utc),
        tenant_id=tenant_a.id,
        reporter_id=user_a.id,
        created_by_id=user_a.id,
        updated_by_id=user_a.id,
    )

    incident_b1 = IncidentFactory.build(
        title="Tenant B Incident 1",
        description="First incident for tenant B",
        incident_type=IncidentType.QUALITY,
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.REPORTED,
        incident_date=datetime.now(timezone.utc),
        reported_date=datetime.now(timezone.utc),
        tenant_id=tenant_b.id,
        reporter_id=user_b.id,
        created_by_id=user_b.id,
        updated_by_id=user_b.id,
    )

    test_session.add(incident_a1)
    test_session.add(incident_a2)
    test_session.add(incident_b1)
    await test_session.flush()

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_a.id),
        "exp": now + timedelta(hours=1),
        "iat": now,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "tenant_id": tenant_a.id,
        "role": "admin",
        "is_superuser": False,
    }
    token_a = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    response = await client.get(
        "/api/v1/incidents/",
        headers=headers_a,
    )

    assert response.status_code == 200
    data = response.json()

    incident_ids = [inc["id"] for inc in data.get("items", [])]
    # Some implementations apply extra scoping (e.g. ownership), so we only
    # assert that tenant-B data is not leaked.
    assert incident_b1.id not in incident_ids, "Tenant A should NOT see tenant B's incidents"


@pytest.mark.asyncio
async def test_cross_tenant_access_denied(
    client: AsyncClient,
    test_session: AsyncSession,
):
    """Test that accessing tenant B's resource with tenant A's token returns 403 or empty result."""
    tenant_a = TenantFactory.build(
        name="Tenant A",
        slug=f"tenant-a-{uuid.uuid4().hex[:8]}",
        admin_email="admin@tenanta.example.com",
        is_active=True,
    )
    tenant_b = TenantFactory.build(
        name="Tenant B",
        slug=f"tenant-b-{uuid.uuid4().hex[:8]}",
        admin_email="admin@tenantb.example.com",
        is_active=True,
    )
    test_session.add(tenant_a)
    test_session.add(tenant_b)
    await test_session.flush()
    await test_session.refresh(tenant_a)
    await test_session.refresh(tenant_b)

    user_a = UserFactory.build(
        email=f"user-a-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("password123"),
        first_name="User",
        last_name="A",
        is_active=True,
        tenant_id=tenant_a.id,
    )
    user_b = UserFactory.build(
        email=f"user-b-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("password123"),
        first_name="User",
        last_name="B",
        is_active=True,
        tenant_id=tenant_b.id,
    )
    test_session.add(user_a)
    test_session.add(user_b)
    await test_session.flush()
    await test_session.refresh(user_a)
    await test_session.refresh(user_b)

    incident_b = IncidentFactory.build(
        title="Tenant B Incident",
        description="Incident for tenant B",
        incident_type=IncidentType.QUALITY,
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.REPORTED,
        incident_date=datetime.now(timezone.utc),
        reported_date=datetime.now(timezone.utc),
        tenant_id=tenant_b.id,
        reporter_id=user_b.id,
        created_by_id=user_b.id,
        updated_by_id=user_b.id,
    )
    test_session.add(incident_b)
    await test_session.flush()
    await test_session.refresh(incident_b)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_a.id),
        "exp": now + timedelta(hours=1),
        "iat": now,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "tenant_id": tenant_a.id,
        "role": "admin",
        "is_superuser": False,
    }
    token_a = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    response = await client.get(
        f"/api/v1/incidents/{incident_b.id}",
        headers=headers_a,
    )

    assert response.status_code in [
        403,
        404,
    ], f"Expected 403 or 404 for cross-tenant access, got {response.status_code}"
