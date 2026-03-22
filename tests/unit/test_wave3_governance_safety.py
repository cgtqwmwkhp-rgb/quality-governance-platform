from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.api.routes.employee_portal import generate_tracking_code, track_report, validate_tracking_code
from src.api.routes.telemetry import TelemetryEvent
from src.domain.models.incident import IncidentSeverity, IncidentStatus
from src.domain.models.user import Role, User


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _TrackingDb:
    def __init__(self, value):
        self._value = value

    async def execute(self, _query):
        return _ScalarResult(self._value)


def test_tracking_code_is_reference_bound() -> None:
    code = generate_tracking_code("INC-2026-0001")

    assert validate_tracking_code("INC-2026-0001", code) is True
    assert validate_tracking_code("INC-2026-0002", code) is False


@pytest.mark.asyncio
async def test_track_report_rejects_missing_tracking_code() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await track_report(reference_number="INC-2026-0001", db=_TrackingDb(None), tracking_code=None)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_track_report_accepts_valid_tracking_code() -> None:
    incident = SimpleNamespace(
        reference_number="INC-2026-0001",
        title="Portal incident",
        status=IncidentStatus.REPORTED,
        severity=IncidentSeverity.MEDIUM,
        created_at=datetime(2026, 3, 22, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 22, tzinfo=timezone.utc),
    )

    response = await track_report(
        reference_number="INC-2026-0001",
        db=_TrackingDb(incident),
        tracking_code=generate_tracking_code("INC-2026-0001"),
    )

    assert response.reference_number == "INC-2026-0001"
    assert response.status == IncidentStatus.REPORTED.value


def test_telemetry_event_rejects_unbounded_dimension_values() -> None:
    with pytest.raises(ValidationError):
        TelemetryEvent(
            name="exp001_form_opened",
            timestamp="2026-03-22T12:00:00Z",
            sessionId="sess-1",
            dimensions={"stepCount": 999, "environment": "staging"},
        )

    with pytest.raises(ValidationError):
        TelemetryEvent(
            name="exp001_form_opened",
            timestamp="2026-03-22T12:00:00Z",
            sessionId="sess-1",
            dimensions={"error": "free-text", "environment": "staging"},
        )


def test_user_has_permission_normalizes_json_and_csv_payloads() -> None:
    json_role = Role(name="json-role", permissions='["incident:read", "incident:update"]')
    csv_role = Role(name="csv-role", permissions=" complaint:read , complaint:update ")
    user = User(
        email="test@example.com",
        hashed_password="hash",
        first_name="Test",
        last_name="User",
        roles=[json_role, csv_role],
    )

    assert user.has_permission("INCIDENT:READ") is True
    assert user.has_permission("complaint:update") is True
    assert user.has_permission("risk:read") is False
