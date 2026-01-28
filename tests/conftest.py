"""
Pytest Configuration and Shared Fixtures

This module provides shared fixtures for all test suites:
- Smoke tests
- E2E tests
- Integration tests
- Unit tests

PHASE 3 ASYNC HARNESS (PR #104):
Provides a "blessed" async test harness that solves the event loop conflict:
- Session-scoped event loop for all async tests
- Test-specific database engine created within the test event loop
- httpx.AsyncClient with ASGITransport for true async testing
"""

import asyncio
import os
import sys
from typing import Any, AsyncGenerator, Generator, Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================================
# Test Configuration
# ============================================================================


class TestConfig:
    """Global test configuration."""

    # API Configuration
    API_BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")

    # Test Credentials
    TEST_USER_EMAIL = os.getenv("TEST_USER_EMAIL", "testuser@plantexpand.com")
    TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD", "testpassword123")
    ADMIN_USER_EMAIL = os.getenv("ADMIN_USER_EMAIL", "admin@plantexpand.com")
    ADMIN_USER_PASSWORD = os.getenv("ADMIN_USER_PASSWORD", "adminpassword123")

    # Timeouts
    REQUEST_TIMEOUT = 30
    SLOW_TEST_THRESHOLD = 5.0

    # Feature Flags for Tests
    SKIP_SLOW_TESTS = os.getenv("SKIP_SLOW_TESTS", "false").lower() == "true"
    SKIP_INTEGRATION_TESTS = os.getenv("SKIP_INTEGRATION", "false").lower() == "true"


# ============================================================================
# PHASE 3 ASYNC HARNESS - Session-scoped Event Loop
# ============================================================================
# This is the "blessed" async test harness that solves GOVPLAT-003/004/005.
# All async tests share this single event loop, ensuring the DB pool
# is created and used within the same loop.


@pytest.fixture(scope="session")
def event_loop():
    """
    Create a session-scoped event loop for all async tests.

    This is the CRITICAL fix for the "Task got Future attached to a different loop" error.
    By using a session-scoped loop, the database engine's connection pool is created
    in the same loop that all tests use.

    Note: pytest-asyncio 0.21+ recommends event_loop_policy fixture, but
    for compatibility we use this explicit approach.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# PHASE 3 ASYNC HARNESS - Test App Factory
# ============================================================================


@pytest_asyncio.fixture(scope="session")
async def test_app(event_loop):
    """
    Create the FastAPI application within the test event loop.

    This ensures the database engine is created in the test event loop,
    avoiding the "different loop" error.
    """
    # Import here to ensure engine is created in test event loop
    from src.main import create_application
    from src.infrastructure.database import engine, init_db

    app = create_application()

    # Initialize database tables (for test isolation)
    await init_db()

    yield app

    # Cleanup: dispose engine connections
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async HTTP client for testing the ASGI app.

    This is the "blessed" way to test async FastAPI apps:
    - Uses httpx.AsyncClient with ASGITransport
    - Runs in the same event loop as the database
    - Supports async context managers properly
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def async_client_function(test_app) -> AsyncGenerator[AsyncClient, None]:
    """
    Function-scoped async client for tests that need isolation.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ============================================================================
# PHASE 3 ASYNC HARNESS - Database Session for Tests
# ============================================================================


@pytest_asyncio.fixture(scope="function")
async def async_db_session():
    """
    Provide an async database session for tests that need direct DB access.

    Uses transaction rollback for test isolation.
    """
    from src.infrastructure.database import async_session_maker

    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


# ============================================================================
# PHASE 4 WAVE 3 - User Seeding for Auth Tests
# ============================================================================
# These fixtures seed test users into the database ONCE per test session.
# This is required for auth-dependent tests like test_enterprise_e2e.py.


@pytest_asyncio.fixture(scope="session")
async def session_db(test_app):
    """
    Session-scoped database session for seeding operations.
    
    Unlike async_db_session (function-scoped with rollback), this session
    commits changes that persist across all tests in the session.
    
    Must depend on test_app to ensure DB is initialized first.
    """
    from src.infrastructure.database import async_session_maker

    async with async_session_maker() as session:
        yield session
        # No rollback - seeding changes should persist for the session


@pytest_asyncio.fixture(scope="session")
async def seeded_users(session_db):
    """
    Seed test users into the database (idempotent).
    
    Creates or updates:
    - testuser@plantexpand.com (regular user)
    - admin@plantexpand.com (superuser)
    
    This fixture is idempotent: safe to run multiple times.
    Users are created if missing, or flags are corrected if they exist.
    
    Returns dict with user emails (NOT passwords or tokens).
    """
    from sqlalchemy import select
    
    from src.core.security import get_password_hash
    from src.domain.models.user import User
    
    users_config = [
        {
            "email": "testuser@plantexpand.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User",
            "is_superuser": False,
            "is_active": True,
        },
        {
            "email": "admin@plantexpand.com",
            "password": "adminpassword123",
            "first_name": "Admin",
            "last_name": "User",
            "is_superuser": True,
            "is_active": True,
        },
    ]
    
    seeded = {}
    
    for config in users_config:
        email = config["email"]
        
        # Check if user exists
        result = await session_db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            # Create new user
            user = User(
                email=email,
                hashed_password=get_password_hash(config["password"]),
                first_name=config["first_name"],
                last_name=config["last_name"],
                is_superuser=config["is_superuser"],
                is_active=config["is_active"],
            )
            session_db.add(user)
        else:
            # Ensure flags are correct (idempotent update)
            if user.is_superuser != config["is_superuser"]:
                user.is_superuser = config["is_superuser"]
            if user.is_active != config["is_active"]:
                user.is_active = config["is_active"]
        
        seeded[email] = {"email": email, "is_superuser": config["is_superuser"]}
    
    await session_db.commit()
    
    # Log seeding summary (no secrets)
    print(f"\n[SEED] Seeded {len(seeded)} test users: {list(seeded.keys())}")
    
    return seeded


# ============================================================================
# Core Fixtures (Legacy - kept for backwards compatibility)
# ============================================================================


@pytest.fixture(scope="session")
def test_config() -> TestConfig:
    """Provide test configuration."""
    return TestConfig()


@pytest.fixture(scope="session")
def app():
    """Create FastAPI application instance (legacy sync fixture)."""
    from src.main import app as fastapi_app

    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    """Create test client for the application (legacy sync fixture)."""
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture(scope="module")
def module_client(app):
    """Module-scoped test client (legacy sync fixture)."""
    from fastapi.testclient import TestClient

    return TestClient(app)


# ============================================================================
# Authentication Fixtures (PHASE 4 WAVE 3 - Async with Seeded Users)
# ============================================================================
# These fixtures provide JWT auth headers by logging in via /api/v1/auth/login.
# They depend on seeded_users to ensure test users exist in the database.


@pytest_asyncio.fixture(scope="session")
async def async_auth_token(async_client, seeded_users, test_config) -> Optional[str]:
    """
    Get authentication token for test user via real login.
    
    Depends on seeded_users to ensure user exists in DB.
    Uses the correct endpoint path (/api/v1/auth/login) and schema (email, not username).
    """
    response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": test_config.TEST_USER_EMAIL,
            "password": test_config.TEST_USER_PASSWORD,
        },
    )
    
    if response.status_code != 200:
        print(f"[AUTH] Login failed for test user: status={response.status_code}")
        return None
    
    token = response.json().get("access_token")
    if token:
        print("[AUTH] Test user login successful")
    return token


@pytest_asyncio.fixture(scope="session")
async def async_auth_headers(async_auth_token) -> dict:
    """
    Get authenticated headers for regular test user.
    
    Returns {"Authorization": "Bearer <token>"} or {} if login failed.
    Token value is NOT logged.
    """
    if async_auth_token:
        return {"Authorization": f"Bearer {async_auth_token}"}
    return {}


@pytest_asyncio.fixture(scope="session")
async def async_admin_token(async_client, seeded_users, test_config) -> Optional[str]:
    """
    Get authentication token for admin user via real login.
    
    Depends on seeded_users to ensure admin user exists in DB with is_superuser=True.
    """
    response = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": test_config.ADMIN_USER_EMAIL,
            "password": test_config.ADMIN_USER_PASSWORD,
        },
    )
    
    if response.status_code != 200:
        print(f"[AUTH] Login failed for admin user: status={response.status_code}")
        return None
    
    token = response.json().get("access_token")
    if token:
        print("[AUTH] Admin user login successful")
    return token


@pytest_asyncio.fixture(scope="session")
async def async_admin_headers(async_admin_token) -> dict:
    """
    Get authenticated headers for admin user (superuser).
    
    Returns {"Authorization": "Bearer <token>"} or {} if login failed.
    Token value is NOT logged.
    """
    if async_admin_token:
        return {"Authorization": f"Bearer {async_admin_token}"}
    return {}


# ============================================================================
# Legacy Authentication Fixtures (kept for backwards compatibility)
# ============================================================================


@pytest.fixture(scope="session")
def auth_token(client, test_config) -> Optional[str]:
    """Get authentication token for test user (LEGACY - sync)."""
    try:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_config.TEST_USER_EMAIL,
                "password": test_config.TEST_USER_PASSWORD,
            },
        )
        if response.status_code == 200:
            return response.json().get("access_token")
    except Exception:
        pass
    return None


@pytest.fixture(scope="session")
def auth_headers(auth_token) -> dict:
    """Get authenticated headers (LEGACY - sync)."""
    if auth_token:
        return {"Authorization": f"Bearer {auth_token}"}
    return {}


@pytest.fixture(scope="session")
def admin_token(client, test_config) -> Optional[str]:
    """Get authentication token for admin user (LEGACY - sync)."""
    try:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_config.ADMIN_USER_EMAIL,
                "password": test_config.ADMIN_USER_PASSWORD,
            },
        )
        if response.status_code == 200:
            return response.json().get("access_token")
    except Exception:
        pass
    return None


@pytest.fixture(scope="session")
def admin_headers(admin_token) -> dict:
    """Get admin authenticated headers (LEGACY - sync)."""
    if admin_token:
        return {"Authorization": f"Bearer {admin_token}"}
    return {}


@pytest.fixture(scope="module")
def auth_client(client, auth_headers):
    """Client with authentication already applied."""

    class AuthenticatedClient:
        def __init__(self, client, headers):
            self._client = client
            self._headers = headers

        def get(self, url, **kwargs):
            headers = {**self._headers, **kwargs.pop("headers", {})}
            return self._client.get(url, headers=headers, **kwargs)

        def post(self, url, **kwargs):
            headers = {**self._headers, **kwargs.pop("headers", {})}
            return self._client.post(url, headers=headers, **kwargs)

        def put(self, url, **kwargs):
            headers = {**self._headers, **kwargs.pop("headers", {})}
            return self._client.put(url, headers=headers, **kwargs)

        def patch(self, url, **kwargs):
            headers = {**self._headers, **kwargs.pop("headers", {})}
            return self._client.patch(url, headers=headers, **kwargs)

        def delete(self, url, **kwargs):
            headers = {**self._headers, **kwargs.pop("headers", {})}
            return self._client.delete(url, headers=headers, **kwargs)

    return AuthenticatedClient(client, auth_headers)


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def db_session():
    """Create database session for tests."""
    try:
        from src.infrastructure.database import SessionLocal

        session = SessionLocal()
        yield session
        session.close()
    except Exception:
        yield None


@pytest.fixture(scope="function")
def clean_db(db_session):
    """Provide clean database state for each test."""
    yield db_session
    if db_session:
        db_session.rollback()


# ============================================================================
# Test Data Factories
# ============================================================================


@pytest.fixture
def incident_data():
    """Factory for incident test data."""

    def _create_incident(title: str = "Test Incident", severity: str = "medium", **kwargs) -> dict:
        return {
            "title": title,
            "description": kwargs.get("description", "Test incident description"),
            "severity": severity,
            "incident_type": kwargs.get("incident_type", "safety"),
            "location": kwargs.get("location", "Test Location"),
            **kwargs,
        }

    return _create_incident


@pytest.fixture
def risk_data():
    """Factory for risk test data."""

    def _create_risk(title: str = "Test Risk", likelihood: int = 3, impact: int = 3, **kwargs) -> dict:
        return {
            "title": title,
            "description": kwargs.get("description", "Test risk description"),
            "category": kwargs.get("category", "operational"),
            "likelihood": likelihood,
            "impact": impact,
            **kwargs,
        }

    return _create_risk


@pytest.fixture
def portal_report_data():
    """Factory for portal report test data."""

    def _create_report(report_type: str = "incident", title: str = "Test Report", **kwargs) -> dict:
        return {
            "report_type": report_type,
            "title": title,
            "description": kwargs.get("description", "Test report description"),
            "severity": kwargs.get("severity", "low"),
            "is_anonymous": kwargs.get("is_anonymous", True),
            **kwargs,
        }

    return _create_report


# ============================================================================
# Utility Functions (exported for tests)
# ============================================================================


def generate_test_reference(prefix: str = "TEST") -> str:
    """Generate a unique reference number for tests.

    Args:
        prefix: The prefix for the reference (default: "TEST")

    Returns:
        A unique reference string like "TEST-20260121-ABC123"
    """
    import random
    import string
    from datetime import datetime

    date_part = datetime.now().strftime("%Y%m%d")
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{date_part}-{random_part}"


# ============================================================================
# Markers
# ============================================================================


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line("markers", "smoke: marks tests as smoke tests")
    config.addinivalue_line("markers", "security: marks tests as security tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers."""
    skip_slow = pytest.mark.skip(reason="Skipping slow tests")
    skip_integration = pytest.mark.skip(reason="Skipping integration tests")

    for item in items:
        if TestConfig.SKIP_SLOW_TESTS and "slow" in item.keywords:
            item.add_marker(skip_slow)
        if TestConfig.SKIP_INTEGRATION_TESTS and "integration" in item.keywords:
            item.add_marker(skip_integration)


# ============================================================================
# Hooks
# ============================================================================


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Make test results available to fixtures."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Add custom summary to test report."""
    terminalreporter.write_sep("=", "Test Suite Summary")

    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    skipped = len(terminalreporter.stats.get("skipped", []))

    total = passed + failed + skipped
    pass_rate = (passed / total * 100) if total > 0 else 0

    terminalreporter.write_line(f"Total Tests: {total}")
    terminalreporter.write_line(f"Passed: {passed}")
    terminalreporter.write_line(f"Failed: {failed}")
    terminalreporter.write_line(f"Skipped: {skipped}")
    terminalreporter.write_line(f"Pass Rate: {pass_rate:.1f}%")

    if pass_rate >= 95:
        terminalreporter.write_line("✅ PRODUCTION READY", green=True)
    elif pass_rate >= 80:
        terminalreporter.write_line("⚠️ STAGING ONLY", yellow=True)
    else:
        terminalreporter.write_line("❌ NOT READY FOR DEPLOYMENT", red=True)
