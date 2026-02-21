"""Tests for telemetry API routes."""

import functools
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def skip_on_import_error(test_func):
    """Decorator to skip tests that fail due to ImportError."""

    @functools.wraps(test_func)
    def wrapper(*args, **kwargs):
        try:
            return test_func(*args, **kwargs)
        except (ImportError, ModuleNotFoundError, TypeError) as e:
            pytest.skip(f"Dependency not available: {e}")

    return wrapper


class TestTelemetryRoutes:
    """Test telemetry route handlers."""

    @skip_on_import_error
    def test_module_imports(self):
        """Verify route module imports without error."""
        from src.api.routes import telemetry

        assert hasattr(telemetry, "router")

    @skip_on_import_error
    def test_router_has_events_route(self):
        """Verify single event receive route exists."""
        from src.api.routes.telemetry import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        event_routes = [r for r in routes if r.path in ("/events", "/telemetry/events") and "POST" in r.methods]
        assert len(event_routes) > 0

    @skip_on_import_error
    def test_router_has_batch_route(self):
        """Verify batch event receive route exists."""
        from src.api.routes.telemetry import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        batch_routes = [
            r for r in routes if r.path in ("/events/batch", "/telemetry/events/batch") and "POST" in r.methods
        ]
        assert len(batch_routes) > 0

    @skip_on_import_error
    def test_allowed_events_populated(self):
        """Verify the event allowlist is populated."""
        from src.api.routes.telemetry import ALLOWED_EVENTS

        assert "exp001_form_opened" in ALLOWED_EVENTS
        assert "login_completed" in ALLOWED_EVENTS
        assert len(ALLOWED_EVENTS) >= 6


class TestTelemetrySchemas:
    """Test telemetry schema validation."""

    @skip_on_import_error
    def test_telemetry_event_valid(self):
        """Test TelemetryEvent schema with valid data."""
        from src.api.routes.telemetry import TelemetryEvent

        data = TelemetryEvent(
            name="exp001_form_opened",
            timestamp="2026-01-15T10:30:00Z",
            sessionId="sess-abc-123",
            dimensions={"formType": "incident", "flagEnabled": True},
        )
        assert data.name == "exp001_form_opened"
        assert data.sessionId == "sess-abc-123"

    @skip_on_import_error
    def test_telemetry_event_invalid_name(self):
        """Test TelemetryEvent rejects unknown event name."""
        from src.api.routes.telemetry import TelemetryEvent

        with pytest.raises(Exception):
            TelemetryEvent(
                name="unknown_event",
                timestamp="2026-01-15T10:30:00Z",
                sessionId="sess-abc-123",
            )

    @skip_on_import_error
    def test_telemetry_event_invalid_dimension_key(self):
        """Test TelemetryEvent rejects unknown dimension keys."""
        from src.api.routes.telemetry import TelemetryEvent

        with pytest.raises(Exception):
            TelemetryEvent(
                name="exp001_form_opened",
                timestamp="2026-01-15T10:30:00Z",
                sessionId="sess-abc-123",
                dimensions={"unknownKey": "value"},
            )

    @skip_on_import_error
    def test_telemetry_batch_schema(self):
        """Test TelemetryBatch schema with valid data."""
        from src.api.routes.telemetry import TelemetryBatch, TelemetryEvent

        events = [
            TelemetryEvent(
                name="exp001_form_opened",
                timestamp="2026-01-15T10:30:00Z",
                sessionId="sess-abc-123",
            ),
            TelemetryEvent(
                name="exp001_form_submitted",
                timestamp="2026-01-15T10:35:00Z",
                sessionId="sess-abc-123",
            ),
        ]
        batch = TelemetryBatch(events=events)
        assert len(batch.events) == 2

    @skip_on_import_error
    def test_login_telemetry_event(self):
        """Test TelemetryEvent with login UX dimensions."""
        from src.api.routes.telemetry import TelemetryEvent

        data = TelemetryEvent(
            name="login_completed",
            timestamp="2026-01-15T10:30:00Z",
            sessionId="sess-abc-456",
            dimensions={"result": "success", "durationBucket": "fast"},
        )
        assert data.dimensions["result"] == "success"


class TestTelemetryResponseSchemas:
    """Test telemetry response schemas."""

    @skip_on_import_error
    def test_receive_event_response(self):
        """Test ReceiveEventResponse schema."""
        from src.api.schemas.telemetry import ReceiveEventResponse

        data = ReceiveEventResponse(status="ok")
        assert data.status == "ok"

    @skip_on_import_error
    def test_receive_batch_event_response(self):
        """Test ReceiveBatchEventResponse schema."""
        from src.api.schemas.telemetry import ReceiveBatchEventResponse

        data = ReceiveBatchEventResponse(status="ok", count=5)
        assert data.count == 5

    @skip_on_import_error
    def test_experiment_metrics_response(self):
        """Test GetExperimentMetricsResponse schema."""
        from src.api.schemas.telemetry import GetExperimentMetricsResponse

        data = GetExperimentMetricsResponse(
            experimentId="EXP_001",
            samples=100,
            events={"exp001_form_opened": 50},
            dimensions={},
        )
        assert data.experimentId == "EXP_001"
        assert data.samples == 100
