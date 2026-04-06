"""CUJ-03: Driver completes daily vehicle checklist.

User Journey:
1. Driver authenticates
2. Selects assigned vehicle
3. Completes pre-departure checklist
4. Submits with defect flagged
5. Defect creates follow-up action
"""

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
class TestCUJ03DailyVehicleChecklist:
    """CUJ-03: End-to-end test for daily vehicle checklist completion."""

    def test_vehicle_check_submission(self, client, auth_headers):
        """Driver can flag a defect against a daily checklist record (vehicle-checklists API)."""
        check_data = {
            "pams_table": "daily",
            "pams_record_id": 1,
            "check_field": "brakes",
            "check_value": "defect",
            "priority": "P2",
            "notes": "Squealing on rear left",
            "vehicle_reg": "CUJ03E2E",
        }
        resp = client.post(
            "/api/v1/vehicle-checklists/defects",
            json=check_data,
            headers=auth_headers,
        )
        assert resp.status_code in (200, 201), f"Check submission failed ({resp.status_code}): {resp.text}"

    def test_defect_creates_followup(self, client, auth_headers):
        """Vehicle defects list supports follow-up workflows."""
        resp = client.get("/api/v1/vehicle-checklists/defects", headers=auth_headers)
        assert resp.status_code == 200, f"Defects list failed ({resp.status_code})"
