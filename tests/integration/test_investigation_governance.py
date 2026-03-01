"""
Integration tests for Investigation system governance.
Tests RBAC, canonical error envelopes, determinism, and entity linkage.
"""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.incident import Incident


@pytest.fixture
async def test_incident(test_session: AsyncSession):
    """Create a test incident for investigation tests."""
    incident = Incident(
        title="Test Incident for Investigations",
        description="Test incident",
        incident_date=datetime.now(timezone.utc),
        reported_date=datetime.now(timezone.utc),
        reference_number=f"INC-TEST-{uuid.uuid4().hex[:8]}",
    )
    test_session.add(incident)
    await test_session.commit()
    await test_session.refresh(incident)
    return incident


@pytest.mark.asyncio
class TestInvestigationRBAC:
    """Test RBAC and authentication for Investigation endpoints."""

    async def test_create_template_unauthenticated_401(self, client: AsyncClient):
        """Test that creating a template without authentication returns 401."""
        data = {
            "name": "Test Template",
            "description": "Test",
            "structure": {"sections": []},
            "applicable_entity_types": ["reporting_incident"],
        }
        response = await client.post("/api/v1/investigation-templates/", json=data)

        # Without auth headers, should get 401
        assert response.status_code == 401

    async def test_create_investigation_unauthenticated_401(self, client: AsyncClient):
        """Test that creating an investigation without authentication returns 401."""
        data = {
            "template_id": 1,
            "assigned_entity_type": "reporting_incident",
            "assigned_entity_id": 1,
            "title": "Test Investigation",
        }
        response = await client.post("/api/v1/investigations/", json=data)

        # Without auth headers, should get 401
        assert response.status_code == 401

    async def test_create_template_authenticated_201(self, client: AsyncClient, auth_headers, test_session):
        """Test that creating a template with authentication returns 201."""
        data = {
            "name": "Authenticated Template",
            "description": "Created with auth",
            "structure": {"sections": [{"name": "Overview", "fields": []}]},
            "applicable_entity_types": ["reporting_incident", "complaint"],
        }
        response = await client.post("/api/v1/investigation-templates/", json=data, headers=auth_headers)

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Authenticated Template"
        assert "id" in body


@pytest.mark.asyncio
class TestInvestigationDeterminism:
    """Test deterministic ordering and pagination for Investigation endpoints."""

    async def test_list_investigations_deterministic_ordering(
        self, client: AsyncClient, auth_headers, test_session, test_incident
    ):
        """Test that list investigations returns deterministic ordering."""
        # Create a template
        template_data = {
            "name": "Test Template",
            "description": "Test",
            "structure": {"sections": []},
            "applicable_entity_types": ["reporting_incident"],
        }
        template_response = await client.post(
            "/api/v1/investigation-templates/", json=template_data, headers=auth_headers
        )
        assert template_response.status_code == 201
        template_id = template_response.json()["id"]

        # Create multiple investigations
        for i in range(3):
            data = {
                "template_id": template_id,
                "assigned_entity_type": "reporting_incident",
                "assigned_entity_id": test_incident.id,
                "title": f"Investigation {i}",
            }
            response = await client.post("/api/v1/investigations/", json=data, headers=auth_headers)
            assert response.status_code == 201

        # List investigations twice and verify same order
        response1 = await client.get("/api/v1/investigations/", headers=auth_headers)
        response2 = await client.get("/api/v1/investigations/", headers=auth_headers)

        assert response1.status_code == 200
        assert response2.status_code == 200

        items1 = response1.json()["items"]
        items2 = response2.json()["items"]

        # Same order
        assert [item["id"] for item in items1] == [item["id"] for item in items2]

        # Ordered by created_at DESC, id ASC
        assert items1[0]["id"] > items1[-1]["id"]  # Most recent first

    async def test_list_investigations_pagination(self, client: AsyncClient, auth_headers, test_session, test_incident):
        """Test that list investigations supports pagination."""
        # Create a template
        template_data = {
            "name": "Test Template",
            "description": "Test",
            "structure": {"sections": []},
            "applicable_entity_types": ["reporting_incident"],
        }
        template_response = await client.post(
            "/api/v1/investigation-templates/", json=template_data, headers=auth_headers
        )
        assert template_response.status_code == 201
        template_id = template_response.json()["id"]

        # Create 5 investigations
        for i in range(5):
            data = {
                "template_id": template_id,
                "assigned_entity_type": "reporting_incident",
                "assigned_entity_id": test_incident.id,
                "title": f"Investigation {i}",
            }
            response = await client.post("/api/v1/investigations/", json=data, headers=auth_headers)
            assert response.status_code == 201

        # Get page 1 with page_size=2
        response = await client.get("/api/v1/investigations/?page=1&page_size=2", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["page"] == 1
        assert body["page_size"] == 2
        assert len(body["items"]) == 2
        assert body["total"] >= 5
        assert body["total_pages"] >= 3


@pytest.mark.asyncio
class TestIncidentsInvestigationLinkage:
    """Test investigation linkage to incidents."""

    async def test_get_incident_investigations_deterministic(
        self, client: AsyncClient, auth_headers, test_session, test_incident
    ):
        """Test that incident investigations endpoint returns deterministic order."""
        # Create a template
        template_data = {
            "name": "Test Template",
            "description": "Test",
            "structure": {"sections": []},
            "applicable_entity_types": ["reporting_incident"],
        }
        template_response = await client.post(
            "/api/v1/investigation-templates/", json=template_data, headers=auth_headers
        )
        assert template_response.status_code == 201
        template_id = template_response.json()["id"]

        # Create 3 investigations for this incident
        for i in range(3):
            data = {
                "template_id": template_id,
                "assigned_entity_type": "reporting_incident",
                "assigned_entity_id": test_incident.id,
                "title": f"Investigation {i}",
            }
            response = await client.post("/api/v1/investigations/", json=data, headers=auth_headers)
            assert response.status_code == 201

        # Get investigations for this incident twice
        response1 = await client.get(f"/api/v1/incidents/{test_incident.id}/investigations", headers=auth_headers)
        response2 = await client.get(f"/api/v1/incidents/{test_incident.id}/investigations", headers=auth_headers)

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Response is paginated envelope
        assert "items" in data1
        assert "total" in data1
        assert "page" in data1
        assert "page_size" in data1
        assert "total_pages" in data1

        items1 = data1["items"]
        items2 = data2["items"]

        # Same order
        assert [item["id"] for item in items1] == [item["id"] for item in items2]

        # All investigations belong to this incident
        for item in items1:
            assert item["assigned_entity_id"] == test_incident.id
            assert item["assigned_entity_type"] == "reporting_incident"

        # Pagination fields correct
        assert data1["total"] == 3
        assert data1["page"] == 1
        assert data1["page_size"] == 25
        assert data1["total_pages"] == 1

    async def test_get_incident_investigations_empty_list(
        self, client: AsyncClient, auth_headers, test_session, test_incident
    ):
        """Test that incident with no investigations returns empty paginated response."""
        response = await client.get(f"/api/v1/incidents/{test_incident.id}/investigations", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 0
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 25
        assert data["total_pages"] == 1

    async def test_create_template_inactive_user_403(self, client: AsyncClient, test_session):
        """Test that an inactive user cannot create a template (403 Forbidden)."""
        from src.core.security import create_access_token, get_password_hash
        from src.domain.models.user import User

        # Create inactive user
        inactive_user = User(
            email="inactive@example.com",
            hashed_password=get_password_hash("password123"),
            first_name="Inactive",
            last_name="User",
            is_active=False,  # Inactive
            is_superuser=False,
        )
        test_session.add(inactive_user)
        await test_session.commit()
        await test_session.refresh(inactive_user)

        # Create token for inactive user
        token = create_access_token(subject=inactive_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        data = {
            "name": "Should Fail Template",
            "description": "Inactive user attempt",
            "structure": {"sections": []},
            "applicable_entity_types": ["reporting_incident"],
        }
        response = await client.post("/api/v1/investigation-templates/", json=data, headers=headers)

        # Should get 403 Forbidden
        assert response.status_code == 403
        body = response.json()
        assert "message" in body
        assert "disabled" in body["message"].lower() or "inactive" in body["message"].lower()

    async def test_create_investigation_inactive_user_403(
        self, client: AsyncClient, test_session, test_incident, auth_headers
    ):
        """Test that an inactive user cannot create an investigation (403 Forbidden)."""
        from src.core.security import create_access_token, get_password_hash
        from src.domain.models.investigation import InvestigationTemplate
        from src.domain.models.user import User

        # Create a template first (using active user)
        template = InvestigationTemplate(
            name="Test Template for 403",
            description="Template for testing",
            structure={"sections": []},
            applicable_entity_types=["reporting_incident"],
            created_by_id=1,
            updated_by_id=1,
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        # Create inactive user
        inactive_user = User(
            email="inactive2@example.com",
            hashed_password=get_password_hash("password123"),
            first_name="Inactive",
            last_name="User2",
            is_active=False,  # Inactive
            is_superuser=False,
        )
        test_session.add(inactive_user)
        await test_session.commit()
        await test_session.refresh(inactive_user)

        # Create token for inactive user
        token = create_access_token(subject=inactive_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        data = {
            "template_id": template.id,
            "assigned_entity_type": "reporting_incident",
            "assigned_entity_id": test_incident.id,
            "title": "Should Fail Investigation",
        }
        response = await client.post("/api/v1/investigations/", json=data, headers=headers)

        # Should get 403 Forbidden
        assert response.status_code == 403
        body = response.json()
        assert "message" in body
        assert "disabled" in body["message"].lower() or "inactive" in body["message"].lower()

    async def test_incident_investigations_pagination_fields(
        self, client: AsyncClient, auth_headers, test_session, test_incident
    ):
        """Test that incident investigations pagination fields are correct."""
        # Create a template
        template_data = {
            "name": "Test Template",
            "description": "Test",
            "structure": {"sections": []},
            "applicable_entity_types": ["reporting_incident"],
        }
        template_response = await client.post(
            "/api/v1/investigation-templates/", json=template_data, headers=auth_headers
        )
        assert template_response.status_code == 201
        template_id = template_response.json()["id"]

        # Create 30 investigations for pagination testing
        for i in range(30):
            data = {
                "template_id": template_id,
                "assigned_entity_type": "reporting_incident",
                "assigned_entity_id": test_incident.id,
                "title": f"Investigation {i}",
            }
            response = await client.post("/api/v1/investigations/", json=data, headers=auth_headers)
            assert response.status_code == 201

        # Test page 1 (default page_size=25)
        response = await client.get(f"/api/v1/incidents/{test_incident.id}/investigations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 30
        assert data["page"] == 1
        assert data["page_size"] == 25
        assert data["total_pages"] == 2
        assert len(data["items"]) == 25

        # Test page 2
        response = await client.get(f"/api/v1/incidents/{test_incident.id}/investigations?page=2", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 30
        assert data["page"] == 2
        assert data["page_size"] == 25
        assert data["total_pages"] == 2
        assert len(data["items"]) == 5

        # Test custom page_size
        response = await client.get(
            f"/api/v1/incidents/{test_incident.id}/investigations?page_size=10", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 30
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["total_pages"] == 3
        assert len(data["items"]) == 10

    async def test_incident_investigations_invalid_page_param(
        self, client: AsyncClient, auth_headers, test_session, test_incident
    ):
        """Test that invalid page parameter returns 422 validation error."""
        # page=0 should fail (must be >= 1)
        response = await client.get(f"/api/v1/incidents/{test_incident.id}/investigations?page=0", headers=auth_headers)
        assert response.status_code == 422

        # page=-1 should fail
        response = await client.get(
            f"/api/v1/incidents/{test_incident.id}/investigations?page=-1", headers=auth_headers
        )
        assert response.status_code == 422

    async def test_incident_investigations_invalid_page_size_param(
        self, client: AsyncClient, auth_headers, test_session, test_incident
    ):
        """Test that invalid page_size parameter returns 422 validation error."""
        # page_size=0 should fail (must be >= 1)
        response = await client.get(
            f"/api/v1/incidents/{test_incident.id}/investigations?page_size=0", headers=auth_headers
        )
        assert response.status_code == 422

        # page_size=101 should fail (must be <= 100)
        response = await client.get(
            f"/api/v1/incidents/{test_incident.id}/investigations?page_size=101", headers=auth_headers
        )
        assert response.status_code == 422

        # page_size=999 should fail
        response = await client.get(
            f"/api/v1/incidents/{test_incident.id}/investigations?page_size=999", headers=auth_headers
        )
        assert response.status_code == 422

    async def test_incident_investigations_404_for_nonexistent_incident(
        self, client: AsyncClient, auth_headers, test_session
    ):
        """Test that requesting investigations for nonexistent incident returns 404."""
        response = await client.get("/api/v1/incidents/999999/investigations", headers=auth_headers)
        assert response.status_code == 404
