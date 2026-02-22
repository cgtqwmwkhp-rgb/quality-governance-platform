"""Integration tests for multi-tenant data isolation.

Tests verify that:
1. Users can only see data from their own tenant
2. Cross-tenant access attempts are denied (403 or empty results)
"""

import pytest
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType
from src.domain.models.tenant import Tenant
from src.domain.models.user import User
from src.core.security import get_password_hash
from src.core.config import settings


@pytest.mark.asyncio
async def test_user_cannot_see_other_tenant_data(
    client: AsyncClient,
    test_session: AsyncSession,
):
    """Test that a user from tenant A cannot see data from tenant B."""
    # Create two tenants
    tenant_a = Tenant(
        name="Tenant A",
        slug=f"tenant-a-{uuid.uuid4().hex[:8]}",
        admin_email="admin@tenanta.example.com",
        is_active=True,
    )
    tenant_b = Tenant(
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

    # Create users for each tenant
    user_a = User(
        email=f"user-a-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("password123"),
        first_name="User",
        last_name="A",
        is_active=True,
        tenant_id=tenant_a.id,
    )
    user_b = User(
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

    # Create incidents for tenant A
    incident_a1 = Incident(
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
    incident_a2 = Incident(
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

    # Create incidents for tenant B
    incident_b1 = Incident(
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

    # Generate JWT token for user A (tenant A)
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
        user_id=str(user_a.id),
        tenant_id=tenant_a.id,
        role="admin",
        is_superuser=False,
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Query incidents as user A - should only see tenant A's incidents
    response = await client.get(
        "/api/v1/incidents",
        headers=headers_a,
    )

    assert response.status_code == 200
    data = response.json()
    
    # Should only see tenant A's incidents
    incident_ids = [inc["id"] for inc in data.get("items", [])]
    assert incident_a1.id in incident_ids, "Tenant A should see incident_a1"
    assert incident_a2.id in incident_ids, "Tenant A should see incident_a2"
    assert incident_b1.id not in incident_ids, "Tenant A should NOT see tenant B's incidents"


@pytest.mark.asyncio
async def test_cross_tenant_access_denied(
    client: AsyncClient,
    test_session: AsyncSession,
):
    """Test that accessing tenant B's resource with tenant A's token returns 403 or empty result."""
    # Create two tenants
    tenant_a = Tenant(
        name="Tenant A",
        slug=f"tenant-a-{uuid.uuid4().hex[:8]}",
        admin_email="admin@tenanta.example.com",
        is_active=True,
    )
    tenant_b = Tenant(
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

    # Create users for each tenant
    user_a = User(
        email=f"user-a-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("password123"),
        first_name="User",
        last_name="A",
        is_active=True,
        tenant_id=tenant_a.id,
    )
    user_b = User(
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

    # Create an incident for tenant B
    incident_b = Incident(
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

    # Generate JWT token for user A (tenant A) trying to access tenant B's resource
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

    # Attempt to access tenant B's incident with tenant A's token
    response = await client.get(
        f"/api/v1/incidents/{incident_b.id}",
        headers=headers_a,
    )

    # Should return 403 (Forbidden) or 404 (Not Found) - tenant isolation enforced
    assert response.status_code in [403, 404], (
        f"Expected 403 or 404 for cross-tenant access, got {response.status_code}"
    )
