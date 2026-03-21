"""
Pytest Configuration and Shared Fixtures

This module provides shared fixtures for all test suites:
- Smoke tests
- E2E tests
- Integration tests
- Unit tests
"""

import os
import sys
from typing import Any, Generator, Optional

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if sys.version_info < (3, 11):
    raise RuntimeError(
        "QGP tests require Python 3.11+. "
        f"Detected {sys.version.split()[0]}. "
        "Use python3.11 (or a toolchain that honors .python-version) before running pytest."
    )


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
# Core Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def test_config() -> TestConfig:
    """Provide test configuration."""
    return TestConfig()


@pytest.fixture(scope="session")
def app():
    """Create FastAPI application instance."""
    from src.main import app as fastapi_app

    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    """Create test client for the application."""
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def async_client(client):
    """Async-style adapter around the shared sync test client."""

    class AsyncClientAdapter:
        async def get(self, url, **kwargs):
            return client.get(url, **kwargs)

        async def post(self, url, **kwargs):
            return client.post(url, **kwargs)

        async def put(self, url, **kwargs):
            return client.put(url, **kwargs)

        async def patch(self, url, **kwargs):
            return client.patch(url, **kwargs)

        async def delete(self, url, **kwargs):
            return client.delete(url, **kwargs)

        async def request(self, method, url, **kwargs):
            return client.request(method, url, **kwargs)

    return AsyncClientAdapter()


@pytest.fixture(scope="module")
def module_client(app):
    """Module-scoped test client."""
    from fastapi.testclient import TestClient

    return TestClient(app)


# ============================================================================
# Authentication Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def auth_token(client, test_config) -> Optional[str]:
    """Get authentication token for test user."""
    try:
        payloads = [
            {"email": test_config.TEST_USER_EMAIL, "password": test_config.TEST_USER_PASSWORD},
            {"username": test_config.TEST_USER_EMAIL, "password": test_config.TEST_USER_PASSWORD},
        ]
        paths = ["/api/v1/auth/login", "/api/auth/login"]
        for path in paths:
            for payload in payloads:
                response = client.post(path, json=payload)
                if response.status_code == 200:
                    return response.json().get("access_token")
    except Exception:
        pass
    return None


@pytest.fixture(scope="session")
def auth_headers(auth_token) -> dict:
    """Get authenticated headers."""
    if auth_token:
        return {"Authorization": f"Bearer {auth_token}"}
    return {}


@pytest.fixture(scope="session")
def admin_token(client, test_config) -> Optional[str]:
    """Get authentication token for admin user."""
    try:
        payloads = [
            {"email": test_config.ADMIN_USER_EMAIL, "password": test_config.ADMIN_USER_PASSWORD},
            {"username": test_config.ADMIN_USER_EMAIL, "password": test_config.ADMIN_USER_PASSWORD},
        ]
        paths = ["/api/v1/auth/login", "/api/auth/login"]
        for path in paths:
            for payload in payloads:
                response = client.post(path, json=payload)
                if response.status_code == 200:
                    return response.json().get("access_token")
    except Exception:
        pass
    return None


@pytest.fixture(scope="session")
def admin_headers(admin_token) -> dict:
    """Get admin authenticated headers."""
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
    """Factory for incident test data, backed by IncidentFactory."""
    from tests.factories import IncidentFactory

    def _create_incident(title: str = "Test Incident", severity: str = "medium", **kwargs) -> dict:
        incident = IncidentFactory.build(title=title, severity=severity, **kwargs)
        return {
            "title": incident.title,
            "description": kwargs.get("description", incident.description),
            "severity": str(incident.severity),
            "incident_type": kwargs.get("incident_type", str(incident.incident_type)),
            "location": kwargs.get("location", "Test Location"),
            **kwargs,
        }

    return _create_incident


@pytest.fixture
def risk_data():
    """Factory for risk test data, backed by RiskFactory."""
    from tests.factories import RiskFactory

    def _create_risk(title: str = "Test Risk", likelihood: int = 3, impact: int = 3, **kwargs) -> dict:
        risk = RiskFactory.build(title=title, likelihood=likelihood, impact=impact, **kwargs)
        return {
            "title": risk.title,
            "description": kwargs.get("description", risk.description),
            "category": kwargs.get("category", risk.category),
            "likelihood": risk.likelihood,
            "impact": risk.impact,
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


_test_ref_counter = 0


def generate_test_reference(prefix: str = "TEST") -> str:
    """Generate a unique, deterministic reference number for tests.

    Uses a monotonic counter instead of random characters so that
    test output is reproducible across runs.
    """
    global _test_ref_counter
    _test_ref_counter += 1
    return f"{prefix}-20260115-{_test_ref_counter:06d}"


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
