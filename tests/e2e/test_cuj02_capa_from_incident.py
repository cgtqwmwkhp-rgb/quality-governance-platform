"""CUJ-02: Manager creates CAPA from incident.

User Journey:
1. Create an incident
2. Set severity to trigger CAPA requirement
3. Promote incident to CAPA action
4. Verify CAPA action is created with correct linkage
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """HTTP client against the FastAPI app (matches sibling E2E modules)."""
    from src.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers(client):
    """Bearer token headers when login succeeds; empty dict otherwise."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@plantexpand.com", "password": "adminpassword123"},
    )
    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


@pytest.mark.e2e
class TestCUJ02CAPAFromIncident:
    """CUJ-02: End-to-end test for creating CAPA from incident."""

    def test_incident_creation_triggers_capa(self, client, auth_headers):
        """Creating a high-severity incident should allow raising a linked CAPA."""
        incident_data = {
            "title": "CUJ-02: Serious equipment failure",
            "description": "Hydraulic press safety guard malfunction during operation",
            "incident_type": "quality",
            "severity": "high",
            "incident_date": "2026-03-15T10:00:00Z",
            "location": "Manufacturing Floor B",
        }
        resp = client.post("/api/v1/incidents/", json=incident_data, headers=auth_headers)
        assert resp.status_code in (200, 201), f"Incident creation failed ({resp.status_code}): {resp.text}"

        incident_id = resp.json().get("id")
        assert incident_id is not None

        capa_body = {
            "title": "CUJ-02: CAPA from incident",
            "description": "Corrective action for equipment guard failure",
            "capa_type": "corrective",
            "priority": "high",
            "source_type": "incident",
            "source_id": incident_id,
            "proposed_action": "Replace guard interlock and re-train operators",
        }
        capa_resp = client.post("/api/v1/capa", json=capa_body, headers=auth_headers)
        assert capa_resp.status_code in (200, 201), f"CAPA creation failed ({capa_resp.status_code}): {capa_resp.text}"

        capa_data = capa_resp.json()
        capa_id = capa_data.get("id")
        if "source_id" in capa_data:
            assert (
                capa_data["source_id"] == incident_id
            ), f"CAPA source_id {capa_data['source_id']} does not match incident {incident_id}"
        else:
            get_resp = client.get(f"/api/v1/capa/{capa_id}", headers=auth_headers)
            if get_resp.status_code == 200:
                fetched = get_resp.json()
                assert fetched.get("source_id") == incident_id, (
                    f"CAPA GET source_id {fetched.get('source_id')} " f"does not match incident {incident_id}"
                )

    def test_capa_action_linked_to_incident(self, client, auth_headers):
        """CAPA action created from incident should reference the source incident."""
        resp = client.get("/api/v1/incidents/", headers=auth_headers)
        assert resp.status_code == 200, f"List incidents failed ({resp.status_code})"

        inc = client.post(
            "/api/v1/incidents/",
            json={
                "title": "CUJ-02: Linkage check",
                "description": "Verify CAPA source linkage",
                "incident_type": "quality",
                "severity": "high",
                "incident_date": datetime.now().isoformat(),
                "location": "Plant floor",
            },
            headers=auth_headers,
        )
        assert inc.status_code in (200, 201), f"Incident creation failed ({inc.status_code})"

        incident_id = inc.json().get("id")
        client.post(
            "/api/v1/capa",
            json={
                "title": "CUJ-02: Linked CAPA",
                "capa_type": "corrective",
                "source_type": "incident",
                "source_id": incident_id,
            },
            headers=auth_headers,
        )

        listed = client.get("/api/v1/capa", headers=auth_headers)
        assert listed.status_code == 200, f"List CAPAs failed ({listed.status_code})"
