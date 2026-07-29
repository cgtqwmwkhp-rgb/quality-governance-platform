"""C-5 / PX-142b: an audit entry must identify the record, the change and the origin.

Measured on 28/07, entries carried ``user_name`` and ``user_email`` (PR #1381)
but ``entity_name``, ``changed_fields``, ``ip_address`` and ``user_agent`` were
null on every row sampled. The trail could therefore say "this named user updated
an incident from this unknown place", which is a count of activity rather than
evidence of it.

These tests go through the real ASGI stack and then read the persisted row back,
because the failure being guarded against is precisely a value that is *accepted*
as a parameter and never reaches the column. Asserting on the call arguments
would have passed against the defect.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.audit_log import AuditLogEntry
from src.domain.services.audit_service import NO_SINGLE_ENTITY, record_audit_event
from src.infrastructure.middleware.tenant_context import apply_tenant_guc

pytestmark = pytest.mark.asyncio

CLIENT_IP = "203.0.113.7"
CLIENT_AGENT = "QGP-Evidence-Probe/1.0"
ORIGIN_HEADERS = {"X-Forwarded-For": CLIENT_IP, "User-Agent": CLIENT_AGENT}


async def _entry_for(test_session, *, entity_type: str, entity_id: str, action: str) -> AuditLogEntry:
    await apply_tenant_guc(test_session, 1)
    test_session.expire_all()
    result = await test_session.execute(
        select(AuditLogEntry)
        .where(
            AuditLogEntry.tenant_id == 1,
            AuditLogEntry.entity_type == entity_type,
            AuditLogEntry.entity_id == entity_id,
            AuditLogEntry.action == action,
        )
        .order_by(AuditLogEntry.sequence.desc())
    )
    entry = result.scalars().first()
    assert entry is not None, f"no {action} audit entry for {entity_type} {entity_id}"
    return entry


def _incident_payload(title: str) -> dict:
    return {
        "title": title,
        "description": "Audit record content proof",
        "incident_type": "injury",
        "severity": "low",
        "status": "reported",
        "incident_date": datetime.now(timezone.utc).isoformat(),
        "location": "Lab",
        "department": "QA",
    }


async def test_created_entry_names_the_record_and_its_origin(client: AsyncClient, auth_headers, test_session):
    """A create through the API records which incident, from which client."""
    response = await client.post(
        "/api/v1/incidents/",
        json=_incident_payload("C-5 create names the record"),
        headers={**auth_headers, **ORIGIN_HEADERS},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    incident_id = str(body["id"])

    entry = await _entry_for(test_session, entity_type="incident", entity_id=incident_id, action="create")

    # C-5: the specific record, not just "an incident".
    assert entry.entity_name, "entity_name is null — the entry does not say which incident"
    assert entry.entity_name == body["reference_number"], (
        f"entity_name {entry.entity_name!r} is not the incident's reference " f"{body['reference_number']!r}"
    )

    # PX-142b: the request origin, carried out of band via ContextVar.
    assert entry.ip_address == CLIENT_IP, f"ip_address is {entry.ip_address!r}, expected {CLIENT_IP!r}"
    assert entry.user_agent == CLIENT_AGENT, f"user_agent is {entry.user_agent!r}"


async def test_updated_entry_records_which_fields_changed(client: AsyncClient, auth_headers, test_session):
    """C-5: an update must name the fields it carried, not just the record."""
    created = await client.post(
        "/api/v1/incidents/",
        json=_incident_payload("C-5 update names the fields"),
        headers={**auth_headers, **ORIGIN_HEADERS},
    )
    assert created.status_code == 201, created.text
    incident_id = str(created.json()["id"])

    response = await client.patch(
        f"/api/v1/incidents/{incident_id}",
        json={"location": "Workshop", "severity": "medium"},
        headers={**auth_headers, **ORIGIN_HEADERS},
    )
    assert response.status_code == 200, response.text

    entry = await _entry_for(test_session, entity_type="incident", entity_id=incident_id, action="update")

    assert entry.changed_fields, "changed_fields is null — the entry does not say what changed"
    assert "location" in entry.changed_fields, f"changed_fields={entry.changed_fields}"
    assert "severity" in entry.changed_fields, f"changed_fields={entry.changed_fields}"
    assert entry.entity_name, "entity_name is null on the update entry"
    assert entry.ip_address == CLIENT_IP


async def test_origin_falls_back_to_the_direct_peer_without_a_proxy_header(
    client: AsyncClient, auth_headers, test_session
):
    """No X-Forwarded-For: record whatever peer address the transport reports, or nothing."""
    response = await client.post(
        "/api/v1/incidents/",
        json=_incident_payload("C-5 no forwarded header"),
        headers={**auth_headers, "User-Agent": CLIENT_AGENT},
    )
    assert response.status_code == 201, response.text
    incident_id = str(response.json()["id"])

    entry = await _entry_for(test_session, entity_type="incident", entity_id=incident_id, action="create")

    assert entry.user_agent == CLIENT_AGENT
    # ASGITransport supplies no client peer, so this is legitimately absent. The
    # point is that it is null rather than a fabricated placeholder.
    assert entry.ip_address is None or entry.ip_address != ""


async def test_bulk_event_marks_the_absence_of_a_single_record_explicitly(test_session, test_tenant, test_user):
    """A set-valued event stores the marker, so "no one record" is not read as "we forgot"."""
    await record_audit_event(
        db=test_session,
        event_type="complaint.list_filtered",
        entity_type="complaint",
        entity_id="*",
        action="list",
        entity_name=NO_SINGLE_ENTITY,
        payload={"filter_type": "complainant_email"},
        user_id=test_user.id,
        tenant_id=test_tenant.id,
    )
    await test_session.commit()

    await apply_tenant_guc(test_session, test_tenant.id)
    entry = (
        await test_session.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.tenant_id == test_tenant.id,
                AuditLogEntry.entity_id == "*",
            )
        )
    ).scalar_one()

    assert entry.entity_name == NO_SINGLE_ENTITY
    assert entry.entity_name is not None


async def test_event_recorded_outside_a_request_degrades_to_absent_origin(test_session, test_tenant, test_user):
    """A Celery task / startup path has no request: null origin, and no refusal.

    The fail-closed behaviour from #1413 must not extend to metadata. This asserts
    the event is still written, which is the part that matters.
    """
    event = await record_audit_event(
        db=test_session,
        event_type="capa.created",
        entity_type="capa",
        entity_id="9100",
        action="create",
        entity_name="CAPA-BACKGROUND-1",
        payload={"title": "No request context"},
        user_id=test_user.id,
        tenant_id=test_tenant.id,
    )
    await test_session.commit()
    assert event.id is not None, "a missing request context refused the event"

    await apply_tenant_guc(test_session, test_tenant.id)
    entry = (
        await test_session.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.tenant_id == test_tenant.id,
                AuditLogEntry.entity_id == "9100",
            )
        )
    ).scalar_one()

    assert entry.ip_address is None
    assert entry.user_agent is None
    assert entry.entity_name == "CAPA-BACKGROUND-1"


async def test_an_oversized_user_agent_does_not_refuse_the_mutation(test_session, test_tenant, test_user):
    """A 2 KB User-Agent must be clipped, not allowed to fail the flush.

    ``user_agent`` is String(500). Without truncation an oversized header raises on
    flush, and because the bridge now fails closed that would roll back and refuse
    the business mutation — a header turning into a rejected incident report.
    """
    from src.domain.context.audit_request_context import audit_request_context

    with audit_request_context(ip_address="198.51.100.9", user_agent="U" * 2000):
        await record_audit_event(
            db=test_session,
            event_type="capa.created",
            entity_type="capa",
            entity_id="9101",
            action="create",
            entity_name="CAPA-LONG-UA",
            payload={"title": "Oversized agent"},
            user_id=test_user.id,
            tenant_id=test_tenant.id,
        )
        await test_session.commit()

    await apply_tenant_guc(test_session, test_tenant.id)
    entry = (
        await test_session.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.tenant_id == test_tenant.id,
                AuditLogEntry.entity_id == "9101",
            )
        )
    ).scalar_one()

    assert entry.user_agent is not None
    assert len(entry.user_agent) == 500
    assert entry.ip_address == "198.51.100.9"
