"""Unit tests for incident ↔ enterprise risk bidirectional link helpers."""

from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import BadRequestError
from src.domain.models.incident import IncidentSeverity
from src.domain.services.incident_risk_links import (
    append_linked_risk_id,
    create_enterprise_risk_from_incident,
    default_impact_for_incident,
    find_existing_enterprise_risk_for_incident,
    incident_risk_source,
    map_treatment_strategy,
    parse_incident_id_from_risk_context,
    parse_linked_risk_ids,
    resolve_enterprise_category,
    resolve_fk_safe_owner_id,
    risk_register_href,
    severity_allows_raise_risk,
)


class _IncidentStub:
    def __init__(self, *, severity="high", incident_type="injury"):
        self.severity = severity
        self.incident_type = incident_type


def test_parse_and_append_linked_risk_ids() -> None:
    assert parse_linked_risk_ids(None) == []
    assert parse_linked_risk_ids("1, 2,2,x,3") == [1, 2, 3]
    assert append_linked_risk_id("1,2", 2) == "1,2"
    assert append_linked_risk_id("1,2", 9) == "1,2,9"
    assert append_linked_risk_id(None, 4) == "4"


def test_incident_risk_source_round_trip() -> None:
    source = incident_risk_source(42, "INC-42")
    assert source == "incident:42|INC-42"
    assert parse_incident_id_from_risk_context(source) == 42
    assert parse_incident_id_from_risk_context("incident:7") == 7
    assert parse_incident_id_from_risk_context("unrelated") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("mitigate", "treat"),
        ("accept", "tolerate"),
        ("transfer", "transfer"),
        ("avoid", "terminate"),
        ("exploit", "treat"),
        ("treat", "treat"),
        ("tolerate", "tolerate"),
        ("terminate", "terminate"),
        (None, "treat"),
        ("unknown", "treat"),
    ],
)
def test_map_treatment_strategy(raw: str | None, expected: str) -> None:
    assert map_treatment_strategy(raw) == expected


@pytest.mark.parametrize(
    ("severity", "expected"),
    [
        ("critical", True),
        ("high", True),
        ("HIGH", True),
        (IncidentSeverity.CRITICAL, True),
        ("medium", False),
        ("low", False),
        (None, False),
    ],
)
def test_severity_allows_raise_risk(severity, expected: bool) -> None:
    assert severity_allows_raise_risk(severity) is expected


@pytest.mark.parametrize(
    ("preferred", "incident_type", "expected"),
    [
        (None, "environmental", "environmental"),
        ("operational", "injury", "operational"),
        ("not-a-category", "security", "information_security"),
        ("bogus", "other", "safety"),
    ],
)
def test_resolve_enterprise_category(preferred: str | None, incident_type: str, expected: str) -> None:
    incident = _IncidentStub(incident_type=incident_type)
    assert resolve_enterprise_category(preferred, incident) == expected


def test_default_impact_for_incident() -> None:
    critical = _IncidentStub(severity="critical")
    medium = _IncidentStub(severity="medium")
    assert default_impact_for_incident(critical) == 5
    assert default_impact_for_incident(medium) == 3
    assert default_impact_for_incident(critical, override=2) == 2


def test_risk_register_href() -> None:
    assert risk_register_href() == "/risk-register"
    assert risk_register_href(9) == "/risk-register?riskId=9"
    assert risk_register_href(9, incident_ref="INC-1") == "/risk-register?riskId=9&incidentRef=INC-1"
    assert risk_register_href(incident_ref="INC-1") == "/risk-register?incidentRef=INC-1"


@pytest.mark.asyncio
async def test_resolve_fk_safe_owner_id_prefers_existing_user() -> None:
    class _Result:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_Result(None), _Result(7)])
    owner = await resolve_fk_safe_owner_id(db, preferred_owner_id=99, fallback_user_id=7)
    assert owner == 7
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_resolve_fk_safe_owner_id_returns_none_when_missing() -> None:
    class _Result:
        def scalar_one_or_none(self):
            return None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result())
    owner = await resolve_fk_safe_owner_id(db, preferred_owner_id=99, fallback_user_id=7)
    assert owner is None


@pytest.mark.asyncio
async def test_find_existing_enterprise_risk_for_incident_by_linked_id() -> None:
    class _Result:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    existing = object()
    incident = _IncidentStub()
    incident.id = 11
    incident.reference_number = "INC-11"
    incident.linked_risk_ids = "42"
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result(existing))
    found = await find_existing_enterprise_risk_for_incident(db, incident=incident)
    assert found is existing


@pytest.mark.asyncio
async def test_create_enterprise_risk_requires_tenant() -> None:
    incident = _IncidentStub()
    incident.id = 11
    incident.reference_number = "INC-11"
    incident.tenant_id = None
    incident.owner_id = None
    incident.department = None
    incident.location = None
    db = AsyncMock()
    with pytest.raises(BadRequestError, match="no tenant"):
        await create_enterprise_risk_from_incident(
            db,
            incident=incident,
            actor_user_id=1,
            title="Risk",
            description="Desc",
            likelihood=4,
            impact=4,
            category="safety",
            treatment_strategy="mitigate",
        )
