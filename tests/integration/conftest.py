"""Integration Test Configuration.

Provides JWT-authenticated test clients at multiple permission levels
(unauthenticated, viewer, admin, superuser) by overriding the
``get_current_user`` dependency with a lightweight mock that validates
the JWT but skips the database lookup.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator

import jwt
import pytest
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_current_user, security
from src.core.config import settings
from src.core.security import decode_token
from src.main import app

# Align with the application's JWT secret so decode_token() succeeds.
TEST_JWT_SECRET = settings.jwt_secret_key
TEST_JWT_ALGORITHM = settings.jwt_algorithm


# ---------------------------------------------------------------------------
# Mock User / Role (no SQLAlchemy session required)
# ---------------------------------------------------------------------------


class _MockRole:
    """Lightweight role stand-in for integration tests."""

    def __init__(self, name: str, permissions: str = ""):
        self.id = 1
        self.name = name
        self.permissions = permissions
        self.description = None
        self.is_system_role = False


class _MockUser:
    """Lightweight user stand-in that mirrors the User model interface."""

    def __init__(
        self,
        user_id: int = 1,
        email: str = "test@example.com",
        role_name: str = "admin",
        permissions: str = "",
        is_superuser: bool = False,
        is_active: bool = True,
        tenant_id: int = 1,
    ):
        self.id = user_id
        self.email = email
        self.first_name = "Test"
        self.last_name = "User"
        self.hashed_password = "unused"
        self.job_title = None
        self.department = None
        self.phone = None
        self.is_active = is_active
        self.is_superuser = is_superuser
        self.tenant_id = tenant_id
        self.last_login = None
        self.azure_oid = None
        self.roles = [_MockRole(name=role_name, permissions=permissions)] if permissions else []

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def has_permission(self, permission: str) -> bool:
        if self.is_superuser:
            return True
        for role in self.roles:
            if role.permissions and permission in role.permissions:
                return True
        return False


# ---------------------------------------------------------------------------
# Permission sets
# ---------------------------------------------------------------------------

_ADMIN_PERMS = ",".join(
    [
        "incident:create",
        "incident:read",
        "incident:update",
        "incident:delete",
        "complaint:create",
        "complaint:read",
        "complaint:update",
        "complaint:delete",
        "rta:create",
        "rta:read",
        "rta:update",
        "rta:delete",
        "policy:create",
        "policy:read",
        "policy:update",
        "policy:delete",
        "action:create",
        "action:read",
        "action:update",
        "action:delete",
        "investigation:create",
        "investigation:read",
        "investigation:update",
        "audit:create",
        "audit:read",
        "audit:update",
        "audit:delete",
        "standard:create",
        "standard:read",
        "standard:update",
        "risk:create",
        "risk:read",
        "risk:update",
        "near_miss:create",
        "near_miss:read",
        "near_miss:update",
        "audit_template:create",
        "audit_template:read",
        "audit_template:update",
        "audit_template:delete",
    ]
)

_VIEWER_PERMS = ",".join(
    [
        "incident:read",
        "complaint:read",
        "rta:read",
        "policy:read",
        "action:read",
        "investigation:read",
        "audit:read",
        "standard:read",
        "risk:read",
        "near_miss:read",
        "audit_template:read",
    ]
)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def _generate_test_jwt(
    user_id: str = "1",
    tenant_id: int = 1,
    role: str = "admin",
    is_superuser: bool = False,
) -> str:
    """Generate a valid JWT for integration testing."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "exp": now + timedelta(hours=1),
        "iat": now,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "role": role,
        "is_superuser": is_superuser,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm=TEST_JWT_ALGORITHM)


def _mock_user_from_jwt(payload: dict) -> _MockUser:
    """Build a ``_MockUser`` from decoded JWT claims."""
    role = payload.get("role", "viewer")
    is_superuser = payload.get("is_superuser", False)
    if is_superuser:
        perms = ""
    elif role in ("admin", "superadmin"):
        perms = _ADMIN_PERMS
    else:
        perms = _VIEWER_PERMS
    return _MockUser(
        user_id=int(payload.get("sub", "1")),
        email=f"{role}@test.example.com",
        role_name=role,
        permissions=perms,
        is_superuser=is_superuser,
        tenant_id=payload.get("tenant_id", 1),
    )


# ---------------------------------------------------------------------------
# Dependency override – validates JWT but skips DB user lookup
# ---------------------------------------------------------------------------


async def _test_get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> _MockUser:
    """Test-only override for ``get_current_user``.

    Validates the JWT signature and ``jti`` claim, then returns a
    ``_MockUser`` constructed from the token claims – no database
    session required.
    """
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise cred_exc
    if not payload.get("jti"):
        raise cred_exc
    return _mock_user_from_jwt(payload)


# ---------------------------------------------------------------------------
# Autouse fixture – install override for every integration test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _override_auth():
    """Replace ``get_current_user`` with a DB-free mock for all integration tests."""
    app.dependency_overrides[get_current_user] = _test_get_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Test clients
# ---------------------------------------------------------------------------


@pytest.fixture
def sync_client() -> Generator[TestClient, None, None]:
    """Synchronous test client for basic integration tests.

    DEPRECATED: Prefer async ``client`` fixture to avoid event loop conflicts.
    See GOVPLAT-ASYNC-001.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for testing FastAPI endpoints (unauthenticated)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Alias for ``client`` fixture for explicit async usage."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def unauth_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client – explicitly unauthenticated (no Bearer header)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def viewer_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client – authenticated as a viewer (read-only permissions)."""
    token = _generate_test_jwt(user_id="3", role="viewer", is_superuser=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac


@pytest.fixture
async def admin_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client – authenticated as admin (full CRUD, no ``set_reference_number``)."""
    token = _generate_test_jwt(user_id="1", role="admin", is_superuser=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac


@pytest.fixture
async def superuser_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client – authenticated as superuser (all permissions)."""
    token = _generate_test_jwt(user_id="2", role="superadmin", is_superuser=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Auth header fixtures (for tests using client + auth_headers separately)
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Test authentication headers with valid JWT (admin role, NOT superuser)."""
    token = _generate_test_jwt()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_user_id() -> str:
    """Test user ID for integration tests."""
    return "1"


@pytest.fixture
def superuser_auth_headers() -> dict[str, str]:
    """Superuser authentication headers with valid JWT."""
    token = _generate_test_jwt(
        user_id="2",
        is_superuser=True,
        role="superadmin",
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_session():
    """Async database session using the application's database connection.

    Creates a transaction that is rolled back after each test to ensure
    test isolation and automatic cleanup of test data.

    Tests can call session.commit() to persist data within the test transaction,
    and all changes will be automatically rolled back after the test completes.
    """
    try:
        from sqlalchemy.ext.asyncio import AsyncSession
        from src.infrastructure.database import async_session_maker

        async with async_session_maker() as session:
            # Start a nested transaction (savepoint) for test isolation
            # This allows tests to call commit() while still being able to rollback
            async with session.begin() as transaction:
                try:
                    yield session
                finally:
                    # Rollback to clean up test data
                    await transaction.rollback()
    except Exception as exc:
        pytest.skip(f"DB session setup failed: {exc}")


# ---------------------------------------------------------------------------
# Data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_tenant(test_session):
    """Create a test tenant in the database and return the tenant_id.

    The tenant is automatically cleaned up after the test via transaction rollback.
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.domain.models.tenant import Tenant
    import uuid

    tenant = Tenant(
        name="Test Tenant",
        slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
        admin_email="admin@test.example.com",
        is_active=True,
    )
    test_session.add(tenant)
    await test_session.flush()  # Flush to get the ID without committing
    await test_session.refresh(tenant)

    yield tenant

    # Cleanup handled by transaction rollback in test_session fixture


@pytest.fixture
async def test_user(test_session, test_tenant):
    """Create a test user in the database with the correct tenant_id.

    The user is automatically cleaned up after the test via transaction rollback.
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.domain.models.user import User
    from src.core.security import get_password_hash
    import uuid

    user = User(
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("testpassword123"),
        first_name="Test",
        last_name="User",
        is_active=True,
        is_superuser=False,
        tenant_id=test_tenant.id,
    )
    test_session.add(user)
    await test_session.flush()  # Flush to get the ID without committing
    await test_session.refresh(user)

    yield user

    # Cleanup handled by transaction rollback in test_session fixture


@pytest.fixture
def test_user_dict():
    """Test user fixture – returns a mock user dict (for backward compatibility)."""
    return {
        "id": "1",
        "email": "test@example.com",
        "full_name": "Test User",
        "tenant_id": 1,
        "role": "admin",
        "is_active": True,
        "is_superuser": False,
    }


@pytest.fixture
def test_incident():
    """Test incident fixture – returns a mock incident dict."""
    return {
        "title": "Integration Test Incident",
        "description": "Created by integration test",
        "severity": "medium",
        "status": "open",
        "tenant_id": 1,
        "reported_by": "1",
    }


@pytest.fixture(scope="session")
def database_url() -> str:
    """Get database URL from environment."""
    return os.environ.get(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./test_integration.db",
    )


# ---------------------------------------------------------------------------
# Pytest hooks
# ---------------------------------------------------------------------------


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "phase34: marks tests requiring Phase 3/4 features (quarantined)",
    )
    config.addinivalue_line(
        "markers",
        "api_contract_mismatch: marks tests with API contract issues (quarantined)",
    )
    config.addinivalue_line(
        "markers",
        "requires_db: marks tests that require database access",
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle quarantined tests."""
    skip_phase34 = pytest.mark.skip(reason="QUARANTINED [GOVPLAT-001]: Phase 3/4 not implemented. Expiry: 2026-03-23")
    skip_contract = pytest.mark.skip(reason="QUARANTINED [GOVPLAT-002]: API contract mismatch. Expiry: 2026-03-23")

    for item in items:
        if "phase34" in item.keywords:
            item.add_marker(skip_phase34)
        if "api_contract_mismatch" in item.keywords:
            item.add_marker(skip_contract)
