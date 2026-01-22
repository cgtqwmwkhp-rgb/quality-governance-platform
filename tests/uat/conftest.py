"""
UAT Test Configuration

Shared fixtures and configuration for User Acceptance Tests.
"""

import pytest


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


@pytest.fixture(scope="session")
def uat_config():
    """UAT test configuration."""
    return {
        "base_url": "http://test",
        "timeout": 30,
        "max_retries": 3,
    }
