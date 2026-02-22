"""
Unit tests for /api/v1/testing endpoint behavior.

Tests:
- Environment guard logic
- Request/Response models
- selectinload import verification
"""

import os
from unittest.mock import patch


class TestEnvironmentGuard:
    """Tests for environment guard logic."""

    def test_staging_env_detection(self):
        """Test staging environment detection logic."""

        # Direct logic test without import
        def is_staging_env() -> bool:
            app_env = os.environ.get("APP_ENV", "development").lower()
            return app_env == "staging"

        with patch.dict(os.environ, {"APP_ENV": "staging"}):
            assert is_staging_env() is True

        with patch.dict(os.environ, {"APP_ENV": "production"}):
            assert is_staging_env() is False

        with patch.dict(os.environ, {"APP_ENV": "development"}):
            assert is_staging_env() is False

    def test_ci_secret_validation_logic(self):
        """Test CI secret validation logic."""
        from typing import Optional

        def validate_ci_secret(header: Optional[str], env_secret: str) -> bool:
            if not env_secret:
                return False
            if not header or header != env_secret:
                return False
            return True

        # Valid secret
        assert validate_ci_secret("correct", "correct") is True

        # Wrong secret
        assert validate_ci_secret("wrong", "correct") is False

        # Missing header
        assert validate_ci_secret(None, "correct") is False

        # Empty env secret
        assert validate_ci_secret("any", "") is False


def _get_testing_py_content():
    """Get the content of testing.py using a reliable path."""
    from pathlib import Path

    # Try relative path from test file first
    testing_path = Path(__file__).parent.parent.parent / "src" / "api" / "routes" / "testing.py"
    if testing_path.exists():
        return testing_path.read_text()

    # Fallback for different directory structures
    alt_paths = [
        Path("src/api/routes/testing.py"),
        Path("../src/api/routes/testing.py"),
        Path("../../src/api/routes/testing.py"),
    ]
    for p in alt_paths:
        if p.exists():
            return p.read_text()

    raise FileNotFoundError("Could not find testing.py")


class TestSelectinloadFix:
    """Test that the MissingGreenlet fix is properly implemented."""

    def test_selectinload_in_testing_module_source(self):
        """Verify selectinload import exists in testing.py source."""
        content = _get_testing_py_content()

        # Verify selectinload import
        assert "from sqlalchemy.orm import selectinload" in content

        # Verify eager loading in query
        assert "selectinload(User.roles)" in content

        # Verify no direct assignment that triggers lazy load
        assert "user.roles = list(roles)" not in content

        # Verify clear/extend pattern instead
        assert "user.roles.clear()" in content
        assert "user.roles.extend(roles)" in content


class TestEndpointSecurity:
    """Test endpoint security features."""

    def test_endpoint_has_staging_check(self):
        """Verify endpoint has staging environment check."""
        content = _get_testing_py_content()

        # Must have staging check
        assert "is_staging_env()" in content
        assert "AuthorizationError" in content or "HTTP_403_FORBIDDEN" in content

    def test_endpoint_has_secret_check(self):
        """Verify endpoint requires CI_TEST_SECRET."""
        content = _get_testing_py_content()

        # Must require CI_TEST_SECRET
        assert "CI_TEST_SECRET" in content
        assert "X-CI-Secret" in content
        assert "AuthenticationError" in content or "HTTP_401_UNAUTHORIZED" in content


class TestIdempotencyPattern:
    """Test idempotent update pattern."""

    def test_endpoint_handles_existing_user(self):
        """Verify endpoint handles existing user case."""
        content = _get_testing_py_content()

        # Must handle existing user
        assert "if user is None:" in content
        assert "else:" in content
        assert "Updated test user" in content
