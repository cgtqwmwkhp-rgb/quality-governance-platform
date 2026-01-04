"""Integration tests for Standards API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.standard import Clause, Control, Standard


class TestStandardsAPI:
    """Test suite for Standards API endpoints."""

    @pytest.mark.asyncio
    async def test_create_standard(
        self,
        client: AsyncClient,
        superuser_auth_headers: dict,
    ):
        """Test creating a new standard."""
        payload = {
            "code": "ISO-9001",
            "name": "ISO 9001",
            "full_name": "Quality Management Systems",
            "version": "2015",
            "description": "Requirements for quality management systems",
            "is_active": True,
        }

        response = await client.post(
            "/api/v1/standards",
            json=payload,
            headers=superuser_auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "ISO-9001"
        assert data["name"] == "ISO 9001"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_list_standards(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        auth_headers: dict,
    ):
        """Test listing standards with pagination."""
        # Create test standards
        standards = [
            Standard(
                code=f"ISO-{i}",
                name=f"ISO {i}",
                full_name=f"Standard {i}",
                version="2015",
                is_active=True,
            )
            for i in range(1, 6)
        ]
        for std in standards:
            test_session.add(std)
        await test_session.commit()

        response = await client.get(
            "/api/v1/standards?page=1&page_size=10",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 5
        assert len(data["items"]) == 5

    @pytest.mark.asyncio
    async def test_get_standard_detail(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        auth_headers: dict,
    ):
        """Test getting standard details with clauses and controls."""
        # Create standard with clauses and controls
        standard = Standard(
            code="ISO-9001",
            name="ISO 9001",
            full_name="Quality Management Systems",
            version="2015",
            is_active=True,
        )
        test_session.add(standard)
        await test_session.commit()
        await test_session.refresh(standard)

        clause = Clause(
            standard_id=standard.id,
            clause_number="4.1",
            title="Understanding the organization",
            description="Context of the organization",
        )
        test_session.add(clause)
        await test_session.commit()
        await test_session.refresh(clause)

        control = Control(
            clause_id=clause.id,
            control_number="4.1.1",
            title="Context determination",
            description="Determine external and internal issues",
        )
        test_session.add(control)
        await test_session.commit()

        response = await client.get(
            f"/api/v1/standards/{standard.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "ISO-9001"
        assert "clauses" in data
        assert len(data["clauses"]) == 1
        assert data["clauses"][0]["clause_number"] == "4.1"

    @pytest.mark.asyncio
    async def test_create_clause(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        superuser_auth_headers: dict,
    ):
        """Test creating a clause for a standard."""
        # Create standard first
        standard = Standard(
            code="ISO-14001",
            name="ISO 14001",
            full_name="Environmental Management",
            version="2015",
            is_active=True,
        )
        test_session.add(standard)
        await test_session.commit()
        await test_session.refresh(standard)

        payload = {
            "standard_id": standard.id,
            "clause_number": "4.1",
            "title": "Understanding the organization",
            "description": "Context requirements",
        }

        response = await client.post(
            f"/api/v1/standards/{standard.id}/clauses",
            json=payload,
            headers=superuser_auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["clause_number"] == "4.1"
        assert data["standard_id"] == standard.id

    @pytest.mark.asyncio
    async def test_create_control(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        superuser_auth_headers: dict,
    ):
        """Test creating a control for a clause."""
        # Create standard and clause
        standard = Standard(
            code="ISO-27001",
            name="ISO 27001",
            full_name="Information Security",
            version="2022",
            is_active=True,
        )
        test_session.add(standard)
        await test_session.commit()
        await test_session.refresh(standard)

        clause = Clause(
            standard_id=standard.id,
            clause_number="5.1",
            title="Policies for information security",
            description="Management direction",
        )
        test_session.add(clause)
        await test_session.commit()
        await test_session.refresh(clause)

        payload = {
            "clause_id": clause.id,
            "control_number": "5.1.1",
            "title": "Information security policy",
            "description": "Documented policy approved by management",
            "implementation_guidance": "Create and maintain policy document",
        }

        response = await client.post(
            f"/api/v1/standards/clauses/{clause.id}/controls",
            json=payload,
            headers=superuser_auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["control_number"] == "5.1.1"
        assert data["clause_id"] == clause.id

    @pytest.mark.asyncio
    async def test_search_standards(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        auth_headers: dict,
    ):
        """Test searching standards by code or name."""
        standards = [
            Standard(code="ISO-9001", name="ISO 9001", full_name="Quality", version="2015", is_active=True),
            Standard(code="ISO-14001", name="ISO 14001", full_name="Environmental", version="2015", is_active=True),
            Standard(code="ISO-27001", name="ISO 27001", full_name="Security", version="2022", is_active=True),
        ]
        for std in standards:
            test_session.add(std)
        await test_session.commit()

        response = await client.get(
            "/api/v1/standards?search=27001",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["code"] == "ISO-27001"

    @pytest.mark.asyncio
    async def test_unauthorized_create_standard(self, client: AsyncClient, auth_headers: dict):
        """Test that non-superusers cannot create standards."""
        payload = {
            "code": "ISO-45001",
            "name": "ISO 45001",
            "full_name": "Occupational Health & Safety",
            "version": "2018",
            "is_active": True,
        }

        response = await client.post(
            "/api/v1/standards",
            json=payload,
            headers=auth_headers,  # Regular user, not superuser
        )

        assert response.status_code == 403
