"""Integration tests for Audits API endpoints."""

import json
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditRun, AuditStatus, AuditTemplate
from src.domain.models.user import User
from tests.conftest import generate_test_reference


def _matches_intake_resolver(template: AuditTemplate) -> bool:
    tags = [str(tag).strip().lower() for tag in (template.tags_json or []) if isinstance(tag, str)]
    return "external_audit_intake" in tags or (template.name or "").strip().lower() == "external audit intake"


async def _deactivate_existing_intake_templates(
    test_session: AsyncSession,
    *,
    external_audit_type: str,
) -> None:
    """Keep resolver-backed tests deterministic in the shared integration database."""
    existing_templates = (await test_session.execute(select(AuditTemplate))).scalars().all()
    specific_tag = f"external_audit_intake:{external_audit_type}".lower()
    for template in existing_templates:
        tags = [str(tag).strip().lower() for tag in (template.tags_json or []) if isinstance(tag, str)]
        if _matches_intake_resolver(template) or specific_tag in tags:
            template.is_published = False
            template.is_active = False
    await test_session.commit()


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
                reference_number=generate_test_reference("TPL"),
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
        assert len(data["items"]) >= 3
        assert data.get("total", 0) >= 3

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
            reference_number=generate_test_reference("TPL"),
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
            reference_number=generate_test_reference("TPL"),
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
    async def test_create_external_audit_run_normalizes_import_type(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test external import types map into the canonical audit metadata fields."""
        await _deactivate_existing_intake_templates(test_session, external_audit_type="achilles_uvdb")
        template = AuditTemplate(
            name="ZZZ External Audit Intake (System)",
            category="System",
            audit_type="external_import",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
            is_published=True,
            tags_json=["external_audit_intake", "external_audit_intake:achilles_uvdb"],
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        response = await client.post(
            "/api/v1/audits/runs",
            json={
                "template_id": template.id,
                "title": "Achilles follow-up audit",
                "external_audit_type": "achilles_uvdb",
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["template_id"] == template.id
        assert data["source_origin"] == "third_party"
        assert data["assurance_scheme"] == "Achilles UVDB"
        assert data["is_external_import_intake"] is True

    @pytest.mark.asyncio
    async def test_get_audit_run_detail_marks_external_import_intake(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test run detail surfaces the external import intake marker for safe routing."""
        await _deactivate_existing_intake_templates(test_session, external_audit_type="achilles_uvdb")
        template = AuditTemplate(
            name="ZZZ External Audit Intake (System)",
            category="System",
            audit_type="external_import",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
            is_published=True,
            tags_json=["external_audit_intake", "external_audit_intake:achilles_uvdb"],
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        create_response = await client.post(
            "/api/v1/audits/runs",
            json={
                "template_id": template.id,
                "title": "Achilles follow-up audit",
                "external_audit_type": "achilles_uvdb",
            },
            headers=auth_headers,
        )
        assert create_response.status_code == 201

        run_id = create_response.json()["id"]
        detail_response = await client.get(
            f"/api/v1/audits/runs/{run_id}",
            headers=auth_headers,
        )

        assert detail_response.status_code == 200
        assert detail_response.json()["is_external_import_intake"] is True

    @pytest.mark.asyncio
    async def test_create_external_audit_run_returns_not_found_when_no_intake_template_exists(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test external imports surface a structured 404 when intake config is missing."""
        test_session.add(
            AuditTemplate(
                name="General Safety Audit",
                category="Safety",
                audit_type="audit",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("TPL"),
                is_published=True,
            )
        )
        await _deactivate_existing_intake_templates(test_session, external_audit_type="achilles_uvdb")

        response = await client.post(
            "/api/v1/audits/runs",
            json={
                "template_id": 999999,
                "title": "Achilles follow-up audit",
                "external_audit_type": "achilles_uvdb",
            },
            headers=auth_headers,
        )

        assert response.status_code == 404
        payload = json.dumps(response.json())
        assert (
            "No published external audit intake template is configured for 'achilles_uvdb'" in payload
            or "No published audit templates are available for this tenant" in payload
        )

    @pytest.mark.asyncio
    async def test_create_external_audit_run_fails_closed_when_multiple_intake_templates_match(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test external imports fail closed when intake template resolution is ambiguous."""
        for reference_suffix in ("A", "B"):
            test_session.add(
                AuditTemplate(
                    name=f"ZZZ External Audit Intake ({reference_suffix})",
                    category="System",
                    audit_type="external_import",
                    created_by_id=test_user.id,
                    reference_number=generate_test_reference(f"TPL{reference_suffix}"),
                    is_published=True,
                    tags_json=["external_audit_intake", "external_audit_intake:planet_mark"],
                )
            )
        await test_session.commit()

        response = await client.post(
            "/api/v1/audits/runs",
            json={
                "template_id": 999999,
                "title": "Planet Mark import",
                "external_audit_type": "planet_mark",
            },
            headers=auth_headers,
        )

        assert response.status_code == 409
        assert "Multiple published external audit intake templates match" in str(response.json())

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
            reference_number=generate_test_reference("TPL"),
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
            reference_number=generate_test_reference("AUD"),
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
            reference_number=generate_test_reference("TPL"),
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
                reference_number=generate_test_reference("AUD"),
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
        assert len(data["items"]) >= 3

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
            reference_number=generate_test_reference("TPL"),
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
                reference_number=generate_test_reference("TPL"),
            ),
            AuditTemplate(
                name="Safety 2",
                category="Safety",
                audit_type="inspection",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("TPL"),
            ),
            AuditTemplate(
                name="Quality 1",
                category="Quality",
                audit_type="audit",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("TPL"),
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
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["category"] == "Safety"

    @pytest.mark.asyncio
    async def test_alias_route_honors_template_optimistic_lock(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Alias template route returns 409 when the caller has a stale timestamp."""
        template = AuditTemplate(
            name="Alias Route Lock Test",
            description="Exercises /api/v1/audit-templates optimistic locking",
            category="Quality",
            audit_type="audit",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        stale_updated_at = (template.updated_at - timedelta(minutes=5)).isoformat()

        response = await client.patch(
            f"/api/v1/audit-templates/{template.id}",
            json={
                "name": "Alias Route Lock Test Updated",
                "expected_updated_at": stale_updated_at,
            },
            headers=auth_headers,
        )

        assert response.status_code == 409
        body = response.json()
        message = body.get("detail") or body.get("error", {}).get("message", "")
        assert "modified by another user" in message
