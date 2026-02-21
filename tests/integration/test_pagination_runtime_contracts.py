"""
Integration tests for pagination runtime contract enforcement.

These tests verify that the runtime behavior of list endpoints matches the
canonical pagination contract defined in Stage 3.0.
"""

import math
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from src.domain.models.complaint import Complaint
from src.domain.models.incident import Incident
from src.domain.models.policy import Policy


class TestPoliciesPaginationRuntimeContract:
    """Test that Policies module honors the canonical pagination contract at runtime."""

    @pytest.mark.asyncio
    async def test_pagination_parameters_honored(
        self, client: AsyncClient, test_session, auth_headers
    ):
        """Verify that page and page_size parameters are honored."""
        # Create 15 policies
        for i in range(15):
            policy = Policy(
                title=f"Policy {i}",
                description=f"Description {i}",
                document_type="policy",
                status="draft",
                reference_number=f"POL-2026-{i+1:04d}",
                created_by_id=1,
                updated_by_id=1,
            )
            test_session.add(policy)
        await test_session.commit()

        # Request page 2 with page_size 5
        response = await client.get(
            "/api/v1/policies?page=2&page_size=5", headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 5
        assert len(data["items"]) == 5
        assert data["total"] == 15

    @pytest.mark.asyncio
    async def test_total_and_pages_correct(
        self, client: AsyncClient, test_session, auth_headers
    ):
        """Verify that total and pages fields are calculated correctly."""
        # Create 23 policies
        for i in range(23):
            policy = Policy(
                title=f"Policy {i}",
                description=f"Description {i}",
                document_type="policy",
                status="draft",
                reference_number=f"POL-2026-{i+1:04d}",
                created_by_id=1,
                updated_by_id=1,
            )
            test_session.add(policy)
        await test_session.commit()

        # Request with page_size 10
        response = await client.get(
            "/api/v1/policies?page=1&page_size=10", headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 23
        assert data["pages"] == math.ceil(23 / 10)  # Should be 3

    @pytest.mark.asyncio
    async def test_ordering_deterministic_across_pages(
        self, client: AsyncClient, test_session, auth_headers
    ):
        """Verify that ordering is deterministic across pages."""
        # Create 10 policies with same reference_number prefix but different IDs
        policies = []
        for i in range(10):
            policy = Policy(
                title=f"Policy {i}",
                description=f"Description {i}",
                document_type="policy",
                status="draft",
                reference_number=f"POL-2026-{i+1:04d}",
                created_by_id=1,
                updated_by_id=1,
            )
            test_session.add(policy)
            await test_session.flush()
            policies.append(policy.id)
        await test_session.commit()

        # Fetch all items across 2 pages
        response1 = await client.get(
            "/api/v1/policies?page=1&page_size=5", headers=auth_headers
        )
        response2 = await client.get(
            "/api/v1/policies?page=2&page_size=5", headers=auth_headers
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        page1_ids = [item["id"] for item in response1.json()["items"]]
        page2_ids = [item["id"] for item in response2.json()["items"]]

        # Verify no overlap
        assert set(page1_ids).isdisjoint(set(page2_ids))

        # Verify ordering is deterministic (reference_number DESC, id ASC)
        all_ids = page1_ids + page2_ids
        assert len(all_ids) == 10
        assert len(set(all_ids)) == 10  # No duplicates


class TestIncidentsPaginationRuntimeContract:
    """Test that Incidents module honors the canonical pagination contract at runtime."""

    @pytest.mark.asyncio
    async def test_pagination_parameters_honored(
        self, client: AsyncClient, test_session, auth_headers
    ):
        """Verify that page and page_size parameters are honored."""
        # Create 12 incidents
        for i in range(12):
            incident = Incident(
                title=f"Incident {i}",
                description=f"Description {i}",
                incident_type="injury",
                severity="low",
                status="reported",
                incident_date=datetime.now(timezone.utc),
                reported_date=datetime.now(timezone.utc),
                location="Test Location",
                department="Test Department",
                reference_number=f"INC-2026-{i+1:04d}",
                reporter_id=1,
                created_by_id=1,
                updated_by_id=1,
            )
            test_session.add(incident)
        await test_session.commit()

        # Request page 2 with page_size 5
        response = await client.get(
            "/api/v1/incidents?page=2&page_size=5", headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 5
        assert len(data["items"]) == 5
        assert data["total"] == 12

    @pytest.mark.asyncio
    async def test_total_and_pages_correct(
        self, client: AsyncClient, test_session, auth_headers
    ):
        """Verify that total and pages fields are calculated correctly."""
        # Create 17 incidents
        for i in range(17):
            incident = Incident(
                title=f"Incident {i}",
                description=f"Description {i}",
                incident_type="injury",
                severity="low",
                status="reported",
                incident_date=datetime.now(timezone.utc),
                reported_date=datetime.now(timezone.utc),
                location="Test Location",
                department="Test Department",
                reference_number=f"INC-2026-{i+1:04d}",
                reporter_id=1,
                created_by_id=1,
                updated_by_id=1,
            )
            test_session.add(incident)
        await test_session.commit()

        # Request with page_size 8
        response = await client.get(
            "/api/v1/incidents?page=1&page_size=8", headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 17
        assert data["pages"] == math.ceil(17 / 8)  # Should be 3

    @pytest.mark.asyncio
    async def test_ordering_deterministic_across_pages(
        self, client: AsyncClient, test_session, auth_headers
    ):
        """Verify that ordering is deterministic across pages."""
        # Create 8 incidents
        incidents = []
        for i in range(8):
            incident = Incident(
                title=f"Incident {i}",
                description=f"Description {i}",
                incident_type="injury",
                severity="low",
                status="reported",
                incident_date=datetime.now(timezone.utc),
                reported_date=datetime.now(timezone.utc),
                location="Test Location",
                department="Test Department",
                reference_number=f"INC-2026-{i+1:04d}",
                reporter_id=1,
                created_by_id=1,
                updated_by_id=1,
            )
            test_session.add(incident)
            await test_session.flush()
            incidents.append(incident.id)
        await test_session.commit()

        # Fetch all items across 2 pages
        response1 = await client.get(
            "/api/v1/incidents?page=1&page_size=4", headers=auth_headers
        )
        response2 = await client.get(
            "/api/v1/incidents?page=2&page_size=4", headers=auth_headers
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        page1_ids = [item["id"] for item in response1.json()["items"]]
        page2_ids = [item["id"] for item in response2.json()["items"]]

        # Verify no overlap
        assert set(page1_ids).isdisjoint(set(page2_ids))

        # Verify all IDs are present
        all_ids = page1_ids + page2_ids
        assert len(all_ids) == 8
        assert len(set(all_ids)) == 8  # No duplicates


class TestComplaintsPaginationRuntimeContract:
    """Test that Complaints module honors the canonical pagination contract at runtime."""

    @pytest.mark.asyncio
    async def test_pagination_parameters_honored(
        self, client: AsyncClient, test_session, auth_headers
    ):
        """Verify that page and page_size parameters are honored."""
        # Create 14 complaints
        for i in range(14):
            complaint = Complaint(
                title=f"Complaint {i}",
                description=f"Description {i}",
                complainant_name="Test User",
                complainant_email="test@example.com",
                received_date=datetime.now(timezone.utc),
                status="received",
                priority="medium",
                complaint_type="service",
                reference_number=f"COMP-2026-{i+1:04d}",
            )
            test_session.add(complaint)
        await test_session.commit()

        # Request page 2 with page_size 6
        response = await client.get(
            "/api/v1/complaints/?page=2&page_size=6", headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 6
        assert len(data["items"]) == 6
        assert data["total"] == 14

    @pytest.mark.asyncio
    async def test_total_and_pages_correct(
        self, client: AsyncClient, test_session, auth_headers
    ):
        """Verify that total and pages fields are calculated correctly."""
        # Create 19 complaints
        for i in range(19):
            complaint = Complaint(
                title=f"Complaint {i}",
                description=f"Description {i}",
                complainant_name="Test User",
                complainant_email="test@example.com",
                received_date=datetime.now(timezone.utc),
                status="received",
                priority="medium",
                complaint_type="service",
                reference_number=f"COMP-2026-{i+1:04d}",
            )
            test_session.add(complaint)
        await test_session.commit()

        # Request with page_size 7
        response = await client.get(
            "/api/v1/complaints/?page=1&page_size=7", headers=auth_headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 19
        assert data["pages"] == math.ceil(19 / 7)  # Should be 3

    @pytest.mark.asyncio
    async def test_ordering_deterministic_across_pages(
        self, client: AsyncClient, test_session, auth_headers
    ):
        """Verify that ordering is deterministic across pages."""
        # Create 9 complaints
        complaints = []
        for i in range(9):
            complaint = Complaint(
                title=f"Complaint {i}",
                description=f"Description {i}",
                complainant_name="Test User",
                complainant_email="test@example.com",
                received_date=datetime.now(timezone.utc),
                status="received",
                priority="medium",
                complaint_type="service",
                reference_number=f"COMP-2026-{i+1:04d}",
            )
            test_session.add(complaint)
            await test_session.flush()
            complaints.append(complaint.id)
        await test_session.commit()

        # Fetch all items across 3 pages
        response1 = await client.get(
            "/api/v1/complaints/?page=1&page_size=3", headers=auth_headers
        )
        response2 = await client.get(
            "/api/v1/complaints/?page=2&page_size=3", headers=auth_headers
        )
        response3 = await client.get(
            "/api/v1/complaints/?page=3&page_size=3", headers=auth_headers
        )

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200

        page1_ids = [item["id"] for item in response1.json()["items"]]
        page2_ids = [item["id"] for item in response2.json()["items"]]
        page3_ids = [item["id"] for item in response3.json()["items"]]

        # Verify no overlap
        assert set(page1_ids).isdisjoint(set(page2_ids))
        assert set(page2_ids).isdisjoint(set(page3_ids))
        assert set(page1_ids).isdisjoint(set(page3_ids))

        # Verify all IDs are present
        all_ids = page1_ids + page2_ids + page3_ids
        assert len(all_ids) == 9
        assert len(set(all_ids)) == 9  # No duplicates
