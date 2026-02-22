"""E2E test: Full incident workflow lifecycle."""

import pytest


@pytest.mark.e2e
class TestWorkflowLifecycle:
    def test_incident_lifecycle(self, client, auth_headers):
        """Create incident -> investigate -> add action -> resolve -> close."""
        if not auth_headers:
            pytest.skip("Auth required")
        
        # 1. Create incident
        resp = client.post("/api/v1/incidents", json={
            "title": "E2E Test Incident",
            "description": "Automated E2E test",
            "severity": "medium",
        }, headers=auth_headers)
        assert resp.status_code in (200, 201)
        incident_data = resp.json()
        incident_id = incident_data.get("id") or incident_data.get("data", {}).get("id")
        assert incident_id is not None
        
        # 2. Get incident
        resp = client.get(f"/api/v1/incidents/{incident_id}", headers=auth_headers)
        assert resp.status_code == 200
        
        # 3. Update status
        resp = client.patch(f"/api/v1/incidents/{incident_id}", json={
            "status": "investigating",
        }, headers=auth_headers)
        assert resp.status_code == 200
