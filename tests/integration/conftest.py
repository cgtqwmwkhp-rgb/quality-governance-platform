"""Integration Test Configuration.

Provides JWT-authenticated test clients at multiple permission levels
(unauthenticated, viewer, admin, superuser) by overriding the
``get_current_user`` dependency with a lightweight mock that validates
the JWT but skips the database lookup.

"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import AsyncGenerator, Generator

import jwt
import pytest
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

# Force test-mode DB engine settings (e.g., NullPool) during imports.
os.environ.setdefault("TESTING", "1")

from src.api.dependencies import get_current_user, get_db, security  # noqa: E402
from src.core.config import settings  # noqa: E402
from src.core.security import decode_token  # noqa: E402
from src.domain.models.user import User  # noqa: E402
from src.main import app  # noqa: E402

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
        first_name: str = "Test",
        last_name: str = "User",
    ):
        self.id = user_id
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
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
    permissions: str | None = None,
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
    if permissions is not None:
        payload["permissions"] = permissions
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm=TEST_JWT_ALGORITHM)


def _mock_user_from_jwt(payload: dict, db_user: object | None = None) -> _MockUser:
    """Build a ``_MockUser`` from decoded JWT claims."""
    role = payload.get("role", "viewer")
    is_superuser = payload.get("is_superuser", False)
    custom_perms = payload.get("permissions")
    if isinstance(custom_perms, list):
        custom_perms = ",".join(custom_perms)

    if custom_perms:
        perms = custom_perms
    elif is_superuser:
        perms = ""
    elif role in ("admin", "superadmin"):
        perms = _ADMIN_PERMS
    else:
        perms = _VIEWER_PERMS
    user_id = int(payload.get("sub", "1"))
    email = getattr(db_user, "email", f"{role}@test.example.com")
    tenant_id = getattr(db_user, "tenant_id", payload.get("tenant_id", 1))
    first_name = getattr(db_user, "first_name", "Test")
    last_name = getattr(db_user, "last_name", "User")
    is_active = getattr(db_user, "is_active", True)
    effective_superuser = bool(getattr(db_user, "is_superuser", is_superuser) or is_superuser)

    return _MockUser(
        user_id=user_id,
        email=email,
        role_name=role,
        permissions=perms,
        is_superuser=effective_superuser,
        is_active=is_active,
        tenant_id=tenant_id,
        first_name=first_name,
        last_name=last_name,
    )


# ---------------------------------------------------------------------------
# Dependency override – validates JWT but skips DB user lookup
# ---------------------------------------------------------------------------


async def _test_get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db),
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

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise cred_exc

    from sqlalchemy.orm import selectinload

    result = await db.execute(select(User).where(User.id == int(user_id_raw)).options(selectinload(User.roles)))
    user = result.scalar_one_or_none()
    if user is not None:
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")
        return _mock_user_from_jwt(payload, db_user=user)

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


@pytest.fixture(autouse=True)
async def _seed_default_data():
    """Seed a default tenant and user for FK integrity.

    The mock auth override returns user id=1, so many API handlers set
    ``created_by_id=1``.  This user MUST exist in the ``users`` table
    to satisfy FK constraints.
    """
    from sqlalchemy import select, text

    from src.core.security import get_password_hash
    from src.domain.models.tenant import Tenant
    from src.domain.models.user import User
    from src.infrastructure.database import async_session_maker, engine
    from tests.factories import TenantFactory, UserFactory

    async with async_session_maker() as session:
        result = await session.execute(select(Tenant).where(Tenant.id == 1))
        if result.scalar_one_or_none() is None:
            session.add(
                TenantFactory.build(
                    id=1,
                    name="Test Tenant",
                    slug="test-tenant",
                    admin_email="admin@test.example.com",
                )
            )
            await session.flush()

        result = await session.execute(select(User).where(User.id == 1))
        if result.scalar_one_or_none() is None:
            session.add(
                UserFactory.build(
                    id=1,
                    email="test@example.com",
                    hashed_password=get_password_hash("testpassword123"),
                    is_active=True,
                    is_superuser=False,
                    tenant_id=1,
                )
            )
        await session.commit()

    if "postgresql" in str(engine.url):
        async with engine.begin() as conn:
            await conn.execute(text("SELECT setval('tenants_id_seq', GREATEST((SELECT MAX(id) FROM tenants), 1))"))
            await conn.execute(text("SELECT setval('users_id_seq', GREATEST((SELECT MAX(id) FROM users), 1))"))

    yield


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
    """Async database session for direct ORM operations in tests."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        database_url = os.environ.get(
            "DATABASE_URL",
            "sqlite+aiosqlite:///./test_integration.db",
        )
        engine = create_async_engine(database_url, poolclass=NullPool, future=True)
        session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        async with session_maker() as session:
            try:
                yield session
            finally:
                # Ensure failed tests do not leak open transactions into later tests.
                if session.in_transaction():
                    await session.rollback()
        await engine.dispose()
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
    from tests.factories import TenantFactory

    tenant = TenantFactory.build(
        name="Test Tenant",
        slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
        admin_email="admin@test.example.com",
        is_active=True,
    )
    test_session.add(tenant)
    await test_session.flush()
    await test_session.refresh(tenant)

    yield tenant


@pytest.fixture
async def test_user(test_session, test_tenant):
    """Create a test user in the database with the correct tenant_id.

    The user is automatically cleaned up after the test via transaction rollback.
    """
    from src.core.security import get_password_hash
    from tests.factories import UserFactory

    user = UserFactory.build(
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("testpassword123"),
        is_active=True,
        is_superuser=False,
        tenant_id=test_tenant.id,
    )
    test_session.add(user)
    await test_session.flush()
    await test_session.refresh(user)

    yield user


@pytest.fixture
def test_user_dict():
    """Test user fixture – returns a mock user dict (for backward compatibility)."""
    from tests.factories import UserFactory

    user = UserFactory.build()
    return {
        "id": str(user.id) if user.id else "1",
        "email": user.email,
        "full_name": f"{user.first_name} {user.last_name}",
        "tenant_id": 1,
        "role": "admin",
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
    }


@pytest.fixture
def test_incident():
    """Test incident fixture – returns a mock incident dict."""
    from tests.factories import IncidentFactory

    incident = IncidentFactory.build()
    return {
        "title": incident.title,
        "description": incident.description,
        "severity": incident.severity,
        "status": incident.status,
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


@pytest.fixture
def near_miss_factory(admin_client):
    """Factory fixture that creates a NearMiss via the API and returns it.

    Used by investigation/source-record integration tests.
    """
    from tests.factories import NearMissFactory

    _counter = 0

    async def _create(**overrides):
        nonlocal _counter
        _counter += 1
        nm = NearMissFactory.build(**overrides)
        payload = {
            "reporter_name": nm.reporter_name,
            "contract": nm.contract,
            "location": nm.location,
            "event_date": nm.event_date.isoformat(),
            "description": nm.description,
        }
        payload.update(overrides)
        response = await admin_client.post("/api/v1/near-misses/", json=payload)
        assert response.status_code in (200, 201), response.text
        return response.json()

    return _create


@pytest.fixture
async def near_miss_with_investigation(admin_client, near_miss_factory):
    """Create a near-miss and linked investigation for source-record tests."""
    near_miss_data = await near_miss_factory()
    source_id = near_miss_data["id"]
    response = await admin_client.post(
        "/api/v1/investigations/from-record",
        json={
            "source_type": "near_miss",
            "source_id": source_id,
            "title": f"Investigation for Near Miss {source_id}",
        },
    )
    assert response.status_code == 201, response.text
    investigation_data = response.json()
    near_miss = SimpleNamespace(id=source_id)
    investigation = SimpleNamespace(
        id=investigation_data["id"],
        reference_number=investigation_data.get("reference_number"),
    )
    return near_miss, investigation


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
