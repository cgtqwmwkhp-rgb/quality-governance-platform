"""Contract checks for incident risk links on list responses."""

from datetime import datetime, timezone

from src.api.schemas.incident import IncidentListResponse, IncidentResponse
from src.domain.models.incident import IncidentSeverity, IncidentStatus, IncidentType


def _incident(*, linked_risk_ids: str | None = None) -> IncidentResponse:
    now = datetime.now(timezone.utc)
    return IncidentResponse(
        id=1,
        reference_number="INC-2026-0001",
        title="Forklift tip",
        description="Near tip in bay A",
        incident_type=IncidentType.OTHER,
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.REPORTED,
        incident_date=now,
        reported_date=now,
        created_at=now,
        updated_at=now,
        linked_risk_ids=linked_risk_ids,
    )


def test_incident_list_item_includes_linked_risk_ids() -> None:
    payload = IncidentListResponse(items=[_incident(linked_risk_ids="12,34")], total=1, pages=1)

    assert payload.model_dump()["items"][0]["linked_risk_ids"] == "12,34"


def test_incident_list_item_preserves_absent_risk_links_as_null() -> None:
    payload = IncidentListResponse(items=[_incident()], total=1, pages=1)

    assert payload.model_dump()["items"][0]["linked_risk_ids"] is None
