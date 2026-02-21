"""Unit tests for setup_required request_id traceability.

These tests ensure that SETUP_REQUIRED responses always include a non-null
request_id for tracing and debugging purposes.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.api.schemas.setup_required import (
    SetupRequiredResponse,
    setup_required_response,
)


class TestSetupRequiredRequestId:
    """Tests for request_id handling in SETUP_REQUIRED responses."""

    def test_setup_required_response_with_request_id(self):
        """Verify setup_required_response includes request_id when provided."""
        request_id = "abc123-def456"
        response = setup_required_response(
            module="test-module",
            message="Test message",
            next_action="Test action",
            request_id=request_id,
        )

        assert response["request_id"] == request_id
        assert response["request_id"] is not None

    def test_setup_required_response_without_request_id_is_null(self):
        """Verify setup_required_response request_id is None when not provided.

        Note: This test documents current behavior that should be fixed.
        All production uses should pass request_id.
        """
        response = setup_required_response(
            module="test-module",
            message="Test message",
            next_action="Test action",
        )

        # Current behavior: None when not provided
        # Production code should always provide request_id
        assert response["request_id"] is None

    def test_setup_required_response_schema_validates_request_id(self):
        """Verify SetupRequiredResponse model accepts request_id."""
        response = SetupRequiredResponse(
            module="test-module",
            message="Test message",
            next_action="Test action",
            request_id="xyz789",
        )

        assert response.request_id == "xyz789"
        assert response.error_class == "SETUP_REQUIRED"
        assert response.setup_required is True

    def test_setup_required_response_has_all_required_fields(self):
        """Verify setup_required_response includes all schema fields."""
        response = setup_required_response(
            module="planet-mark",
            message="Module not configured",
            next_action="Run migrations",
            request_id="test-request-id",
        )

        required_fields = [
            "error_class",
            "setup_required",
            "module",
            "message",
            "next_action",
            "request_id",
        ]

        for field in required_fields:
            assert field in response, f"Missing required field: {field}"

    def test_request_id_format_uuid_hex(self):
        """Verify request_id accepts UUID hex format."""
        # UUID hex format: 32 chars without hyphens
        uuid_hex = "abc123def456789012345678abcdef01"
        response = setup_required_response(
            module="test",
            message="Test",
            next_action="Test",
            request_id=uuid_hex,
        )

        assert response["request_id"] == uuid_hex
        assert len(response["request_id"]) == 32


class TestSetupRequiredIntegration:
    """Integration-style tests for request_id in API context."""

    def test_get_request_id_returns_string(self):
        """Verify get_request_id dependency returns a string."""
        from src.api.dependencies.request_context import get_request_id

        # Mock request with request_id in state
        mock_request = MagicMock()
        mock_request.state.request_id = "test-id-123"

        result = get_request_id(mock_request)

        assert result == "test-id-123"
        assert isinstance(result, str)

    def test_get_request_id_fallback_when_missing(self):
        """Verify get_request_id returns 'unknown' when state is missing."""
        from src.api.dependencies.request_context import get_request_id

        # Mock request without request_id
        mock_request = MagicMock(spec=[])
        mock_request.state = MagicMock(spec=[])  # No request_id attribute

        result = get_request_id(mock_request)

        assert result == "unknown"
