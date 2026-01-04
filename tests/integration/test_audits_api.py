"""Integration tests for Audits API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditRun, AuditStatus, AuditTemplate
from src.domain.models.user import User
from tests.conftest import generate_test_reference


class TestAuditsAPI:
    """Test suite for Audits API endpoints."""

    @pytest.mark.asyncio
    async def test_create_audit_template(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict,
    ):
        """Test creating a new audit template."""
        payload = {
            "name": "Monthly Safety Inspection",
            "description": "Regular safety checks",
            "category": "Safety",
            "audit_type": "inspection",
            "scoring_method": "percentage",
            "passing_score": 80.0,
            "is_active": True,
        }

        response = await client.post(
            "/api/v1/audits/templates",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Monthly Safety Inspection"
        assert data["scoring_method"] == "percentage"
        assert "reference_number" in data

    @pytest.mark.asyncio
    async def test_list_audit_templates(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test listing audit templates."""
        templates = [
            AuditTemplate(
                name=f"Template {i}",
                category="Safety",
                audit_type="inspection",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("TPL", i),
            )
            for i in range(1, 4)
        ]
        for tmpl in templates:
            test_session.add(tmpl)
        await test_session.commit()

        response = await client.get(
            "/api/v1/audits/templates",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 3

    @pytest.mark.asyncio
    async def test_get_audit_template_detail(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test getting audit template details."""
        template = AuditTemplate(
            name="Quality Audit",
            description="ISO 9001 compliance check",
            category="Quality",
            audit_type="audit",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL", 1),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        response = await client.get(
            f"/api/v1/audits/templates/{template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Quality Audit"
        assert data["category"] == "Quality"

    @pytest.mark.asyncio
    async def test_create_audit_run(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test creating an audit run from a template."""
        template = AuditTemplate(
            name="Fire Safety Check",
            category="Safety",
            audit_type="inspection",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL", 1),
            is_published=True,  # Must be published to create runs
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        payload = {
            "template_id": template.id,
            "title": "Q1 2026 Fire Safety Audit",
            "location": "Building A",
            "scheduled_date": "2026-03-15T10:00:00Z",
        }

        response = await client.post(
            "/api/v1/audits/runs",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Q1 2026 Fire Safety Audit"
        assert data["template_id"] == template.id
        assert data["status"] == "scheduled"

    @pytest.mark.asyncio
    async def test_start_audit_run(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test starting an audit run."""
        template = AuditTemplate(
            name="Equipment Inspection",
            category="Safety",
            audit_type="inspection",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL", 1),
            is_published=True,
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        audit_run = AuditRun(
            template_id=template.id,
            title="Equipment Audit",
            status=AuditStatus.SCHEDULED,
            assigned_to_id=test_user.id,
            reference_number=generate_test_reference("AUD", 1),
        )
        test_session.add(audit_run)
        await test_session.commit()
        await test_session.refresh(audit_run)

        response = await client.post(
            f"/api/v1/audits/runs/{audit_run.id}/start",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_list_audit_runs(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test listing audit runs with filtering."""
        template = AuditTemplate(
            name="Test Template",
            category="Testing",
            audit_type="inspection",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL", 1),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        runs = [
            AuditRun(
                template_id=template.id,
                title=f"Audit Run {i}",
                status=AuditStatus.DRAFT,
                assigned_to_id=test_user.id,
                reference_number=generate_test_reference("AUD", i),
            )
            for i in range(1, 4)
        ]
        for run in runs:
            test_session.add(run)
        await test_session.commit()

        response = await client.get(
            "/api/v1/audits/runs",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 3

    @pytest.mark.skip(reason="Quarantined - feature not implemented, see docs/TEST_QUARANTINE_POLICY.md")
    @pytest.mark.asyncio
    async def test_clone_audit_template(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test cloning an existing audit template."""
        template = AuditTemplate(
            name="Original Template",
            description="To be cloned",
            category="Quality",
            audit_type="audit",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL", 1),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        response = await client.post(
            f"/api/v1/audits/templates/{template.id}/clone",
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert "Copy of Original Template" in data["name"]
        assert data["id"] != template.id

    @pytest.mark.asyncio
    async def test_filter_audit_templates_by_category(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test filtering audit templates by category."""
        templates = [
            AuditTemplate(
                name="Safety 1",
                category="Safety",
                audit_type="inspection",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("TPL", 1),
            ),
            AuditTemplate(
                name="Safety 2",
                category="Safety",
                audit_type="inspection",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("TPL", 2),
            ),
            AuditTemplate(
                name="Quality 1",
                category="Quality",
                audit_type="audit",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("TPL", 3),
            ),
        ]
        for tmpl in templates:
            test_session.add(tmpl)
        await test_session.commit()

        response = await client.get(
            "/api/v1/audits/templates?category=Safety",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["category"] == "Safety"
