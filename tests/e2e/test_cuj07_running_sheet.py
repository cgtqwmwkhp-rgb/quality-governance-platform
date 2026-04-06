"""CUJ-07: Running sheet entry added to RTA.

User Journey:
1. RTA incident exists
2. Add timestamped running sheet entry
3. Entry visible in running sheet timeline
4. Entry author and timestamp recorded
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
class TestCUJ07RunningSheet:
    """CUJ-07: End-to-end test for RTA running sheet entries."""

    def test_add_running_sheet_entry(self, client, auth_headers):
        """A running sheet entry can be added to an RTA."""
        now = datetime.now().isoformat()
        rta = client.post(
            "/api/v1/rtas/",
            json={
                "title": "CUJ-07: Running sheet case",
                "description": "Timeline updates for insurer",
                "severity": "damage_only",
                "collision_date": now,
                "reported_date": now,
                "location": "Service road",
            },
            headers=auth_headers,
        )
        assert rta.status_code in (200, 201), f"RTA creation failed ({rta.status_code}): {rta.text}"

        rta_id = rta.json().get("id")
        entry_data = {
            "content": "CUJ-07: Police arrived at scene. Officer badge #4521.",
            "entry_type": "update",
        }
        resp = client.post(
            f"/api/v1/rtas/{rta_id}/running-sheet",
            json=entry_data,
            headers=auth_headers,
        )
        assert resp.status_code in (200, 201), f"Running sheet entry failed ({resp.status_code}): {resp.text}"

    def test_running_sheet_timeline_ordered(self, client, auth_headers):
        """Running sheet entries are returned in deterministic order (newest first)."""
        resp = client.get("/api/v1/rtas/", headers=auth_headers)
        assert resp.status_code == 200, f"List RTAs failed ({resp.status_code})"

        now = datetime.now().isoformat()
        rta = client.post(
            "/api/v1/rtas/",
            json={
                "title": "CUJ-07: Ordering",
                "description": "Two entries for ordering check",
                "severity": "damage_only",
                "collision_date": now,
                "reported_date": now,
                "location": "Depot",
            },
            headers=auth_headers,
        )
        assert rta.status_code in (200, 201), f"RTA creation failed ({rta.status_code})"

        rta_id = rta.json().get("id")
        client.post(
            f"/api/v1/rtas/{rta_id}/running-sheet",
            json={"content": "First entry", "entry_type": "note"},
            headers=auth_headers,
        )
        client.post(
            f"/api/v1/rtas/{rta_id}/running-sheet",
            json={"content": "Second entry", "entry_type": "note"},
            headers=auth_headers,
        )

        sheet = client.get(f"/api/v1/rtas/{rta_id}/running-sheet", headers=auth_headers)
        assert sheet.status_code == 200, f"Running sheet fetch failed ({sheet.status_code})"

        entries = sheet.json()
        assert isinstance(entries, list)
        if len(entries) >= 2:
            times = [e.get("created_at") for e in entries if e.get("created_at")]
            assert times == sorted(times, reverse=True)
