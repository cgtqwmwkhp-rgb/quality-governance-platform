"""Integration Test Configuration."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator

import jwt
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.main import app

TEST_JWT_SECRET = os.environ.get("JWT_SECRET_KEY", "test-jwt-secret-min16chars")
TEST_JWT_ALGORITHM = "HS256"


def _generate_test_jwt(
    user_id: str = "test-user-integration-001",
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


@pytest.fixture
def sync_client() -> Generator[TestClient, None, None]:
    """Synchronous test client for basic integration tests.

    DEPRECATED: Prefer async `client` fixture to avoid event loop conflicts.
    See GOVPLAT-ASYNC-001: Mixing sync TestClient with async fixtures
    (asyncpg pools, etc.) causes "attached to a different loop" errors.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Alias for client fixture for explicit async usage."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Test authentication headers with valid JWT."""
    token = _generate_test_jwt()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_user_id() -> str:
    """Test user ID for integration tests."""
    return "test-user-integration-001"


@pytest.fixture
def superuser_auth_headers() -> dict[str, str]:
    """Superuser authentication headers with valid JWT."""
    token = _generate_test_jwt(
        user_id="test-superuser-001",
        is_superuser=True,
        role="superadmin",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def test_session():
    """Async database session -- requires DATABASE_URL in environment."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url or "sqlite" in db_url:
        pytest.skip("Async DB session requires PostgreSQL DATABASE_URL")
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_async_engine(db_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            yield session
            await session.rollback()
        await engine.dispose()
    except Exception as exc:
        pytest.skip(f"DB session setup failed: {exc}")


@pytest.fixture
def test_user():
    """Test user fixture -- returns a mock user dict."""
    return {
        "id": "test-user-integration-001",
        "email": "test@example.com",
        "full_name": "Test User",
        "tenant_id": 1,
        "role": "admin",
        "is_active": True,
        "is_superuser": False,
    }


@pytest.fixture
def test_incident():
    """Test incident fixture -- returns a mock incident dict."""
    return {
        "title": "Integration Test Incident",
        "description": "Created by integration test",
        "severity": "medium",
        "status": "open",
        "tenant_id": 1,
        "reported_by": "test-user-integration-001",
    }


@pytest.fixture(scope="session")
def database_url() -> str:
    """Get database URL from environment."""
    return os.environ.get(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./test_integration.db",
    )


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
