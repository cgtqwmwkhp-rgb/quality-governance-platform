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
            "/api/v1/standards/",
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
            Standard(
                code="ISO-9001",
                name="ISO 9001",
                full_name="Quality",
                version="2015",
                is_active=True,
            ),
            Standard(
                code="ISO-14001",
                name="ISO 14001",
                full_name="Environmental",
                version="2015",
                is_active=True,
            ),
            Standard(
                code="ISO-27001",
                name="ISO 27001",
                full_name="Security",
                version="2022",
                is_active=True,
            ),
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
            "/api/v1/standards/",
            json=payload,
            headers=auth_headers,  # Regular user, not superuser
        )

        assert response.status_code == 403


class TestComplianceScoreAPI:
    """Test suite for compliance score and controls aggregation endpoints."""

    @pytest.mark.asyncio
    async def test_compliance_score_zero_controls(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        auth_headers: dict,
    ):
        """Test compliance score returns setup_required=true when no controls."""
        standard = Standard(
            code="ISO-EMPTY",
            name="ISO Empty",
            full_name="Empty Standard",
            version="2024",
            is_active=True,
        )
        test_session.add(standard)
        await test_session.commit()
        await test_session.refresh(standard)

        response = await client.get(
            f"/api/v1/standards/{standard.id}/compliance-score",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["standard_id"] == standard.id
        assert data["standard_code"] == "ISO-EMPTY"
        assert data["total_controls"] == 0
        assert data["implemented_count"] == 0
        assert data["partial_count"] == 0
        assert data["not_implemented_count"] == 0
        assert data["compliance_percentage"] == 0
        assert data["setup_required"] is True

    @pytest.mark.asyncio
    async def test_compliance_score_calculation(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        auth_headers: dict,
    ):
        """Test compliance score calculation with mixed statuses."""
        standard = Standard(
            code="ISO-COMP",
            name="ISO Compliance",
            full_name="Compliance Test Standard",
            version="2024",
            is_active=True,
        )
        test_session.add(standard)
        await test_session.commit()
        await test_session.refresh(standard)

        clause = Clause(
            standard_id=standard.id,
            clause_number="5.1",
            title="Test Clause",
            sort_order=1,
        )
        test_session.add(clause)
        await test_session.commit()
        await test_session.refresh(clause)

        # Add 4 controls: 2 implemented, 1 partial, 1 not_implemented
        controls = [
            Control(
                clause_id=clause.id,
                control_number="5.1.1",
                title="Implemented Control 1",
                implementation_status="implemented",
                is_applicable=True,
            ),
            Control(
                clause_id=clause.id,
                control_number="5.1.2",
                title="Implemented Control 2",
                implementation_status="implemented",
                is_applicable=True,
            ),
            Control(
                clause_id=clause.id,
                control_number="5.1.3",
                title="Partial Control",
                implementation_status="partial",
                is_applicable=True,
            ),
            Control(
                clause_id=clause.id,
                control_number="5.1.4",
                title="Not Implemented Control",
                implementation_status="not_implemented",
                is_applicable=True,
            ),
        ]
        for ctrl in controls:
            test_session.add(ctrl)
        await test_session.commit()

        response = await client.get(
            f"/api/v1/standards/{standard.id}/compliance-score",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_controls"] == 4
        assert data["implemented_count"] == 2
        assert data["partial_count"] == 1
        assert data["not_implemented_count"] == 1
        # (2 + 0.5*1) / 4 * 100 = 2.5/4 * 100 = 62.5 => 62 (rounded)
        assert data["compliance_percentage"] == 62
        assert data["setup_required"] is False

    @pytest.mark.asyncio
    async def test_compliance_score_excludes_non_applicable(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        auth_headers: dict,
    ):
        """Test compliance score excludes non-applicable controls."""
        standard = Standard(
            code="ISO-NA",
            name="ISO NA",
            full_name="Non-Applicable Test",
            version="2024",
            is_active=True,
        )
        test_session.add(standard)
        await test_session.commit()
        await test_session.refresh(standard)

        clause = Clause(
            standard_id=standard.id,
            clause_number="6.1",
            title="Test Clause",
            sort_order=1,
        )
        test_session.add(clause)
        await test_session.commit()
        await test_session.refresh(clause)

        controls = [
            Control(
                clause_id=clause.id,
                control_number="6.1.1",
                title="Applicable Implemented",
                implementation_status="implemented",
                is_applicable=True,
            ),
            Control(
                clause_id=clause.id,
                control_number="6.1.2",
                title="Non-Applicable Control",
                implementation_status="not_implemented",
                is_applicable=False,  # Should be excluded
            ),
        ]
        for ctrl in controls:
            test_session.add(ctrl)
        await test_session.commit()

        response = await client.get(
            f"/api/v1/standards/{standard.id}/compliance-score",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_controls"] == 1  # Only applicable control
        assert data["implemented_count"] == 1
        assert data["compliance_percentage"] == 100

    @pytest.mark.asyncio
    async def test_compliance_score_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test compliance score returns 404 for non-existent standard."""
        response = await client.get(
            "/api/v1/standards/99999/compliance-score",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_controls_deterministic_order(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        auth_headers: dict,
    ):
        """Test controls list ordering is deterministic across calls."""
        standard = Standard(
            code="ISO-ORD",
            name="ISO Order",
            full_name="Order Test Standard",
            version="2024",
            is_active=True,
        )
        test_session.add(standard)
        await test_session.commit()
        await test_session.refresh(standard)

        # Add clauses with different sort orders
        clause1 = Clause(
            standard_id=standard.id,
            clause_number="4.2",
            title="Second Clause",
            sort_order=2,
        )
        clause2 = Clause(
            standard_id=standard.id,
            clause_number="4.1",
            title="First Clause",
            sort_order=1,
        )
        test_session.add(clause1)
        test_session.add(clause2)
        await test_session.commit()
        await test_session.refresh(clause1)
        await test_session.refresh(clause2)

        # Add controls in non-sorted order
        controls = [
            Control(
                clause_id=clause1.id,
                control_number="4.2.2",
                title="C4",
                is_applicable=True,
            ),
            Control(
                clause_id=clause2.id,
                control_number="4.1.1",
                title="C1",
                is_applicable=True,
            ),
            Control(
                clause_id=clause1.id,
                control_number="4.2.1",
                title="C3",
                is_applicable=True,
            ),
            Control(
                clause_id=clause2.id,
                control_number="4.1.2",
                title="C2",
                is_applicable=True,
            ),
        ]
        for ctrl in controls:
            test_session.add(ctrl)
        await test_session.commit()

        # Make two requests and verify ordering is stable
        response1 = await client.get(
            f"/api/v1/standards/{standard.id}/controls",
            headers=auth_headers,
        )
        response2 = await client.get(
            f"/api/v1/standards/{standard.id}/controls",
            headers=auth_headers,
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Both responses should be identical
        assert len(data1) == 4
        assert data1 == data2

        # Verify order: clause sort_order, then clause_number, then control_number
        control_numbers = [c["control_number"] for c in data1]
        assert control_numbers == ["4.1.1", "4.1.2", "4.2.1", "4.2.2"]

    @pytest.mark.asyncio
    async def test_list_controls_with_status(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        auth_headers: dict,
    ):
        """Test controls list returns implementation status."""
        standard = Standard(
            code="ISO-STAT",
            name="ISO Status",
            full_name="Status Test Standard",
            version="2024",
            is_active=True,
        )
        test_session.add(standard)
        await test_session.commit()
        await test_session.refresh(standard)

        clause = Clause(
            standard_id=standard.id,
            clause_number="7.1",
            title="Test Clause",
            sort_order=1,
        )
        test_session.add(clause)
        await test_session.commit()
        await test_session.refresh(clause)

        control = Control(
            clause_id=clause.id,
            control_number="7.1.1",
            title="Test Control",
            implementation_status="partial",
            is_applicable=True,
        )
        test_session.add(control)
        await test_session.commit()

        response = await client.get(
            f"/api/v1/standards/{standard.id}/controls",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["control_number"] == "7.1.1"
        assert data[0]["clause_number"] == "7.1"
        assert data[0]["implementation_status"] == "partial"
        assert data[0]["is_applicable"] is True

    @pytest.mark.asyncio
    async def test_list_controls_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test controls list returns 404 for non-existent standard."""
        response = await client.get(
            "/api/v1/standards/99999/controls",
            headers=auth_headers,
        )
        assert response.status_code == 404
