"""CUJ-05: Witness details added to RTA.

User Journey:
1. RTA incident exists
2. Add witness statement
3. Witness details are recorded
4. Running sheet entry created
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@plantexpand.com", "password": "adminpassword123"},
    )
    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


@pytest.mark.e2e
class TestCUJ05WitnessDetails:
    """CUJ-05: End-to-end test for adding witness details to RTA."""

    def test_add_witness_to_rta(self, client, auth_headers):
        """Witness details can be added to an existing RTA."""
        now = datetime.now().isoformat()
        rta_data = {
            "title": "CUJ-05: Rear-end collision on M4",
            "description": "Low-speed rear-end collision at traffic lights",
            "severity": "damage_only",
            "collision_date": now,
            "reported_date": now,
            "location": "M4 Junction 28",
        }
        resp = client.post("/api/v1/rtas/", json=rta_data, headers=auth_headers)
        assert resp.status_code in (200, 201), f"RTA creation failed ({resp.status_code}): {resp.text}"

        rta_id = resp.json().get("id")
        witness_update = {
            "witnesses": "Independent witness: Jane Doe.",
            "witnesses_structured": {
                "name": "Jane Doe",
                "statement_summary": "Observed stationary queue; other vehicle failed to stop.",
            },
        }
        patch = client.patch(f"/api/v1/rtas/{rta_id}", json=witness_update, headers=auth_headers)
        assert patch.status_code == 200, f"RTA witness update failed ({patch.status_code}): {patch.text}"

    def test_running_sheet_entry_for_witness(self, client, auth_headers):
        """Adding witness details can be mirrored with a running sheet entry."""
        resp = client.get("/api/v1/rtas/", headers=auth_headers)
        assert resp.status_code == 200, f"List RTAs failed ({resp.status_code})"

        now = datetime.now().isoformat()
        create = client.post(
            "/api/v1/rtas/",
            json={
                "title": "CUJ-05: Witness running sheet",
                "description": "Witness statement logged",
                "severity": "damage_only",
                "collision_date": now,
                "reported_date": now,
                "location": "A-road junction",
            },
            headers=auth_headers,
        )
        assert create.status_code in (200, 201), f"RTA creation failed ({create.status_code})"

        rta_id = create.json().get("id")
        entry = client.post(
            f"/api/v1/rtas/{rta_id}/running-sheet",
            json={
                "content": "Witness statement captured and stored in case file.",
                "entry_type": "communication",
            },
            headers=auth_headers,
        )
        assert entry.status_code in (200, 201), f"Running sheet entry failed ({entry.status_code}): {entry.text}"
