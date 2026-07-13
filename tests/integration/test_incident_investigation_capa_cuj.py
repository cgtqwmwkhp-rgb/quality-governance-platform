"""Live-database proof for the incident → investigation → CAPA journey."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.investigation import AssignedEntityType, InvestigationRun


@pytest.mark.asyncio
async def test_incident_investigation_capa_chain(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_session: AsyncSession,
) -> None:
    """HTTP chain: incident → from-record investigation → CAPA linkage."""
    incident_date = datetime.now(timezone.utc)
    incident_payload = {
        "title": "CUJ slip near loading bay",
        "description": "Operator slipped on wet surface",
        "incident_type": "injury",
        "severity": "high",
        "status": "reported",
        "incident_date": incident_date.isoformat(),
        "location": "Loading bay",
    }

    incident_response = await client.post(
        "/api/v1/incidents/",
        json=incident_payload,
        headers=auth_headers,
    )
    assert incident_response.status_code == 201, incident_response.text
    incident = incident_response.json()
    incident_id = incident["id"]

    investigation_response = await client.post(
        "/api/v1/investigations/from-record",
        json={
            "source_type": "reporting_incident",
            "source_id": incident_id,
            "title": "CUJ investigation for slip",
        },
        headers=auth_headers,
    )
    assert investigation_response.status_code == 201, investigation_response.text
    investigation = investigation_response.json()
    investigation_id = investigation["id"]
    assert investigation["assigned_entity_type"] == "reporting_incident"
    assert investigation["assigned_entity_id"] == incident_id

    test_session.expire_all()
    persisted = await test_session.scalar(
        select(InvestigationRun).where(InvestigationRun.id == investigation_id),
    )
    assert persisted is not None
    assert persisted.assigned_entity_type == AssignedEntityType.REPORTING_INCIDENT
    assert persisted.assigned_entity_id == incident_id

    linked_response = await client.get(
        f"/api/v1/incidents/{incident_id}/investigations",
        headers=auth_headers,
    )
    assert linked_response.status_code == 200, linked_response.text
    linked_items = linked_response.json()["items"]
    assert any(item["id"] == investigation_id for item in linked_items)

    action_payload = {
        "title": "Install anti-slip matting",
        "description": "Reduce slip risk at loading bay",
        "source_type": "investigation",
        "source_id": investigation_id,
        "priority": "high",
        "action_type": "corrective",
    }
    action_response = await client.post(
        "/api/v1/actions/",
        json=action_payload,
        headers=auth_headers,
    )
    assert action_response.status_code == 201, action_response.text
    action = action_response.json()
    assert action["source_type"] == "investigation"
    assert action["source_id"] == investigation_id
    assert action["reference_number"] is not None

    scoped_list = await client.get(
        "/api/v1/actions/",
        params={"source_type": "investigation", "source_id": investigation_id},
        headers=auth_headers,
    )
    assert scoped_list.status_code == 200, scoped_list.text
    scoped_items = scoped_list.json()["items"]
    assert any(item["id"] == action["id"] for item in scoped_items)

    incident_action_payload = {
        "title": "Barrier cordon while matting installed",
        "description": "Temporary control while CAPA is implemented",
        "source_type": "incident",
        "source_id": incident_id,
        "priority": "medium",
        "action_type": "corrective",
    }
    incident_action_response = await client.post(
        "/api/v1/actions/",
        json=incident_action_payload,
        headers=auth_headers,
    )
    assert incident_action_response.status_code == 201, incident_action_response.text
    incident_action = incident_action_response.json()
    assert incident_action["source_type"] == "incident"
    assert incident_action["source_id"] == incident_id

    incident_scoped = await client.get(
        "/api/v1/actions/",
        params={"source_type": "incident", "source_id": incident_id},
        headers=auth_headers,
    )
    assert incident_scoped.status_code == 200, incident_scoped.text
    incident_items = incident_scoped.json()["items"]
    assert any(item["id"] == incident_action["id"] for item in incident_items)
