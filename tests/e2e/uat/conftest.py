"""
UAT E2E Test Configuration

Provides fixtures and utilities for UAT workflow testing:
- Deterministic test data from seed
- Role-based authentication
- API client helpers
- Assertion utilities for stable ordering
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, Optional

import pytest

# Add scripts to path for seed data access
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts" / "uat"))

from seed_data import UATSeedGenerator, generate_deterministic_uuid  # noqa: E402

# =============================================================================
# UAT TEST CONFIGURATION
# =============================================================================


@dataclass
class UATConfig:
    """UAT test configuration."""

    base_url: str
    environment: str
    seed_version: str
    admin_username: str
    admin_password: str
    user_username: str
    user_password: str


def get_uat_config() -> UATConfig:
    """Get UAT configuration from environment or defaults."""
    return UATConfig(
        base_url=os.environ.get("UAT_BASE_URL", "http://localhost:8000"),
        environment=os.environ.get("APP_ENV", "test"),
        seed_version="1.0.0",
        admin_username="uat_admin",
        admin_password="UatTestPass123!",
        user_username="uat_user",
        user_password="UatTestPass123!",
    )


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def uat_config() -> UATConfig:
    """Provide UAT configuration."""
    return get_uat_config()


@pytest.fixture(scope="session")
def seed_generator() -> UATSeedGenerator:
    """Provide seed data generator with deterministic IDs."""
    generator = UATSeedGenerator()
    generator.generate_all()
    return generator


@pytest.fixture(scope="session")
def uat_user_ids(seed_generator: UATSeedGenerator) -> Dict[str, str]:
    """Provide deterministic user IDs."""
    return {
        "admin": seed_generator.users[0].id,
        "user": seed_generator.users[1].id,
        "auditor": seed_generator.users[2].id,
        "readonly": seed_generator.users[3].id,
    }


@pytest.fixture(scope="session")
def uat_incident_ids(seed_generator: UATSeedGenerator) -> Dict[str, str]:
    """Provide deterministic incident IDs."""
    return {
        "open": seed_generator.incidents[0].id,
        "in_progress": seed_generator.incidents[1].id,
        "closed": seed_generator.incidents[2].id,
    }


@pytest.fixture(scope="session")
def uat_audit_ids(seed_generator: UATSeedGenerator) -> Dict[str, str]:
    """Provide deterministic audit IDs."""
    return {
        "scheduled": seed_generator.audits[0].id,
        "in_progress": seed_generator.audits[1].id,
        "completed": seed_generator.audits[2].id,
    }


@pytest.fixture(scope="session")
def uat_risk_ids(seed_generator: UATSeedGenerator) -> Dict[str, str]:
    """Provide deterministic risk IDs."""
    return {
        "open_security": seed_generator.risks[0].id,
        "mitigated": seed_generator.risks[1].id,
        "open_compliance": seed_generator.risks[2].id,
    }


@pytest.fixture(scope="session")
def uat_standard_ids(seed_generator: UATSeedGenerator) -> Dict[str, str]:
    """Provide deterministic standard IDs."""
    return {
        "iso27001": seed_generator.standards[0].id,
        "soc2": seed_generator.standards[1].id,
    }


@pytest.fixture(scope="session")
def uat_control_ids(seed_generator: UATSeedGenerator) -> Dict[str, str]:
    """Provide deterministic control IDs."""
    return {
        "iso_policies": seed_generator.controls[0].id,
        "iso_access": seed_generator.controls[1].id,
        "soc2_environment": seed_generator.controls[2].id,
        "soc2_access": seed_generator.controls[3].id,
    }


# =============================================================================
# API CLIENT HELPERS
# =============================================================================


class UATApiClient:
    """
    UAT API client with authentication support.

    Usage:
        client = UATApiClient(base_url)
        await client.login('uat_admin', 'password')
        response = await client.get('/api/v1/incidents')
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token: Optional[str] = None
        self.role: Optional[str] = None

    def _headers(self) -> Dict[str, str]:
        """Get request headers with auth token."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def login(self, username: str, password: str) -> bool:
        """
        Authenticate and store token.

        Returns True on success.
        """
        # Placeholder - in real implementation, use httpx or aiohttp
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         f'{self.base_url}/api/v1/auth/login',
        #         json={'username': username, 'password': password}
        #     )
        #     if response.status_code == 200:
        #         data = response.json()
        #         self.token = data['access_token']
        #         self.role = data.get('role')
        #         return True
        # return False

        # For testing, simulate successful login
        self.token = f"test-token-{username}"
        self.role = "admin" if "admin" in username else "user"
        return True

    async def get(self, path: str) -> Dict[str, Any]:
        """GET request."""
        # Placeholder
        return {"status": "ok", "path": path}

    async def post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST request."""
        # Placeholder
        return {"status": "created", "path": path, "data": data}

    async def put(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """PUT request."""
        # Placeholder
        return {"status": "updated", "path": path, "data": data}

    async def delete(self, path: str) -> Dict[str, Any]:
        """DELETE request."""
        # Placeholder
        return {"status": "deleted", "path": path}


@pytest.fixture
async def admin_client(uat_config: UATConfig) -> Generator[UATApiClient, None, None]:
    """Provide authenticated admin API client."""
    client = UATApiClient(uat_config.base_url)
    await client.login(uat_config.admin_username, uat_config.admin_password)
    yield client


@pytest.fixture
async def user_client(uat_config: UATConfig) -> Generator[UATApiClient, None, None]:
    """Provide authenticated regular user API client."""
    client = UATApiClient(uat_config.base_url)
    await client.login(uat_config.user_username, uat_config.user_password)
    yield client


# =============================================================================
# ASSERTION HELPERS
# =============================================================================


def assert_stable_ordering(items: list, key: str, expected_order: list) -> None:
    """
    Assert items are in stable, deterministic order.

    Args:
        items: List of items to check
        key: Key to extract for ordering check
        expected_order: Expected order of key values
    """
    actual_order = [item[key] for item in items]
    assert (
        actual_order == expected_order
    ), f"Ordering not stable. Expected: {expected_order}, Got: {actual_order}"


def assert_no_pii(data: Dict[str, Any], forbidden_patterns: list = None) -> None:
    """
    Assert no PII is present in response data.

    Default forbidden patterns:
    - Real email domains (not @test.local)
    - SSN patterns
    - Phone number patterns
    """
    forbidden = forbidden_patterns or [
        r"@(?!test\.local)[a-z]+\.[a-z]+",  # Real email domains
        r"\d{3}-\d{2}-\d{4}",  # SSN
        r"\d{3}[-.\s]?\d{3}[-.\s]?\d{4}",  # Phone
    ]

    import re

    data_str = json.dumps(data)

    for pattern in forbidden:
        matches = re.findall(pattern, data_str)
        assert not matches, f"Potential PII found: {matches}"


def assert_uat_reference(reference: str, prefix: str) -> None:
    """Assert reference number has UAT prefix."""
    assert reference.startswith(
        f"{prefix}-UAT-"
    ), f"Reference '{reference}' does not have UAT prefix '{prefix}-UAT-'"
