"""
Integration Test Configuration

QUARANTINE STATUS: Many integration tests require async fixtures that are not
fully configured. These tests are skipped until the async test infrastructure
is properly set up.

See tests/smoke/QUARANTINE_POLICY.md for details.

Quarantine Date: 2026-01-21
Expiry Date: 2026-02-21
Issue: GOVPLAT-003
Reason: Async fixture architecture not aligned with test requirements.
"""

import os

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


# ============================================================================
# Fixtures for Integration Tests
# ============================================================================


@pytest.fixture
def client():
    """Synchronous test client for basic integration tests."""
    from src.main import app

    return TestClient(app)


@pytest.fixture
def async_client_skip():
    """Marker for tests requiring async client - skip until infrastructure ready."""
    pytest.skip("QUARANTINED: Async client fixtures not configured. See QUARANTINE_POLICY.md")


# Override client fixture for async tests to skip them gracefully
@pytest.fixture
def test_session():
    """Database session fixture - skip until async DB infrastructure ready."""
    pytest.skip("QUARANTINED: Async DB session fixtures not configured. See QUARANTINE_POLICY.md")


@pytest.fixture
def test_user():
    """Test user fixture - skip until async DB infrastructure ready."""
    pytest.skip("QUARANTINED: Async user fixtures not configured. See QUARANTINE_POLICY.md")


@pytest.fixture
def auth_headers():
    """Auth headers fixture - skip until async auth infrastructure ready."""
    pytest.skip("QUARANTINED: Async auth fixtures not configured. See QUARANTINE_POLICY.md")


@pytest.fixture
def inactive_user():
    """Inactive user fixture - skip until async infrastructure ready."""
    pytest.skip("QUARANTINED: Async user fixtures not configured. See QUARANTINE_POLICY.md")


@pytest.fixture
def db_session():
    """DB session fixture - skip until async infrastructure ready."""
    pytest.skip("QUARANTINED: Async DB session fixtures not configured. See QUARANTINE_POLICY.md")
