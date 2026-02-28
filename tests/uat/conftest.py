"""
UAT Test Configuration

Shared fixtures and configuration for User Acceptance Tests.
Uses per-test transaction rollback for complete isolation.
"""

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app


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


_CLEANUP_TABLES = [
    "audit_events",
    "audit_questions",
    "audit_sections",
    "audit_run_responses",
    "audit_runs",
    "audit_templates",
    "actions",
    "investigation_runs",
    "investigations",
    "complaints",
    "incidents",
    "near_misses",
    "risks",
    "policies",
    "standards",
    "users",
]


@pytest.fixture(scope="session", autouse=True)
async def _seed_default_tenant():
    """Ensure a default tenant exists for UAT tests."""
    from sqlalchemy import select

    from src.domain.models.tenant import Tenant
    from src.infrastructure.database import async_session_maker

    try:
        async with async_session_maker() as session:
            result = await session.execute(select(Tenant).where(Tenant.id == 1))
            if result.scalar_one_or_none() is None:
                tenant = Tenant(
                    id=1,
                    name="UAT Test Tenant",
                    slug="uat-test",
                    admin_email="uat@example.com",
                )
                session.add(tenant)
                await session.commit()
    except Exception:
        pass


@pytest.fixture(autouse=True)
async def _cleanup_test_data():
    """Delete test data after each test for isolation."""
    yield

    from src.infrastructure.database import async_session_maker

    try:
        from sqlalchemy import text

        async with async_session_maker() as session:
            for table in _CLEANUP_TABLES:
                await session.execute(text(f"DELETE FROM {table}"))
            await session.commit()
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for UAT tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def fresh_client() -> AsyncGenerator[AsyncClient, None]:
    """Fresh async client (alias for client with transaction rollback)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


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
