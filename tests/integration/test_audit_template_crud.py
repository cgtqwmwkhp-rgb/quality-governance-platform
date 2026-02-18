"""Integration tests for Audit Template CRUD operations.

Covers the full lifecycle: create, read, update, delete, publish, clone.
Also tests section and question management within templates.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditQuestion, AuditSection, AuditTemplate
from src.domain.models.user import User
from tests.conftest import generate_test_reference


class TestAuditTemplateCRUD:
    """Full CRUD test suite for audit templates."""

    @pytest.mark.asyncio
    async def test_update_audit_template(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test updating an existing audit template."""
        template = AuditTemplate(
            name="Original Name",
            description="Original description",
            category="Safety",
            audit_type="inspection",
            scoring_method="percentage",
            passing_score=80.0,
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        response = await client.patch(
            f"/api/v1/audits/templates/{template.id}",
            json={
                "name": "Updated Name",
                "description": "Updated description",
                "passing_score": 90.0,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"
        assert data["passing_score"] == 90.0

    @pytest.mark.asyncio
    async def test_update_template_mass_assignment_protection(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test that mass assignment of protected fields is blocked."""
        template = AuditTemplate(
            name="Protected Template",
            category="Quality",
            audit_type="audit",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        response = await client.patch(
            f"/api/v1/audits/templates/{template.id}",
            json={
                "name": "Safe Update",
                "is_published": True,
                "is_active": False,
                "version": 99,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Safe Update"
        assert data["is_published"] is False
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_delete_audit_template(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        superuser_auth_headers: dict,
    ):
        """Test soft-deleting an audit template (superuser only)."""
        template = AuditTemplate(
            name="To Be Deleted",
            category="Safety",
            audit_type="inspection",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        response = await client.delete(
            f"/api/v1/audits/templates/{template.id}",
            headers=superuser_auth_headers,
        )

        assert response.status_code == 204

        # Verify it's soft-deleted (not in list)
        list_response = await client.get(
            "/api/v1/audits/templates",
            headers=superuser_auth_headers,
        )
        template_ids = [t["id"] for t in list_response.json()["items"]]
        assert template.id not in template_ids

    @pytest.mark.asyncio
    async def test_publish_template_with_questions(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test publishing a template that has questions."""
        template = AuditTemplate(
            name="Publishable Template",
            category="Quality",
            audit_type="audit",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        section = AuditSection(
            template_id=template.id,
            title="Section 1",
            sort_order=0,
        )
        test_session.add(section)
        await test_session.commit()
        await test_session.refresh(section)

        question = AuditQuestion(
            template_id=template.id,
            section_id=section.id,
            question_text="Is fire equipment accessible?",
            question_type="yes_no",
            sort_order=0,
        )
        test_session.add(question)
        await test_session.commit()

        response = await client.post(
            f"/api/v1/audits/templates/{template.id}/publish",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_published"] is True

    @pytest.mark.asyncio
    async def test_publish_template_without_questions_fails(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test that publishing an empty template fails."""
        template = AuditTemplate(
            name="Empty Template",
            category="Quality",
            audit_type="audit",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        response = await client.post(
            f"/api/v1/audits/templates/{template.id}/publish",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "at least one question" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_nonexistent_template_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test updating a template that doesn't exist."""
        response = await client.patch(
            "/api/v1/audits/templates/99999",
            json={"name": "Ghost"},
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestAuditSectionCRUD:
    """Test suite for audit section operations within templates."""

    @pytest.mark.asyncio
    async def test_create_section(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test creating a section in a template."""
        template = AuditTemplate(
            name="Template With Sections",
            category="Safety",
            audit_type="inspection",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        response = await client.post(
            f"/api/v1/audits/templates/{template.id}/sections",
            json={
                "title": "Fire Safety",
                "description": "Fire safety checks",
                "sort_order": 0,
                "weight": 2.0,
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Fire Safety"
        assert data["weight"] == 2.0

    @pytest.mark.asyncio
    async def test_update_section(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test updating a section."""
        template = AuditTemplate(
            name="Template",
            category="Safety",
            audit_type="inspection",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        section = AuditSection(
            template_id=template.id,
            title="Old Title",
            sort_order=0,
        )
        test_session.add(section)
        await test_session.commit()
        await test_session.refresh(section)

        response = await client.patch(
            f"/api/v1/audits/sections/{section.id}",
            json={"title": "New Title", "weight": 3.0},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["title"] == "New Title"

    @pytest.mark.asyncio
    async def test_delete_section(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test soft-deleting a section."""
        template = AuditTemplate(
            name="Template",
            category="Safety",
            audit_type="inspection",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        section = AuditSection(
            template_id=template.id,
            title="To Delete",
            sort_order=0,
        )
        test_session.add(section)
        await test_session.commit()
        await test_session.refresh(section)

        response = await client.delete(
            f"/api/v1/audits/sections/{section.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204


class TestAuditQuestionCRUD:
    """Test suite for audit question operations."""

    @pytest.mark.asyncio
    async def test_create_question(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test creating a question in a template."""
        template = AuditTemplate(
            name="Template",
            category="Safety",
            audit_type="inspection",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        section = AuditSection(
            template_id=template.id,
            title="Section 1",
            sort_order=0,
        )
        test_session.add(section)
        await test_session.commit()
        await test_session.refresh(section)

        response = await client.post(
            f"/api/v1/audits/templates/{template.id}/questions",
            json={
                "section_id": section.id,
                "question_text": "Are exits clearly marked?",
                "question_type": "yes_no",
                "is_required": True,
                "weight": 2.0,
                "sort_order": 0,
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["question_text"] == "Are exits clearly marked?"
        assert data["question_type"] == "yes_no"
        assert data["weight"] == 2.0

    @pytest.mark.asyncio
    async def test_update_question(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test updating a question."""
        template = AuditTemplate(
            name="Template",
            category="Safety",
            audit_type="inspection",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        question = AuditQuestion(
            template_id=template.id,
            question_text="Original question",
            question_type="yes_no",
            sort_order=0,
        )
        test_session.add(question)
        await test_session.commit()
        await test_session.refresh(question)

        response = await client.patch(
            f"/api/v1/audits/questions/{question.id}",
            json={
                "question_text": "Updated question text",
                "question_type": "pass_fail",
                "weight": 5.0,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["question_text"] == "Updated question text"
        assert data["question_type"] == "pass_fail"

    @pytest.mark.asyncio
    async def test_delete_question(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test soft-deleting a question."""
        template = AuditTemplate(
            name="Template",
            category="Safety",
            audit_type="inspection",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        question = AuditQuestion(
            template_id=template.id,
            question_text="To be deleted",
            question_type="text",
            sort_order=0,
        )
        test_session.add(question)
        await test_session.commit()
        await test_session.refresh(question)

        response = await client.delete(
            f"/api/v1/audits/questions/{question.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_create_question_with_options(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test creating a multiple-choice question with options."""
        template = AuditTemplate(
            name="Template",
            category="Quality",
            audit_type="audit",
            created_by_id=test_user.id,
            reference_number=generate_test_reference("TPL"),
        )
        test_session.add(template)
        await test_session.commit()
        await test_session.refresh(template)

        response = await client.post(
            f"/api/v1/audits/templates/{template.id}/questions",
            json={
                "question_text": "Rate the condition",
                "question_type": "radio",
                "is_required": True,
                "weight": 1.0,
                "sort_order": 0,
                "options": [
                    {"value": "excellent", "label": "Excellent", "score": 5.0},
                    {"value": "good", "label": "Good", "score": 4.0},
                    {"value": "fair", "label": "Fair", "score": 3.0},
                    {"value": "poor", "label": "Poor", "score": 1.0},
                ],
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["question_type"] == "radio"


class TestAuditTemplateLifecycle:
    """Tests for complete template lifecycle workflows."""

    @pytest.mark.asyncio
    async def test_full_template_lifecycle(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test creating a template, adding sections/questions, and publishing."""
        # 1. Create template
        create_response = await client.post(
            "/api/v1/audits/templates",
            json={
                "name": "Lifecycle Test Template",
                "description": "Full lifecycle test",
                "category": "Safety",
                "audit_type": "inspection",
                "scoring_method": "percentage",
                "passing_score": 80.0,
            },
            headers=auth_headers,
        )
        assert create_response.status_code == 201
        template_id = create_response.json()["id"]

        # 2. Add section
        section_response = await client.post(
            f"/api/v1/audits/templates/{template_id}/sections",
            json={"title": "General Safety", "sort_order": 0},
            headers=auth_headers,
        )
        assert section_response.status_code == 201
        section_id = section_response.json()["id"]

        # 3. Add question
        question_response = await client.post(
            f"/api/v1/audits/templates/{template_id}/questions",
            json={
                "section_id": section_id,
                "question_text": "Is the area safe?",
                "question_type": "yes_no",
                "sort_order": 0,
            },
            headers=auth_headers,
        )
        assert question_response.status_code == 201

        # 4. Get full template detail
        detail_response = await client.get(
            f"/api/v1/audits/templates/{template_id}",
            headers=auth_headers,
        )
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["section_count"] == 1
        assert detail["question_count"] == 1

        # 5. Publish
        publish_response = await client.post(
            f"/api/v1/audits/templates/{template_id}/publish",
            headers=auth_headers,
        )
        assert publish_response.status_code == 200
        assert publish_response.json()["is_published"] is True

        # 6. Clone
        clone_response = await client.post(
            f"/api/v1/audits/templates/{template_id}/clone",
            headers=auth_headers,
        )
        assert clone_response.status_code == 201
        assert "Copy of" in clone_response.json()["name"]
        assert clone_response.json()["is_published"] is False

    @pytest.mark.asyncio
    async def test_search_templates(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Test searching templates by name."""
        for name in ["Fire Safety Check", "Vehicle Inspection", "IT Security Audit"]:
            template = AuditTemplate(
                name=name,
                category="Safety",
                audit_type="inspection",
                created_by_id=test_user.id,
                reference_number=generate_test_reference("TPL"),
            )
            test_session.add(template)
        await test_session.commit()

        response = await client.get(
            "/api/v1/audits/templates?search=Fire",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any("Fire" in item["name"] for item in data["items"])
