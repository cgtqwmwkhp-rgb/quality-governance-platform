"""
UAT Test Configuration

Shared fixtures and configuration for User Acceptance Tests.

IMPORTANT: These tests require proper async isolation to prevent
the "attached to a different loop" error when database operations
are involved. Each test gets a fresh async context.

Note: Some UAT tests involving database operations may fail due to
event loop contamination from asyncpg connection pools. These failures
identify real integration issues between the app's DB layer and the
test infrastructure.
"""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app

# Configure pytest-asyncio to use strict mode with function scope
# pytest_plugins moved to root conftest per pytest deprecation rules


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


def pytest_configure(config):
    """Register custom markers for UAT tests."""
    config.addinivalue_line(
        "markers",
        "uat: marks tests as User Acceptance Tests",
    )
    config.addinivalue_line(
        "markers",
        "stage1: marks basic UAT tests (Stage 1)",
    )
    config.addinivalue_line(
        "markers",
        "stage2: marks sophisticated UAT tests (Stage 2)",
    )


@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for UAT tests with proper lifecycle management.

    This fixture ensures:
    1. Each test gets a fresh AsyncClient
    2. The app's lifespan events are properly triggered
    3. Database connections are disposed after each test

    IMPORTANT: Database engine is disposed after each test to prevent
    event loop contamination from asyncpg connection pool futures.
    """
    from src.infrastructure.database import engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Dispose engine to prevent event loop contamination
    # This ensures each test gets fresh connections
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def fresh_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Fresh async client with guaranteed clean database state.

    Use this for tests that absolutely require DB isolation.
    The engine is disposed both before and after the test.
    """
    from src.infrastructure.database import engine

    # Dispose any stale connections before test
    await engine.dispose()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Dispose after test
    await engine.dispose()


@pytest.fixture(scope="session")
def uat_config():
    """UAT test configuration."""
    return {
        "base_url": "http://test",
        "timeout": 30,
        "max_retries": 3,
    }


# ============================================================================
# Data Fixtures
# ============================================================================


@pytest.fixture
def valid_incident_report():
    """Valid incident report data for employee portal."""
    return {
        "report_type": "incident",
        "title": "UAT Test - Slip hazard near entrance",
        "description": "Water leak causing slippery floor near main entrance. "
        "Multiple employees have reported near-misses.",
        "location": "Building A - Main Entrance",
        "severity": "high",
        "reporter_name": "UAT Test User",
        "reporter_email": "uat.test@example.com",
        "department": "Operations",
        "is_anonymous": False,
    }


@pytest.fixture
def valid_complaint_report():
    """Valid complaint report data for employee portal."""
    return {
        "report_type": "complaint",
        "title": "UAT Test - Service quality concern",
        "description": "Repeated delays in equipment maintenance requests. "
        "This has impacted productivity significantly.",
        "severity": "medium",
        "reporter_name": "UAT Complainant",
        "reporter_email": "uat.complainant@example.com",
        "is_anonymous": False,
    }


@pytest.fixture
def anonymous_report():
    """Anonymous report data."""
    return {
        "report_type": "incident",
        "title": "UAT Test - Anonymous safety concern",
        "description": "Confidential safety concern requiring investigation.",
        "severity": "critical",
        "is_anonymous": True,
    }
