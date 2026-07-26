"""Contract tests for the portal report-tracking read path.

PX-315: the tracking gate used to answer every failure with 404, so a client
that sent no credential looked identical to an unknown reference. These tests
pin one status code per failure mode, and pin the success case the shipped
frontend actually exercises.

PX-316: the same endpoint spans four models with different status casing, so
the canonical lowercase wire form is pinned here too.

The endpoint is mounted on a bare app with stubbed persistence: the behaviour
under test is the authorisation gate and the response mapping, neither of which
needs a database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import get_optional_current_user
from src.api.middleware.error_handler import register_exception_handlers
from src.api.routes.employee_portal import generate_tracking_code, router
from src.domain.models.incident import IncidentSeverity, IncidentStatus
from src.infrastructure.database import get_db

INCIDENT_REF = "INC-2026-ABCD1234"
NEAR_MISS_REF = "NM-2026-ABCD1234"
OWNER_EMAIL = "engineer@example.com"
TENANT_ID = 3


class _Result:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _StubSession:
    """Returns the same record for any query; the route only ever runs one."""

    def __init__(self, record: Any) -> None:
        self._record = record

    async def execute(self, _query: Any) -> _Result:
        return _Result(self._record)


def _incident(**overrides: Any) -> SimpleNamespace:
    now = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    fields: dict[str, Any] = {
        "reference_number": INCIDENT_REF,
        "title": "Slip hazard in the yard",
        "status": IncidentStatus.UNDER_INVESTIGATION,
        "severity": IncidentSeverity.HIGH,
        "created_at": now,
        "updated_at": now,
        "reporter_email": OWNER_EMAIL,
        "tenant_id": TENANT_ID,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _near_miss(**overrides: Any) -> SimpleNamespace:
    now = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    fields: dict[str, Any] = {
        "reference_number": NEAR_MISS_REF,
        "contract": "Northern Depot",
        # NearMiss persists a plain uppercase string, unlike the three enums.
        "status": "UNDER_REVIEW",
        "priority": "HIGH",
        "created_at": now,
        "updated_at": now,
        "reporter_email": OWNER_EMAIL,
        "tenant_id": TENANT_ID,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _client(record: Any = None, user: Optional[Any] = None) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1/portal")
    app.dependency_overrides[get_db] = lambda: _StubSession(record)
    app.dependency_overrides[get_optional_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def _track(client: TestClient, reference: str, **params: str):
    return client.get(f"/api/v1/portal/reports/{reference}/", params=params)


def _comparable(response: Any) -> dict[str, Any]:
    """The error body minus the per-request correlation id, which always differs."""
    body = response.json()
    body["error"].pop("request_id", None)
    return body


# ---------------------------------------------------------------------------
# PX-315 — one status code per failure mode
# ---------------------------------------------------------------------------


def test_track_succeeds_when_the_caller_sends_a_valid_tracking_code() -> None:
    """The journey the frontend was failing to perform: reference + its code."""
    client = _client(record=_incident())

    response = _track(client, INCIDENT_REF, tracking_code=generate_tracking_code(INCIDENT_REF))

    assert response.status_code == 200
    body = response.json()
    assert body["reference_number"] == INCIDENT_REF
    assert body["title"] == "Slip hazard in the yard"


def test_track_without_any_credential_is_401_not_404() -> None:
    """The PX-315 regression guard: a missing code is not 'no such report'."""
    client = _client(record=_incident())

    response = _track(client, INCIDENT_REF)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_track_with_a_wrong_tracking_code_is_403() -> None:
    client = _client(record=_incident())

    response = _track(client, INCIDENT_REF, tracking_code="not-the-right-code")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_track_with_an_unrecognised_reference_format_is_400() -> None:
    client = _client(record=_incident())

    response = _track(client, "NOT-A-REFERENCE", tracking_code="anything")

    assert response.status_code == 400


def test_track_of_a_genuinely_unknown_reference_is_404() -> None:
    """A correct code for a reference with no row behind it is real 'not found'."""
    client = _client(record=None)

    response = _track(client, INCIDENT_REF, tracking_code=generate_tracking_code(INCIDENT_REF))

    assert response.status_code == 404


def test_signed_in_submitter_can_track_without_a_tracking_code() -> None:
    client = _client(
        record=_incident(),
        user=SimpleNamespace(email=OWNER_EMAIL, tenant_id=TENANT_ID),
    )

    response = _track(client, INCIDENT_REF)

    assert response.status_code == 200


def test_signed_in_user_cannot_read_somebody_elses_report() -> None:
    """Session access is scoped to the submitter, and a miss must not leak existence."""
    client = _client(
        record=_incident(),
        user=SimpleNamespace(email="someone.else@example.com", tenant_id=TENANT_ID),
    )

    response = _track(client, INCIDENT_REF)

    assert response.status_code == 404


def test_signed_in_user_from_another_tenant_cannot_read_the_report() -> None:
    client = _client(
        record=_incident(),
        user=SimpleNamespace(email=OWNER_EMAIL, tenant_id=TENANT_ID + 1),
    )

    response = _track(client, INCIDENT_REF)

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("label", "user", "params"),
    [
        ("no credential", None, {}),
        ("wrong tracking code", None, {"tracking_code": "not-the-right-code"}),
        (
            "signed in, not the submitter",
            SimpleNamespace(email="someone.else@example.com", tenant_id=TENANT_ID),
            {},
        ),
    ],
)
def test_a_refused_read_never_reveals_whether_the_reference_exists(
    label: str,
    user: Optional[Any],
    params: dict[str, str],
) -> None:
    """A caller who may not read a report must not learn whether one is there.

    Every refusal is compared against the same refusal for a reference with no
    row behind it. Status code *and* body must match, because a 404 chosen to
    hide existence hides nothing if the wording differs — which is exactly how
    the ownership mismatch leaked before.
    """
    present = _track(_client(record=_incident(), user=user), INCIDENT_REF, **params)
    absent = _track(_client(record=None, user=user), INCIDENT_REF, **params)

    assert present.status_code == absent.status_code, label
    assert _comparable(present) == _comparable(absent), label


def test_anonymous_submission_stays_code_only_for_signed_in_users() -> None:
    """An anonymous report has no owner email, so a session must not unlock it."""
    client = _client(
        record=_incident(reporter_email=None),
        user=SimpleNamespace(email=OWNER_EMAIL, tenant_id=TENANT_ID),
    )

    assert _track(client, INCIDENT_REF).status_code == 404
    assert _track(client, INCIDENT_REF, tracking_code=generate_tracking_code(INCIDENT_REF)).status_code == 200


# ---------------------------------------------------------------------------
# PX-316 — one status casing on the wire
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("record", "reference", "expected_status", "expected_label"),
    [
        (_incident(), INCIDENT_REF, "under_investigation", "🔍 Under Investigation"),
        (_near_miss(), NEAR_MISS_REF, "under_review", "under_review"),
    ],
)
def test_status_is_lowercase_regardless_of_how_the_model_stores_it(
    record: Any,
    reference: str,
    expected_status: str,
    expected_label: str,
) -> None:
    client = _client(record=record)

    response = _track(client, reference, tracking_code=generate_tracking_code(reference))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == expected_status
    assert body["status_label"] == expected_label
