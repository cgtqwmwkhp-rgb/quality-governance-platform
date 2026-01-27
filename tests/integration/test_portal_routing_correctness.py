"""Integration tests for portal incident routing correctness.

These tests verify that:
1. Each portal report_type routes to the correct database table
2. Admin dashboards return only records from their intended table (no cross-leakage)
3. Source form tracking is correctly recorded for audit purposes

Reference: ADR-0001 quality gates, ADR-0002 fail-fast config validation
"""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.incident import Incident
from src.domain.models.rta import RoadTrafficCollision
from src.domain.models.near_miss import NearMiss
from src.domain.models.complaint import Complaint


class TestPortalRoutingCorrectness:
    """Test suite for portal submission routing correctness."""

    # =========================================================================
    # Test Data - Canonical Mapping Contract
    # =========================================================================

    PORTAL_ROUTING_CONTRACT = {
        "incident": {
            "report_type": "incident",
            "expected_table": "incidents",
            "expected_model": Incident,
            "expected_ref_prefix": "INC-",
            "expected_source_form_id": "portal_incident_v1",
        },
        "complaint": {
            "report_type": "complaint",
            "expected_table": "complaints",
            "expected_model": Complaint,
            "expected_ref_prefix": "COMP-",
            "expected_source_form_id": "portal_complaint_v1",
        },
        "rta": {
            "report_type": "rta",
            "expected_table": "road_traffic_collisions",
            "expected_model": RoadTrafficCollision,
            "expected_ref_prefix": "RTA-",
            "expected_source_form_id": "portal_rta_v1",
        },
        "near_miss": {
            "report_type": "near_miss",
            "expected_table": "near_misses",
            "expected_model": NearMiss,
            "expected_ref_prefix": "NM-",
            "expected_source_form_id": "portal_near_miss_v1",
        },
    }

    # =========================================================================
    # Portal Submission Routing Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_incident_portal_routes_to_incidents_table(self, async_client: AsyncClient, db_session: AsyncSession):
        """Verify incident portal submission creates record in incidents table."""
        # Get initial count
        initial_count = (await db_session.execute(select(func.count()).select_from(Incident))).scalar() or 0

        # Submit via portal
        payload = {
            "report_type": "incident",
            "title": "Test Incident - Routing Verification",
            "description": "This is a test incident to verify portal routing.",
            "location": "Test Location",
            "severity": "medium",
            "reporter_name": "Test User",
            "reporter_email": "test@example.com",
            "is_anonymous": False,
        }

        response = await async_client.post("/api/v1/portal/reports/", json=payload)
        assert response.status_code == 201, f"Portal submission failed: {response.json()}"

        data = response.json()
        assert data["reference_number"].startswith("INC-"), f"Expected INC- prefix, got: {data['reference_number']}"

        # Verify record created in incidents table
        new_count = (await db_session.execute(select(func.count()).select_from(Incident))).scalar() or 0
        assert new_count == initial_count + 1, "Incident not created in incidents table"

        # Verify source_form_id is set for audit
        incident = (
            await db_session.execute(select(Incident).where(Incident.reference_number == data["reference_number"]))
        ).scalar_one_or_none()
        assert incident is not None, "Incident record not found"
        assert (
            incident.source_form_id == "portal_incident_v1"
        ), f"Expected source_form_id 'portal_incident_v1', got: {incident.source_form_id}"

    @pytest.mark.asyncio
    async def test_rta_portal_routes_to_rta_table(self, async_client: AsyncClient, db_session: AsyncSession):
        """Verify RTA portal submission creates record in road_traffic_collisions table."""
        # Get initial count
        initial_count = (await db_session.execute(select(func.count()).select_from(RoadTrafficCollision))).scalar() or 0

        # Submit via portal
        payload = {
            "report_type": "rta",
            "title": "Test RTA - Routing Verification",
            "description": "This is a test RTA to verify portal routing.",
            "location": "Test Road Junction",
            "severity": "high",
            "reporter_name": "Test Driver",
            "reporter_email": "driver@example.com",
            "is_anonymous": False,
        }

        response = await async_client.post("/api/v1/portal/reports/", json=payload)
        assert response.status_code == 201, f"Portal submission failed: {response.json()}"

        data = response.json()
        assert data["reference_number"].startswith("RTA-"), f"Expected RTA- prefix, got: {data['reference_number']}"

        # Verify record created in RTA table (NOT incidents table)
        new_count = (await db_session.execute(select(func.count()).select_from(RoadTrafficCollision))).scalar() or 0
        assert new_count == initial_count + 1, "RTA not created in road_traffic_collisions table"

        # Verify source_form_id is set for audit
        rta = (
            await db_session.execute(
                select(RoadTrafficCollision).where(RoadTrafficCollision.reference_number == data["reference_number"])
            )
        ).scalar_one_or_none()
        assert rta is not None, "RTA record not found"
        assert (
            rta.source_form_id == "portal_rta_v1"
        ), f"Expected source_form_id 'portal_rta_v1', got: {rta.source_form_id}"

    @pytest.mark.asyncio
    async def test_near_miss_portal_routes_to_near_miss_table(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Verify near miss portal submission creates record in near_misses table."""
        # Get initial count
        initial_count = (await db_session.execute(select(func.count()).select_from(NearMiss))).scalar() or 0

        # Submit via portal
        payload = {
            "report_type": "near_miss",
            "title": "Test Near Miss - Routing Verification",
            "description": "This is a test near miss to verify portal routing.",
            "location": "Test Site",
            "severity": "low",
            "reporter_name": "Test Reporter",
            "reporter_email": "reporter@example.com",
            "department": "Test Contract",
            "is_anonymous": False,
        }

        response = await async_client.post("/api/v1/portal/reports/", json=payload)
        assert response.status_code == 201, f"Portal submission failed: {response.json()}"

        data = response.json()
        assert data["reference_number"].startswith("NM-"), f"Expected NM- prefix, got: {data['reference_number']}"

        # Verify record created in near_misses table (NOT incidents table)
        new_count = (await db_session.execute(select(func.count()).select_from(NearMiss))).scalar() or 0
        assert new_count == initial_count + 1, "Near miss not created in near_misses table"

        # Verify source_form_id is set for audit
        near_miss = (
            await db_session.execute(select(NearMiss).where(NearMiss.reference_number == data["reference_number"]))
        ).scalar_one_or_none()
        assert near_miss is not None, "Near miss record not found"
        assert (
            near_miss.source_form_id == "portal_near_miss_v1"
        ), f"Expected source_form_id 'portal_near_miss_v1', got: {near_miss.source_form_id}"

    @pytest.mark.asyncio
    async def test_complaint_portal_routes_to_complaint_table(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Verify complaint portal submission creates record in complaints table."""
        # Get initial count
        initial_count = (await db_session.execute(select(func.count()).select_from(Complaint))).scalar() or 0

        # Submit via portal
        payload = {
            "report_type": "complaint",
            "title": "Test Complaint - Routing Verification",
            "description": "This is a test complaint to verify portal routing.",
            "location": "Test Location",
            "severity": "medium",
            "reporter_name": "Test Complainant",
            "reporter_email": "complainant@example.com",
            "reporter_phone": "07700 000000",
            "is_anonymous": False,
        }

        response = await async_client.post("/api/v1/portal/reports/", json=payload)
        assert response.status_code == 201, f"Portal submission failed: {response.json()}"

        data = response.json()
        assert data["reference_number"].startswith("COMP-"), f"Expected COMP- prefix, got: {data['reference_number']}"

        # Verify record created in complaints table
        new_count = (await db_session.execute(select(func.count()).select_from(Complaint))).scalar() or 0
        assert new_count == initial_count + 1, "Complaint not created in complaints table"

        # Verify source_form_id is set for audit
        complaint = (
            await db_session.execute(select(Complaint).where(Complaint.reference_number == data["reference_number"]))
        ).scalar_one_or_none()
        assert complaint is not None, "Complaint record not found"
        assert (
            complaint.source_form_id == "portal_complaint_v1"
        ), f"Expected source_form_id 'portal_complaint_v1', got: {complaint.source_form_id}"

    # =========================================================================
    # Dashboard Isolation Tests (No Cross-Leakage)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_rta_dashboard_does_not_show_incidents(
        self, async_client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """Verify RTA dashboard API returns only RTAs, not incidents or other types."""
        # Create an incident via portal
        incident_payload = {
            "report_type": "incident",
            "title": "Cross-leak test incident",
            "description": "This incident should NOT appear in RTA dashboard.",
            "severity": "medium",
            "reporter_name": "Test User",
            "is_anonymous": False,
        }
        inc_response = await async_client.post("/api/v1/portal/reports/", json=incident_payload)
        assert inc_response.status_code == 201
        incident_ref = inc_response.json()["reference_number"]

        # Create an RTA via portal
        rta_payload = {
            "report_type": "rta",
            "title": "Cross-leak test RTA",
            "description": "This RTA should appear in RTA dashboard.",
            "location": "Test Road",
            "severity": "high",
            "reporter_name": "Test Driver",
            "is_anonymous": False,
        }
        rta_response = await async_client.post("/api/v1/portal/reports/", json=rta_payload)
        assert rta_response.status_code == 201
        rta_ref = rta_response.json()["reference_number"]

        # Query RTA dashboard API
        dashboard_response = await async_client.get("/api/v1/rtas/", headers=auth_headers)
        assert dashboard_response.status_code == 200

        items = dashboard_response.json()["items"]
        reference_numbers = [item["reference_number"] for item in items]

        # RTA should be present
        assert rta_ref in reference_numbers, f"RTA {rta_ref} not found in RTA dashboard"

        # Incident should NOT be present
        assert (
            incident_ref not in reference_numbers
        ), f"Incident {incident_ref} incorrectly appeared in RTA dashboard - CROSS-LEAKAGE DETECTED"

    @pytest.mark.asyncio
    async def test_incidents_dashboard_does_not_show_rtas(
        self, async_client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """Verify Incidents dashboard API returns only Incidents, not RTAs or other types."""
        # Create an RTA via portal
        rta_payload = {
            "report_type": "rta",
            "title": "Cross-leak test RTA 2",
            "description": "This RTA should NOT appear in Incidents dashboard.",
            "location": "Test Junction",
            "severity": "medium",
            "reporter_name": "Test Driver",
            "is_anonymous": False,
        }
        rta_response = await async_client.post("/api/v1/portal/reports/", json=rta_payload)
        assert rta_response.status_code == 201
        rta_ref = rta_response.json()["reference_number"]

        # Create an incident via portal
        incident_payload = {
            "report_type": "incident",
            "title": "Cross-leak test incident 2",
            "description": "This incident should appear in Incidents dashboard.",
            "severity": "medium",
            "reporter_name": "Test User",
            "is_anonymous": False,
        }
        inc_response = await async_client.post("/api/v1/portal/reports/", json=incident_payload)
        assert inc_response.status_code == 201
        incident_ref = inc_response.json()["reference_number"]

        # Query Incidents dashboard API
        dashboard_response = await async_client.get("/api/v1/incidents/", headers=auth_headers)
        assert dashboard_response.status_code == 200

        items = dashboard_response.json()["items"]
        reference_numbers = [item["reference_number"] for item in items]

        # Incident should be present
        assert incident_ref in reference_numbers, f"Incident {incident_ref} not found in Incidents dashboard"

        # RTA should NOT be present
        assert (
            rta_ref not in reference_numbers
        ), f"RTA {rta_ref} incorrectly appeared in Incidents dashboard - CROSS-LEAKAGE DETECTED"

    # =========================================================================
    # Unknown Report Type Rejection Test
    # =========================================================================

    @pytest.mark.asyncio
    async def test_unknown_report_type_rejected(self, async_client: AsyncClient):
        """Verify unknown report_type is rejected with explicit error (no silent default)."""
        payload = {
            "report_type": "unknown_type",  # Invalid type
            "title": "Test Unknown Type",
            "description": "This should be rejected, not defaulted to incident.",
            "severity": "medium",
            "reporter_name": "Test User",
            "is_anonymous": False,
        }

        response = await async_client.post("/api/v1/portal/reports/", json=payload)

        # Should be rejected, not silently accepted
        assert (
            response.status_code == 400
        ), f"Unknown report_type should be rejected with 400, got {response.status_code}"

        error_detail = response.json().get("detail", "")
        assert (
            "invalid report_type" in error_detail.lower() or "must be" in error_detail.lower()
        ), f"Error message should indicate invalid report_type: {error_detail}"

    # =========================================================================
    # Determinism Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_portal_routing_is_deterministic(self, async_client: AsyncClient, db_session: AsyncSession):
        """Verify repeated submissions with same data produce consistent routing."""
        for i in range(3):
            payload = {
                "report_type": "rta",
                "title": f"Determinism Test RTA {i}",
                "description": "Testing deterministic routing.",
                "location": "Same Location",
                "severity": "medium",
                "reporter_name": "Same User",
                "is_anonymous": False,
            }

            response = await async_client.post("/api/v1/portal/reports/", json=payload)
            assert response.status_code == 201

            data = response.json()
            assert data["reference_number"].startswith(
                "RTA-"
            ), f"Run {i}: Expected RTA- prefix, got: {data['reference_number']}"

    # =========================================================================
    # Mapping Contract Completeness Test
    # =========================================================================

    @pytest.mark.asyncio
    async def test_all_portal_types_have_complete_mapping(self, async_client: AsyncClient):
        """Verify all portal types in contract are correctly routed."""
        for portal_type, contract in self.PORTAL_ROUTING_CONTRACT.items():
            payload = {
                "report_type": contract["report_type"],
                "title": f"Mapping Test - {portal_type}",
                "description": f"Testing mapping for {portal_type} type.",
                "location": "Test Location",
                "severity": "medium",
                "reporter_name": "Test User",
                "department": "Test Contract",  # Required for near_miss
                "is_anonymous": False,
            }

            response = await async_client.post("/api/v1/portal/reports/", json=payload)
            assert response.status_code == 201, f"Portal type '{portal_type}' submission failed: {response.json()}"

            data = response.json()
            assert data["reference_number"].startswith(contract["expected_ref_prefix"]), (
                f"Portal type '{portal_type}': Expected {contract['expected_ref_prefix']} prefix, "
                f"got: {data['reference_number']}"
            )


class TestSourceFormAuditTrail:
    """Tests for source_form_id audit trail correctness."""

    @pytest.mark.asyncio
    async def test_source_form_id_enables_audit_query(self, async_client: AsyncClient, db_session: AsyncSession):
        """Verify source_form_id allows tracing portal submissions for audit."""
        # Submit multiple types
        for report_type, source_form in [
            ("incident", "portal_incident_v1"),
            ("rta", "portal_rta_v1"),
            ("near_miss", "portal_near_miss_v1"),
            ("complaint", "portal_complaint_v1"),
        ]:
            payload = {
                "report_type": report_type,
                "title": f"Audit Trail Test - {report_type}",
                "description": f"Testing audit trail for {report_type}.",
                "location": "Audit Test Location",
                "severity": "medium",
                "reporter_name": "Audit Tester",
                "department": "Audit Contract",
                "is_anonymous": False,
            }

            response = await async_client.post("/api/v1/portal/reports/", json=payload)
            assert response.status_code == 201

        # Query for portal-sourced incidents only
        incident_count = (
            await db_session.execute(
                select(func.count()).select_from(Incident).where(Incident.source_form_id == "portal_incident_v1")
            )
        ).scalar() or 0

        assert incident_count >= 1, "Should find portal-sourced incidents by source_form_id"

        # Query for portal-sourced RTAs only
        rta_count = (
            await db_session.execute(
                select(func.count())
                .select_from(RoadTrafficCollision)
                .where(RoadTrafficCollision.source_form_id == "portal_rta_v1")
            )
        ).scalar() or 0

        assert rta_count >= 1, "Should find portal-sourced RTAs by source_form_id"
