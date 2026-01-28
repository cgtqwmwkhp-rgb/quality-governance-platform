"""
Integration tests for UAT Safety Middleware.

Tests the middleware behavior using mocking to avoid settings cache issues.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.responses import JSONResponse

from src.core.uat_safety import (
    UATSafetyMiddleware,
    UATWriteBlockedResponse,
    _is_path_always_allowed,
    _is_user_uat_admin,
    _validate_override_headers,
)


class TestUATSafetyMiddlewareLogic:
    """Tests for UAT safety middleware core logic (no app startup needed)."""

    def test_write_blocked_response_structure(self):
        """Blocked response has correct structure."""
        response = UATWriteBlockedResponse.create()
        assert response.status_code == 409

        import json

        body = json.loads(response.body)
        assert body["error_class"] == "UAT_WRITE_BLOCKED"
        assert "detail" in body
        assert "how_to_enable" in body

    def test_always_allowed_paths(self):
        """Certain paths are always allowed."""
        assert _is_path_always_allowed("/healthz") is True
        assert _is_path_always_allowed("/readyz") is True
        assert _is_path_always_allowed("/api/v1/meta/version") is True
        assert _is_path_always_allowed("/api/v1/auth/login") is True
        assert _is_path_always_allowed("/docs") is True

    def test_api_paths_not_always_allowed(self):
        """Regular API paths are not in always-allowed list."""
        assert _is_path_always_allowed("/api/v1/incidents") is False
        assert _is_path_always_allowed("/api/v1/audits") is False
        assert _is_path_always_allowed("/api/v1/risks") is False

    def test_valid_override_headers(self):
        """Valid override headers pass validation."""
        request = MagicMock()
        request.headers = {
            "X-UAT-WRITE-ENABLE": "true",
            "X-UAT-ISSUE-ID": "GOVPLAT-123",
            "X-UAT-OWNER": "qa-team",
        }
        is_valid, error = _validate_override_headers(request)
        assert is_valid is True
        assert error is None

    def test_missing_enable_header(self):
        """Missing X-UAT-WRITE-ENABLE fails validation."""
        request = MagicMock()
        request.headers = {
            "X-UAT-ISSUE-ID": "GOVPLAT-123",
            "X-UAT-OWNER": "qa-team",
        }
        is_valid, error = _validate_override_headers(request)
        assert is_valid is False
        assert "X-UAT-WRITE-ENABLE" in error

    def test_missing_issue_id(self):
        """Missing X-UAT-ISSUE-ID fails validation."""
        request = MagicMock()
        request.headers = {
            "X-UAT-WRITE-ENABLE": "true",
            "X-UAT-OWNER": "qa-team",
        }
        is_valid, error = _validate_override_headers(request)
        assert is_valid is False
        assert "X-UAT-ISSUE-ID" in error

    def test_expired_override_blocked(self):
        """Expired X-UAT-EXPIRY fails validation."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        request = MagicMock()
        request.headers = {
            "X-UAT-WRITE-ENABLE": "true",
            "X-UAT-ISSUE-ID": "GOVPLAT-123",
            "X-UAT-OWNER": "qa-team",
            "X-UAT-EXPIRY": yesterday,
        }
        is_valid, error = _validate_override_headers(request)
        assert is_valid is False
        assert "expired" in error.lower()

    def test_future_expiry_allowed(self):
        """Future X-UAT-EXPIRY passes validation."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        request = MagicMock()
        request.headers = {
            "X-UAT-WRITE-ENABLE": "true",
            "X-UAT-ISSUE-ID": "GOVPLAT-123",
            "X-UAT-OWNER": "qa-team",
            "X-UAT-EXPIRY": tomorrow,
        }
        is_valid, error = _validate_override_headers(request)
        assert is_valid is True
        assert error is None

    def test_admin_user_check(self):
        """Admin user check works correctly."""
        with patch("src.core.uat_safety.settings") as mock_settings:
            mock_settings.uat_admin_user_list = ["admin1", "admin2"]
            assert _is_user_uat_admin("admin1") is True
            assert _is_user_uat_admin("admin2") is True
            assert _is_user_uat_admin("regular_user") is False
            assert _is_user_uat_admin(None) is False
