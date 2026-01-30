"""
Unit tests for telemetry login event validation.

Ensures LOGIN_UX_CONTRACT.md events are properly accepted by the backend.
Tests for Phase 3 of Planet Mark operational task (telemetry 422 fix).
"""

import pytest

from src.api.routes.telemetry import (
    ALLOWED_ACTIONS,
    ALLOWED_DURATION_BUCKETS,
    ALLOWED_ERROR_CODES,
    ALLOWED_EVENTS,
    ALLOWED_LOGIN_RESULTS,
    TelemetryEvent,
)


class TestLoginEventsAllowlist:
    """Test that login events are in the allowlist."""

    def test_login_completed_in_allowlist(self):
        """login_completed event should be allowed."""
        assert "login_completed" in ALLOWED_EVENTS

    def test_login_error_shown_in_allowlist(self):
        """login_error_shown event should be allowed."""
        assert "login_error_shown" in ALLOWED_EVENTS

    def test_login_recovery_action_in_allowlist(self):
        """login_recovery_action event should be allowed."""
        assert "login_recovery_action" in ALLOWED_EVENTS

    def test_login_slow_warning_in_allowlist(self):
        """login_slow_warning event should be allowed."""
        assert "login_slow_warning" in ALLOWED_EVENTS


class TestLoginDimensionValues:
    """Test that login dimension values are properly constrained."""

    def test_login_result_values(self):
        """Login result values should be bounded."""
        assert ALLOWED_LOGIN_RESULTS == {"success", "error"}

    def test_duration_bucket_values(self):
        """Duration bucket values should match frontend enum."""
        expected = {"fast", "normal", "slow", "very_slow", "timeout"}
        assert ALLOWED_DURATION_BUCKETS == expected

    def test_error_code_values(self):
        """Error codes should match frontend enum."""
        expected = {
            "TIMEOUT",
            "UNAUTHORIZED",
            "UNAVAILABLE",
            "SERVER_ERROR",
            "NETWORK_ERROR",
            "UNKNOWN",
        }
        assert ALLOWED_ERROR_CODES == expected

    def test_action_values(self):
        """Recovery actions should match frontend enum."""
        assert ALLOWED_ACTIONS == {"retry", "clear_session"}


class TestLoginEventValidation:
    """Test that login events pass Pydantic validation."""

    def test_login_completed_success(self):
        """login_completed with success result should validate."""
        event = TelemetryEvent(
            name="login_completed",
            timestamp="2026-01-30T12:00:00Z",
            sessionId="sess_123_abc",
            dimensions={
                "result": "success",
                "durationBucket": "fast",
                "environment": "production",
            },
        )
        assert event.name == "login_completed"
        assert event.dimensions["result"] == "success"

    def test_login_completed_error(self):
        """login_completed with error result should validate."""
        event = TelemetryEvent(
            name="login_completed",
            timestamp="2026-01-30T12:00:00Z",
            sessionId="sess_123_abc",
            dimensions={
                "result": "error",
                "durationBucket": "timeout",
                "errorCode": "UNAUTHORIZED",
                "environment": "production",
            },
        )
        assert event.dimensions["errorCode"] == "UNAUTHORIZED"

    def test_login_recovery_action(self):
        """login_recovery_action should validate."""
        event = TelemetryEvent(
            name="login_recovery_action",
            timestamp="2026-01-30T12:00:00Z",
            sessionId="sess_123_abc",
            dimensions={
                "action": "retry",
                "environment": "staging",
            },
        )
        assert event.dimensions["action"] == "retry"

    def test_login_slow_warning(self):
        """login_slow_warning with empty dimensions should validate."""
        event = TelemetryEvent(
            name="login_slow_warning",
            timestamp="2026-01-30T12:00:00Z",
            sessionId="sess_123_abc",
            dimensions={
                "environment": "development",
            },
        )
        assert event.name == "login_slow_warning"

    def test_invalid_result_rejected(self):
        """Invalid result value should be rejected."""
        with pytest.raises(ValueError, match="result .* not in allowlist"):
            TelemetryEvent(
                name="login_completed",
                timestamp="2026-01-30T12:00:00Z",
                sessionId="sess_123_abc",
                dimensions={
                    "result": "invalid",
                    "durationBucket": "fast",
                },
            )

    def test_invalid_error_code_rejected(self):
        """Invalid error code should be rejected."""
        with pytest.raises(ValueError, match="errorCode .* not in allowlist"):
            TelemetryEvent(
                name="login_completed",
                timestamp="2026-01-30T12:00:00Z",
                sessionId="sess_123_abc",
                dimensions={
                    "result": "error",
                    "durationBucket": "timeout",
                    "errorCode": "INVALID_CODE",
                },
            )

    def test_invalid_action_rejected(self):
        """Invalid action should be rejected."""
        with pytest.raises(ValueError, match="action .* not in allowlist"):
            TelemetryEvent(
                name="login_recovery_action",
                timestamp="2026-01-30T12:00:00Z",
                sessionId="sess_123_abc",
                dimensions={
                    "action": "invalid_action",
                },
            )


class TestBackwardCompatibility:
    """Test that existing EXP-001 events still work."""

    def test_exp001_form_opened(self):
        """EXP-001 form_opened should still validate."""
        event = TelemetryEvent(
            name="exp001_form_opened",
            timestamp="2026-01-30T12:00:00Z",
            sessionId="sess_123_abc",
            dimensions={
                "formType": "incident",
                "flagEnabled": True,
                "hasDraft": False,
                "environment": "production",
            },
        )
        assert event.name == "exp001_form_opened"

    def test_exp001_form_submitted(self):
        """EXP-001 form_submitted should still validate."""
        event = TelemetryEvent(
            name="exp001_form_submitted",
            timestamp="2026-01-30T12:00:00Z",
            sessionId="sess_123_abc",
            dimensions={
                "formType": "near-miss",
                "flagEnabled": True,
                "hadDraft": True,
                "stepCount": 5,
                "error": False,
                "environment": "staging",
            },
        )
        assert event.dimensions["formType"] == "near-miss"
