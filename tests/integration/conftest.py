"""Integration Test Configuration."""

import os
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
def sync_client() -> Generator[TestClient, None, None]:
    """Synchronous test client for basic integration tests.

    DEPRECATED: Prefer async `client` fixture to avoid event loop conflicts.
    See GOVPLAT-ASYNC-001: Mixing sync TestClient with async fixtures
    (asyncpg pools, etc.) causes "attached to a different loop" errors.

    This fixture is kept for compatibility but should not be used in
    tests that run alongside async tests in the same session.
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
def auth_headers():
    """Test authentication headers - quarantined."""
    pytest.skip("QUARANTINED [GOVPLAT-003]: Auth headers require valid JWT. See tests/QUARANTINE_POLICY.yaml")


@pytest.fixture
def test_user_id() -> str:
    """Test user ID for integration tests."""
    return "test-user-integration-001"


@pytest.fixture
def superuser_auth_headers():
    """Superuser authentication headers - quarantined."""
    pytest.skip("QUARANTINED [GOVPLAT-003]: Superuser auth requires JWT. See tests/QUARANTINE_POLICY.yaml")


@pytest.fixture
async def test_session():
    """Async database session - quarantined."""
    pytest.skip("QUARANTINED [GOVPLAT-003]: Async DB session not configured. See tests/QUARANTINE_POLICY.yaml")


@pytest.fixture
def test_user():
    """Test user fixture - quarantined."""
    pytest.skip("QUARANTINED [GOVPLAT-003]: Test user requires DB session. See tests/QUARANTINE_POLICY.yaml")


@pytest.fixture
def test_incident():
    """Test incident fixture - quarantined."""
    pytest.skip("QUARANTINED [GOVPLAT-003]: Test incident requires DB session. See tests/QUARANTINE_POLICY.yaml")


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
    skip_phase34 = pytest.mark.skip(reason="QUARANTINED [GOVPLAT-001]: Phase 3/4 not implemented. Expiry: 2026-02-21")
    skip_contract = pytest.mark.skip(reason="QUARANTINED [GOVPLAT-002]: API contract mismatch. Expiry: 2026-02-21")

    for item in items:
        if "phase34" in item.keywords:
            item.add_marker(skip_phase34)
        if "api_contract_mismatch" in item.keywords:
            item.add_marker(skip_contract)
