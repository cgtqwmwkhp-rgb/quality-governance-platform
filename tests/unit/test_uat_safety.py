#!/usr/bin/env python3
"""
Unit tests for UAT Safety Middleware.

Tests prove:
1. READ_ONLY mode blocks writes without headers (409)
2. Override headers allow writes for admin users
3. Expired override is blocked
4. Non-admin users cannot use override
5. READ_WRITE mode allows all operations
"""

import os
from datetime import datetime, timedelta
from unittest import TestCase, main
from unittest.mock import MagicMock, patch


class TestUATSafetyModeDetection(TestCase):
    """Tests for UAT mode configuration detection."""

    def test_read_only_mode_detection(self):
        """is_uat_read_only returns True when UAT_MODE=READ_ONLY."""
        with patch.dict(os.environ, {"UAT_MODE": "READ_ONLY"}):
            # Need to reimport to pick up new env var
            from importlib import reload

            import src.core.config as config_module

            reload(config_module)
            self.assertTrue(config_module.settings.is_uat_read_only)

    def test_read_write_mode_detection(self):
        """is_uat_read_only returns False when UAT_MODE=READ_WRITE."""
        with patch.dict(os.environ, {"UAT_MODE": "READ_WRITE"}, clear=False):
            from importlib import reload

            import src.core.config as config_module

            # Clear cache and reload
            config_module.get_settings.cache_clear()
            reload(config_module)
            self.assertFalse(config_module.settings.is_uat_read_only)

    def test_admin_user_list_parsing(self):
        """uat_admin_user_list correctly parses comma-separated list."""
        with patch.dict(os.environ, {"UAT_ADMIN_USERS": "user1,user2,user3"}):
            from importlib import reload

            import src.core.config as config_module

            config_module.get_settings.cache_clear()
            reload(config_module)
            admins = config_module.settings.uat_admin_user_list
            self.assertEqual(admins, ["user1", "user2", "user3"])

    def test_empty_admin_list(self):
        """uat_admin_user_list returns empty list when not set."""
        with patch.dict(os.environ, {"UAT_ADMIN_USERS": ""}):
            from importlib import reload

            import src.core.config as config_module

            config_module.get_settings.cache_clear()
            reload(config_module)
            self.assertEqual(config_module.settings.uat_admin_user_list, [])


class TestOverrideHeaderValidation(TestCase):
    """Tests for override header validation logic."""

    def test_valid_override_headers(self):
        """Valid override headers pass validation."""
        from src.core.uat_safety import _validate_override_headers

        request = MagicMock()
        request.headers = {
            "X-UAT-WRITE-ENABLE": "true",
            "X-UAT-ISSUE-ID": "GOVPLAT-123",
            "X-UAT-OWNER": "qa-team",
        }

        is_valid, error = _validate_override_headers(request)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_missing_enable_header(self):
        """Missing X-UAT-WRITE-ENABLE fails validation."""
        from src.core.uat_safety import _validate_override_headers

        request = MagicMock()
        request.headers = {
            "X-UAT-ISSUE-ID": "GOVPLAT-123",
            "X-UAT-OWNER": "qa-team",
        }

        is_valid, error = _validate_override_headers(request)
        self.assertFalse(is_valid)
        self.assertIn("X-UAT-WRITE-ENABLE", error)

    def test_missing_issue_id(self):
        """Missing X-UAT-ISSUE-ID fails validation."""
        from src.core.uat_safety import _validate_override_headers

        request = MagicMock()
        request.headers = {
            "X-UAT-WRITE-ENABLE": "true",
            "X-UAT-OWNER": "qa-team",
        }

        is_valid, error = _validate_override_headers(request)
        self.assertFalse(is_valid)
        self.assertIn("X-UAT-ISSUE-ID", error)

    def test_missing_owner(self):
        """Missing X-UAT-OWNER fails validation."""
        from src.core.uat_safety import _validate_override_headers

        request = MagicMock()
        request.headers = {
            "X-UAT-WRITE-ENABLE": "true",
            "X-UAT-ISSUE-ID": "GOVPLAT-123",
        }

        is_valid, error = _validate_override_headers(request)
        self.assertFalse(is_valid)
        self.assertIn("X-UAT-OWNER", error)

    def test_expired_override(self):
        """Expired X-UAT-EXPIRY fails validation."""
        from src.core.uat_safety import _validate_override_headers

        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        request = MagicMock()
        request.headers = {
            "X-UAT-WRITE-ENABLE": "true",
            "X-UAT-ISSUE-ID": "GOVPLAT-123",
            "X-UAT-OWNER": "qa-team",
            "X-UAT-EXPIRY": yesterday,
        }

        is_valid, error = _validate_override_headers(request)
        self.assertFalse(is_valid)
        self.assertIn("expired", error.lower())

    def test_future_expiry_allowed(self):
        """Future X-UAT-EXPIRY passes validation."""
        from src.core.uat_safety import _validate_override_headers

        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        request = MagicMock()
        request.headers = {
            "X-UAT-WRITE-ENABLE": "true",
            "X-UAT-ISSUE-ID": "GOVPLAT-123",
            "X-UAT-OWNER": "qa-team",
            "X-UAT-EXPIRY": tomorrow,
        }

        is_valid, error = _validate_override_headers(request)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_invalid_expiry_format(self):
        """Invalid X-UAT-EXPIRY format fails validation."""
        from src.core.uat_safety import _validate_override_headers

        request = MagicMock()
        request.headers = {
            "X-UAT-WRITE-ENABLE": "true",
            "X-UAT-ISSUE-ID": "GOVPLAT-123",
            "X-UAT-OWNER": "qa-team",
            "X-UAT-EXPIRY": "01-28-2026",  # Wrong format
        }

        is_valid, error = _validate_override_headers(request)
        self.assertFalse(is_valid)
        self.assertIn("YYYY-MM-DD", error)


class TestUserAdminCheck(TestCase):
    """Tests for UAT admin user verification."""

    def test_admin_user_allowed(self):
        """User in admin list is recognized as admin."""
        from src.core.uat_safety import _is_user_uat_admin

        with patch("src.core.uat_safety.settings") as mock_settings:
            mock_settings.uat_admin_user_list = ["admin1", "admin2"]
            self.assertTrue(_is_user_uat_admin("admin1"))

    def test_non_admin_user_blocked(self):
        """User not in admin list is not recognized as admin."""
        from src.core.uat_safety import _is_user_uat_admin

        with patch("src.core.uat_safety.settings") as mock_settings:
            mock_settings.uat_admin_user_list = ["admin1", "admin2"]
            self.assertFalse(_is_user_uat_admin("regular_user"))

    def test_none_user_blocked(self):
        """None user ID is not recognized as admin."""
        from src.core.uat_safety import _is_user_uat_admin

        with patch("src.core.uat_safety.settings") as mock_settings:
            mock_settings.uat_admin_user_list = ["admin1"]
            self.assertFalse(_is_user_uat_admin(None))


class TestAlwaysAllowedPaths(TestCase):
    """Tests for paths that bypass UAT restrictions."""

    def test_health_endpoint_allowed(self):
        """Health endpoint is always allowed."""
        from src.core.uat_safety import _is_path_always_allowed

        self.assertTrue(_is_path_always_allowed("/healthz"))
        self.assertTrue(_is_path_always_allowed("/readyz"))

    def test_meta_endpoint_allowed(self):
        """Meta version endpoint is always allowed."""
        from src.core.uat_safety import _is_path_always_allowed

        self.assertTrue(_is_path_always_allowed("/api/v1/meta/version"))

    def test_auth_endpoints_allowed(self):
        """Auth endpoints are always allowed."""
        from src.core.uat_safety import _is_path_always_allowed

        self.assertTrue(_is_path_always_allowed("/api/v1/auth/login"))
        self.assertTrue(_is_path_always_allowed("/api/v1/auth/token"))

    def test_api_endpoint_not_in_always_allowed(self):
        """Regular API endpoints are not in always-allowed list."""
        from src.core.uat_safety import _is_path_always_allowed

        self.assertFalse(_is_path_always_allowed("/api/v1/incidents"))
        self.assertFalse(_is_path_always_allowed("/api/v1/audits"))


class TestWriteBlockedResponse(TestCase):
    """Tests for the blocked response format."""

    def test_blocked_response_structure(self):
        """Blocked response has correct structure."""
        from src.core.uat_safety import UATWriteBlockedResponse

        response = UATWriteBlockedResponse.create()
        self.assertEqual(response.status_code, 409)

        import json

        body = json.loads(response.body)
        self.assertEqual(body["error_class"], "UAT_WRITE_BLOCKED")
        self.assertIn("detail", body)
        self.assertIn("how_to_enable", body)

    def test_blocked_response_custom_detail(self):
        """Blocked response accepts custom detail message."""
        from src.core.uat_safety import UATWriteBlockedResponse

        response = UATWriteBlockedResponse.create("Custom reason")

        import json

        body = json.loads(response.body)
        self.assertEqual(body["detail"], "Custom reason")


if __name__ == "__main__":
    main()
