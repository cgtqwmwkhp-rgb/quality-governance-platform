"""
UAT E2E Tests: Complaint Lifecycle

Tests the admin complaint workflow contract against the UAT harness client:
1. Create complaint
2. Update status (received → acknowledged)
3. List complaint-scoped actions
4. Create investigation from complaint (from-record)
5. Add running-sheet entry

Uses deterministic path/status assertions on the UATApiClient stub contract
(no vacuous `assert True` / commented HTTP bodies).
"""

from typing import Any, Dict

import pytest
from conftest import UATApiClient

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.uat,
    pytest.mark.complaint,
]


class TestComplaintLifecycle:
    """Test complete complaint admin lifecycle."""

    @pytest.mark.asyncio
    async def test_create_complaint(self, admin_client: UATApiClient) -> None:
        """Admin can create a new complaint."""
        complaint_data = {
            "title": "UAT Test - Service delay",
            "description": "Created during UAT testing",
            "complaint_type": "service",
            "received_date": "2026-03-10T08:30:00Z",
            "complainant_name": "UAT Complainant",
            "complainant_email": "uat@test.local",
            "priority": "medium",
        }

        response = await admin_client.post("/api/v1/complaints/", complaint_data)

        assert response["status"] in ("created", "ok")
        assert response["path"] == "/api/v1/complaints/"
        assert response["data"]["title"] == "UAT Test - Service delay"
        assert response["data"]["complaint_type"] == "service"

    @pytest.mark.asyncio
    async def test_patch_complaint_status_acknowledged(self, admin_client: UATApiClient) -> None:
        """Admin can acknowledge a complaint."""
        complaint_id = "uat-complaint-open"
        update_data: Dict[str, Any] = {"status": "acknowledged"}

        response = await admin_client.put(f"/api/v1/complaints/{complaint_id}", update_data)

        assert response["status"] == "updated"
        assert response["path"] == f"/api/v1/complaints/{complaint_id}"
        assert response["data"]["status"] == "acknowledged"

    @pytest.mark.asyncio
    async def test_list_complaint_scoped_actions(self, admin_client: UATApiClient) -> None:
        """Can list actions scoped to a complaint source."""
        complaint_id = "uat-complaint-open"

        response = await admin_client.get(
            f"/api/v1/actions/?page=1&page_size=10&source_type=complaint&source_id={complaint_id}"
        )

        assert response["status"] == "ok"
        assert "source_type=complaint" in response["path"] or response["path"].startswith("/api/v1/actions/")

    @pytest.mark.asyncio
    async def test_create_investigation_from_complaint(self, admin_client: UATApiClient) -> None:
        """Admin can start an investigation from a complaint via from-record."""
        payload = {
            "source_type": "complaint",
            "source_id": "uat-complaint-open",
            "title": "UAT complaint investigation",
        }

        response = await admin_client.post("/api/v1/investigations/from-record", payload)

        assert response["status"] in ("created", "ok")
        assert response["path"] == "/api/v1/investigations/from-record"
        assert response["data"]["source_type"] == "complaint"
        assert response["data"]["title"] == "UAT complaint investigation"

    @pytest.mark.asyncio
    async def test_add_complaint_running_sheet_entry(self, admin_client: UATApiClient) -> None:
        """Admin can append a running-sheet note to a complaint."""
        complaint_id = "uat-complaint-open"
        payload = {"content": "UAT: acknowledged complainant by phone"}

        response = await admin_client.post(
            f"/api/v1/complaints/{complaint_id}/running-sheet",
            payload,
        )

        assert response["status"] in ("created", "ok")
        assert response["path"] == f"/api/v1/complaints/{complaint_id}/running-sheet"
        assert response["data"]["content"] == "UAT: acknowledged complainant by phone"

    @pytest.mark.asyncio
    async def test_list_complaint_investigations(self, admin_client: UATApiClient) -> None:
        """Can list investigations linked to a complaint."""
        complaint_id = "uat-complaint-open"

        response = await admin_client.get(f"/api/v1/complaints/{complaint_id}/investigations?page=1&page_size=10")

        assert response["status"] == "ok"
        assert response["path"] == f"/api/v1/complaints/{complaint_id}/investigations?page=1&page_size=10"
