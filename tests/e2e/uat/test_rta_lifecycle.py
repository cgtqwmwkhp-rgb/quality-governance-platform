"""
UAT E2E Tests: RTA Lifecycle

Tests the admin RTA workflow contract against the UAT harness client:
1. Create RTA
2. Update status (reported → under_investigation)
3. List RTA-scoped actions
4. Create investigation from RTA (from-record)
5. Add running-sheet entry
6. List RTA investigations

Uses deterministic path/status/data assertions on the UATApiClient stub contract
(no vacuous `assert True` / commented HTTP bodies).
"""

from typing import Any, Dict

import pytest
from conftest import UATApiClient

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.uat,
    pytest.mark.rta,
]


class TestRTALifecycle:
    """Test complete RTA admin lifecycle."""

    @pytest.mark.asyncio
    async def test_create_rta(self, admin_client: UATApiClient) -> None:
        """Admin can create a new RTA."""
        rta_data = {
            "title": "UAT Test - Fleet collision",
            "description": "Created during UAT testing",
            "severity": "damage_only",
            "collision_date": "2026-06-01T09:00:00Z",
            "reported_date": "2026-06-01T10:00:00Z",
            "location": "A1 junction",
        }

        response = await admin_client.post("/api/v1/rtas/", rta_data)

        assert response["status"] in ("created", "ok")
        assert response["path"] == "/api/v1/rtas/"
        assert response["data"]["title"] == "UAT Test - Fleet collision"
        assert response["data"]["severity"] == "damage_only"

    @pytest.mark.asyncio
    async def test_patch_rta_status_under_investigation(self, admin_client: UATApiClient) -> None:
        """Admin can move an RTA into under_investigation."""
        rta_id = "uat-rta-open"
        update_data: Dict[str, Any] = {"status": "under_investigation"}

        response = await admin_client.put(f"/api/v1/rtas/{rta_id}", update_data)

        assert response["status"] == "updated"
        assert response["path"] == f"/api/v1/rtas/{rta_id}"
        assert response["data"]["status"] == "under_investigation"

    @pytest.mark.asyncio
    async def test_list_rta_scoped_actions(self, admin_client: UATApiClient) -> None:
        """Can list actions scoped to an RTA source."""
        rta_id = "uat-rta-open"

        response = await admin_client.get(f"/api/v1/actions/?page=1&page_size=10&source_type=rta&source_id={rta_id}")

        assert response["status"] == "ok"
        assert "source_type=rta" in response["path"] or response["path"].startswith("/api/v1/actions/")

    @pytest.mark.asyncio
    async def test_create_investigation_from_rta(self, admin_client: UATApiClient) -> None:
        """Admin can start an investigation from an RTA via from-record."""
        payload = {
            "source_type": "road_traffic_collision",
            "source_id": "uat-rta-open",
            "title": "UAT RTA investigation",
        }

        response = await admin_client.post("/api/v1/investigations/from-record", payload)

        assert response["status"] in ("created", "ok")
        assert response["path"] == "/api/v1/investigations/from-record"
        assert response["data"]["source_type"] == "road_traffic_collision"
        assert response["data"]["title"] == "UAT RTA investigation"

    @pytest.mark.asyncio
    async def test_add_rta_running_sheet_entry(self, admin_client: UATApiClient) -> None:
        """Admin can append a running-sheet note to an RTA."""
        rta_id = "uat-rta-open"
        payload = {"content": "UAT: police reference confirmed by phone"}

        response = await admin_client.post(
            f"/api/v1/rtas/{rta_id}/running-sheet",
            payload,
        )

        assert response["status"] in ("created", "ok")
        assert response["path"] == f"/api/v1/rtas/{rta_id}/running-sheet"
        assert response["data"]["content"] == "UAT: police reference confirmed by phone"

    @pytest.mark.asyncio
    async def test_list_rta_investigations(self, admin_client: UATApiClient) -> None:
        """Can list investigations linked to an RTA."""
        rta_id = "uat-rta-open"

        response = await admin_client.get(f"/api/v1/rtas/{rta_id}/investigations?page=1&page_size=10")

        assert response["status"] == "ok"
        assert response["path"] == f"/api/v1/rtas/{rta_id}/investigations?page=1&page_size=10"
