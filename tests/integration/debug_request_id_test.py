"""Debug test to check request_id value in audit events and error envelopes."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from src.domain.models.audit_log import AuditEvent


@pytest.mark.asyncio
async def test_debug_audit_event_request_id(client: AsyncClient, test_session, test_user, auth_headers):
    """Check if request_id is set in audit events."""
    policy_data = {
        "title": "Debug Test Policy",
        "description": "Testing request_id",
        "document_type": "policy",
        "status": "draft",
    }
    response = await client.post("/api/v1/policies", json=policy_data, headers=auth_headers)
    assert response.status_code == 201
    
    policy_id = response.json()["id"]
    
    # Check audit event
    result = await test_session.execute(
        select(AuditEvent).where(
            AuditEvent.entity_type == "policy",
            AuditEvent.entity_id == str(policy_id),
        )
    )
    audit_event = result.scalar_one_or_none()
    
    print(f"\n=== AUDIT EVENT DEBUG ===")
    print(f"request_id value: {repr(audit_event.request_id)}")
    print(f"request_id is None: {audit_event.request_id is None}")
    print(f"request_id type: {type(audit_event.request_id)}")
    if audit_event.request_id:
        print(f"request_id length: {len(audit_event.request_id)}")
    print(f"=========================\n")
    
    assert audit_event is not None


@pytest.mark.asyncio
async def test_debug_error_envelope_request_id(client: AsyncClient, auth_headers):
    """Check if request_id is set in error envelopes (404)."""
    # Try to get a non-existent policy
    response = await client.get("/api/v1/policies/99999", headers=auth_headers)
    
    print(f"\n=== ERROR ENVELOPE DEBUG ===")
    print(f"Status code: {response.status_code}")
    body = response.json()
    print(f"request_id value: {repr(body.get('request_id'))}")
    print(f"request_id is None: {body.get('request_id') is None}")
    if body.get('request_id'):
        print(f"request_id length: {len(body['request_id'])}")
    print(f"============================\n")
    
    assert response.status_code == 404
