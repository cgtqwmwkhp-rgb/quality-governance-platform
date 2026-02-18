"""Integration tests for Risk Register API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.risk import OperationalRiskControl, Risk
from src.domain.models.user import User
from tests.conftest import generate_test_reference


class TestRisksAPI:
    """Test suite for Risk Register API endpoints."""

    @pytest.mark.asyncio
    async def test_create_risk(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test creating a new risk."""
        payload = {
            "title": "Data Breach Risk",
            "description": "Unauthorized access to customer data",
            "category": "information_security",
            "likelihood": 3,
            "impact": 5,
            "treatment_strategy": "mitigate",
        }

        response = await client.post(
            "/api/v1/risks",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Data Breach Risk"
        assert data["likelihood"] == 3
        assert data["impact"] == 5
        assert data["risk_score"] == 15
        assert data["risk_level"] == "high"
        assert "reference_number" in data

    @pytest.mark.asyncio
    async def test_list_risks(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test listing risks with pagination."""
        risks = [
            Risk(
                title=f"Risk {i}",
                description=f"Description {i}",
                category="operational",
                likelihood=2,
                impact=3,
                risk_score=6,
                risk_level="medium",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("RSK"),
            )
            for i in range(1, 6)
        ]
        for risk in risks:
            test_session.add(risk)
        await test_session.commit()

        response = await client.get(
            "/api/v1/risks?page=1&page_size=10",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_get_risk_detail(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test getting risk details."""
        risk = Risk(
            title="Supply Chain Disruption",
            description="Supplier failure causing production delays",
            category="operational",
            likelihood=4,
            impact=4,
            risk_score=16,
            risk_level="high",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("RSK"),
        )
        test_session.add(risk)
        await test_session.commit()
        await test_session.refresh(risk)

        response = await client.get(
            f"/api/v1/risks/{risk.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Supply Chain Disruption"
        assert data["risk_score"] == 16

    @pytest.mark.asyncio
    async def test_update_risk(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test updating a risk."""
        risk = Risk(
            title="Original Title",
            description="Original description",
            category="operational",
            likelihood=2,
            impact=2,
            risk_score=4,
            risk_level="low",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("RSK"),
        )
        test_session.add(risk)
        await test_session.commit()
        await test_session.refresh(risk)

        payload = {
            "title": "Updated Title",
            "likelihood": 4,
            "impact": 5,
        }

        response = await client.patch(
            f"/api/v1/risks/{risk.id}",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["likelihood"] == 4
        assert data["impact"] == 5
        assert data["risk_score"] == 20

    @pytest.mark.asyncio
    async def test_add_risk_control(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test adding a control to a risk."""
        risk = Risk(
            title="Cybersecurity Risk",
            description="Malware infection",
            category="information_security",
            likelihood=3,
            impact=4,
            risk_score=12,
            risk_level="high",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("RSK"),
        )
        test_session.add(risk)
        await test_session.commit()
        await test_session.refresh(risk)

        payload = {
            "title": "Antivirus Software",
            "description": "Enterprise antivirus deployed on all endpoints",
            "control_type": "preventive",
            "implementation_status": "implemented",
            "effectiveness": "effective",
        }

        response = await client.post(
            f"/api/v1/risks/{risk.id}/controls",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Antivirus Software"
        assert data["effectiveness"] == "effective"

    @pytest.mark.asyncio
    async def test_list_risk_controls(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test listing controls for a risk."""
        risk = Risk(
            title="Test Risk",
            description="For control testing",
            category="operational",
            likelihood=3,
            impact=3,
            risk_score=9,
            risk_level="medium",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("RSK"),
        )
        test_session.add(risk)
        await test_session.commit()
        await test_session.refresh(risk)

        controls = [
            OperationalRiskControl(
                risk_id=risk.id,
                title=f"Control {i}",
                description=f"Description {i}",
                control_type="preventive",
                implementation_status="implemented",
            )
            for i in range(1, 4)
        ]
        for ctrl in controls:
            test_session.add(ctrl)
        await test_session.commit()

        response = await client.get(
            f"/api/v1/risks/{risk.id}/controls",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_get_risk_statistics(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test getting risk statistics."""
        risks = [
            Risk(
                title="Risk 1",
                description="Desc",
                category="operational",
                likelihood=5,
                impact=5,
                risk_score=25,
                risk_level="critical",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("RSK"),
            ),
            Risk(
                title="Risk 2",
                description="Desc",
                category="operational",
                likelihood=4,
                impact=4,
                risk_score=16,
                risk_level="high",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("RSK"),
            ),
            Risk(
                title="Risk 3",
                description="Desc",
                category="financial",
                likelihood=2,
                impact=2,
                risk_score=4,
                risk_level="low",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("RSK"),
            ),
        ]
        for risk in risks:
            test_session.add(risk)
        await test_session.commit()

        response = await client.get(
            "/api/v1/risks/statistics",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_risks" in data
        assert "risks_by_level" in data
        assert data["total_risks"] == 3

    @pytest.mark.asyncio
    async def test_get_risk_matrix(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test getting risk matrix with counts."""
        risks = [
            Risk(
                title="R1",
                description="D",
                category="operational",
                likelihood=1,
                impact=1,
                risk_score=1,
                risk_level="very_low",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("RSK"),
            ),
            Risk(
                title="R2",
                description="D",
                category="operational",
                likelihood=3,
                impact=3,
                risk_score=9,
                risk_level="medium",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("RSK"),
            ),
            Risk(
                title="R3",
                description="D",
                category="operational",
                likelihood=5,
                impact=5,
                risk_score=25,
                risk_level="critical",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("RSK"),
            ),
        ]
        for risk in risks:
            test_session.add(risk)
        await test_session.commit()

        response = await client.get(
            "/api/v1/risks/matrix",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "matrix" in data
        assert isinstance(data["matrix"], list)

    @pytest.mark.asyncio
    async def test_filter_risks_by_level(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test filtering risks by risk level."""
        risks = [
            Risk(
                title="High Risk 1",
                description="D",
                category="operational",
                likelihood=4,
                impact=4,
                risk_score=16,
                risk_level="high",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("RSK"),
            ),
            Risk(
                title="High Risk 2",
                description="D",
                category="operational",
                likelihood=5,
                impact=4,
                risk_score=20,
                risk_level="high",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("RSK"),
            ),
            Risk(
                title="Low Risk",
                description="D",
                category="operational",
                likelihood=1,
                impact=2,
                risk_score=2,
                risk_level="low",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("RSK"),
            ),
        ]
        for risk in risks:
            test_session.add(risk)
        await test_session.commit()

        response = await client.get(
            "/api/v1/risks?risk_level=high",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["risk_level"] == "high"
