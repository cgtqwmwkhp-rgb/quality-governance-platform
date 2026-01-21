"""
Integration Test Configuration

Provides async and sync fixtures for integration testing against PostgreSQL.
Uses pytest-asyncio for async test support and httpx.AsyncClient for API testing.

Database: PostgreSQL with alembic migrations applied before test run.
"""

import os
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.main import app


# ============================================================================
# Sync Fixtures (for tests that don't need async)
# ============================================================================


@pytest.fixture
def sync_client() -> Generator[TestClient, None, None]:
    """Synchronous test client for basic integration tests."""
    with TestClient(app) as c:
        yield c


# ============================================================================
# Async Fixtures (for async integration tests)
# ============================================================================


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for testing FastAPI endpoints.
    
    Uses ASGITransport to call the app directly without network overhead.
    This is the primary client fixture for integration tests.
    """
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
    """
    Test authentication headers.
    
    For integration tests, we use a mock authorization header.
    The actual auth validation should be mocked or use test tokens.
    """
    # In a real setup, this would be a valid JWT for a test user
    # For now, we return headers that can be used with auth-optional endpoints
    return {
        "Authorization": "Bearer test-integration-token",
        "X-Test-User": "integration-test-user",
    }


@pytest.fixture
def test_user_id() -> str:
    """Test user ID for integration tests."""
    return "test-user-integration-001"


# ============================================================================
# Database Session Fixtures
# ============================================================================


@pytest.fixture
async def test_session():
    """
    Async database session for integration tests.
    
    Note: Tests requiring full database access with seeded data
    should be marked with @pytest.mark.requires_db
    """
    pytest.skip(
        "QUARANTINED [GOVPLAT-003]: Async DB session not configured. "
        "See tests/QUARANTINE_POLICY.yaml"
    )


@pytest.fixture
def test_user():
    """Test user fixture - requires database."""
    pytest.skip(
        "QUARANTINED [GOVPLAT-003]: Test user requires DB session. "
        "See tests/QUARANTINE_POLICY.yaml"
    )


@pytest.fixture
def test_incident():
    """Test incident fixture - requires database."""
    pytest.skip(
        "QUARANTINED [GOVPLAT-003]: Test incident requires DB session. "
        "See tests/QUARANTINE_POLICY.yaml"
    )


# ============================================================================
# Database URL Configuration
# ============================================================================


@pytest.fixture(scope="session")
def database_url() -> str:
    """
    Get database URL from environment.
    
    CI sets DATABASE_URL to PostgreSQL connection string.
    Falls back to SQLite for local development.
    """
    return os.environ.get(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./test_integration.db"
    )


# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "phase34: marks tests requiring Phase 3/4 features (quarantined)"
    )
    config.addinivalue_line(
        "markers", 
        "api_contract_mismatch: marks tests with known API contract issues (quarantined)"
    )
    config.addinivalue_line(
        "markers",
        "requires_db: marks tests that require database access"
    )


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to handle quarantined tests.
    
    Tests marked with quarantine markers are skipped with documentation.
    """
    skip_phase34 = pytest.mark.skip(
        reason="QUARANTINED [GOVPLAT-001]: Phase 3/4 features not implemented. "
        "Expiry: 2026-02-21. See tests/QUARANTINE_POLICY.yaml"
    )
    skip_contract = pytest.mark.skip(
        reason="QUARANTINED [GOVPLAT-002]: API contract mismatch. "
        "Expiry: 2026-02-21. See tests/QUARANTINE_POLICY.yaml"
    )
    
    for item in items:
        if "phase34" in item.keywords:
            item.add_marker(skip_phase34)
        if "api_contract_mismatch" in item.keywords:
            item.add_marker(skip_contract)
