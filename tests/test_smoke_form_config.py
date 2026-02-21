"""Smoke tests for Form Configuration Admin API.

These tests verify that all form config endpoints are working correctly.
Run with: pytest tests/test_smoke_form_config.py -v
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.form_config import (
    Contract,
    FormField,
    FormStep,
    FormTemplate,
    LookupOption,
    SystemSetting,
)
from src.main import app


class TestFormTemplateEndpoints:
    """Test form template CRUD operations."""

    @pytest.fixture
    def sample_template_data(self):
        return {
            "name": "Test Incident Form",
            "slug": "test-incident-form",
            "description": "A test form for incidents",
            "form_type": "incident",
            "icon": "AlertTriangle",
            "color": "#ef4444",
            "allow_drafts": True,
            "allow_attachments": True,
            "require_signature": False,
            "auto_assign_reference": True,
            "reference_prefix": "TEST",
            "notify_on_submit": True,
            "steps": [
                {
                    "name": "Basic Info",
                    "description": "Enter basic information",
                    "order": 0,
                    "fields": [
                        {
                            "name": "title",
                            "label": "Title",
                            "field_type": "text",
                            "order": 0,
                            "is_required": True,
                            "width": "full",
                        },
                        {
                            "name": "description",
                            "label": "Description",
                            "field_type": "textarea",
                            "order": 1,
                            "is_required": True,
                            "width": "full",
                        },
                    ],
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_list_templates(self, async_client: AsyncClient, auth_headers: dict):
        """Test listing form templates."""
        response = await async_client.get(
            "/api/v1/admin/config/templates",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_create_template(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_template_data: dict,
    ):
        """Test creating a new form template."""
        response = await async_client.post(
            "/api/v1/admin/config/templates",
            headers=auth_headers,
            json=sample_template_data,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_template_data["name"]
        assert data["slug"] == sample_template_data["slug"]
        assert data["form_type"] == sample_template_data["form_type"]
        assert "id" in data

    @pytest.mark.asyncio
    async def test_get_template_by_id(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_template_data: dict,
    ):
        """Test getting a template by ID."""
        # First create a template
        create_response = await async_client.post(
            "/api/v1/admin/config/templates",
            headers=auth_headers,
            json={**sample_template_data, "slug": "test-get-by-id"},
        )
        template_id = create_response.json()["id"]

        # Then get it
        response = await async_client.get(
            f"/api/v1/admin/config/templates/{template_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["id"] == template_id

    @pytest.mark.asyncio
    async def test_update_template(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_template_data: dict,
    ):
        """Test updating a form template."""
        # First create a template
        create_response = await async_client.post(
            "/api/v1/admin/config/templates",
            headers=auth_headers,
            json={**sample_template_data, "slug": "test-update"},
        )
        template_id = create_response.json()["id"]

        # Then update it
        response = await async_client.patch(
            f"/api/v1/admin/config/templates/{template_id}",
            headers=auth_headers,
            json={"name": "Updated Name", "description": "Updated description"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_publish_template(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_template_data: dict,
    ):
        """Test publishing a form template."""
        # First create a template
        create_response = await async_client.post(
            "/api/v1/admin/config/templates",
            headers=auth_headers,
            json={**sample_template_data, "slug": "test-publish"},
        )
        template_id = create_response.json()["id"]

        # Then publish it
        response = await async_client.post(
            f"/api/v1/admin/config/templates/{template_id}/publish",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_published"] is True
        assert response.json()["published_at"] is not None

    @pytest.mark.asyncio
    async def test_delete_template(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_template_data: dict,
    ):
        """Test deleting a form template."""
        # First create a template
        create_response = await async_client.post(
            "/api/v1/admin/config/templates",
            headers=auth_headers,
            json={**sample_template_data, "slug": "test-delete"},
        )
        template_id = create_response.json()["id"]

        # Then delete it
        response = await async_client.delete(
            f"/api/v1/admin/config/templates/{template_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204


class TestContractEndpoints:
    """Test contract CRUD operations."""

    @pytest.fixture
    def sample_contract_data(self):
        return {
            "name": "Test Contract",
            "code": "test-contract",
            "description": "A test contract",
            "client_name": "Test Client Ltd",
            "is_active": True,
            "display_order": 1,
        }

    @pytest.mark.asyncio
    async def test_list_contracts(self, async_client: AsyncClient, auth_headers: dict):
        """Test listing contracts."""
        response = await async_client.get(
            "/api/v1/admin/config/contracts",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_create_contract(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_contract_data: dict,
    ):
        """Test creating a new contract."""
        response = await async_client.post(
            "/api/v1/admin/config/contracts",
            headers=auth_headers,
            json=sample_contract_data,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_contract_data["name"]
        assert data["code"] == sample_contract_data["code"]

    @pytest.mark.asyncio
    async def test_update_contract(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_contract_data: dict,
    ):
        """Test updating a contract."""
        # First create a contract
        create_response = await async_client.post(
            "/api/v1/admin/config/contracts",
            headers=auth_headers,
            json={**sample_contract_data, "code": "test-update-contract"},
        )
        contract_id = create_response.json()["id"]

        # Then update it
        response = await async_client.patch(
            f"/api/v1/admin/config/contracts/{contract_id}",
            headers=auth_headers,
            json={"name": "Updated Contract Name"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Contract Name"


class TestSystemSettingEndpoints:
    """Test system setting CRUD operations."""

    @pytest.fixture
    def sample_setting_data(self):
        return {
            "key": "test.setting",
            "value": "test_value",
            "category": "testing",
            "description": "A test setting",
            "value_type": "string",
            "is_public": False,
            "is_editable": True,
        }

    @pytest.mark.asyncio
    async def test_list_settings(self, async_client: AsyncClient, auth_headers: dict):
        """Test listing system settings."""
        response = await async_client.get(
            "/api/v1/admin/config/settings",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_create_setting(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_setting_data: dict,
    ):
        """Test creating a new system setting."""
        response = await async_client.post(
            "/api/v1/admin/config/settings",
            headers=auth_headers,
            json=sample_setting_data,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["key"] == sample_setting_data["key"]
        assert data["value"] == sample_setting_data["value"]


class TestLookupOptionEndpoints:
    """Test lookup option CRUD operations."""

    @pytest.fixture
    def sample_lookup_data(self):
        return {
            "category": "test_roles",
            "code": "test-role",
            "label": "Test Role",
            "description": "A test role",
            "is_active": True,
            "display_order": 1,
        }

    @pytest.mark.asyncio
    async def test_list_lookup_options(self, async_client: AsyncClient):
        """Test listing lookup options by category."""
        response = await async_client.get(
            "/api/v1/admin/config/lookup/roles",
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_create_lookup_option(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_lookup_data: dict,
    ):
        """Test creating a new lookup option."""
        response = await async_client.post(
            f"/api/v1/admin/config/lookup/{sample_lookup_data['category']}",
            headers=auth_headers,
            json=sample_lookup_data,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == sample_lookup_data["code"]
        assert data["label"] == sample_lookup_data["label"]


class TestFormStepEndpoints:
    """Test form step CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_step(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test creating a new step in a template."""
        # First create a template
        template_response = await async_client.post(
            "/api/v1/admin/config/templates",
            headers=auth_headers,
            json={
                "name": "Step Test Template",
                "slug": "step-test-template",
                "form_type": "incident",
            },
        )
        template_id = template_response.json()["id"]

        # Then create a step
        response = await async_client.post(
            f"/api/v1/admin/config/templates/{template_id}/steps",
            headers=auth_headers,
            json={
                "name": "New Step",
                "description": "A new step",
                "order": 0,
            },
        )
        assert response.status_code == 201
        assert response.json()["name"] == "New Step"


class TestFormFieldEndpoints:
    """Test form field CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_field(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test creating a new field in a step."""
        # First create a template with a step
        template_response = await async_client.post(
            "/api/v1/admin/config/templates",
            headers=auth_headers,
            json={
                "name": "Field Test Template",
                "slug": "field-test-template",
                "form_type": "incident",
                "steps": [
                    {"name": "Step 1", "order": 0},
                ],
            },
        )
        template_data = template_response.json()
        step_id = template_data["steps"][0]["id"]

        # Then create a field
        response = await async_client.post(
            f"/api/v1/admin/config/steps/{step_id}/fields",
            headers=auth_headers,
            json={
                "name": "new_field",
                "label": "New Field",
                "field_type": "text",
                "order": 0,
                "is_required": True,
                "width": "full",
            },
        )
        assert response.status_code == 201
        assert response.json()["name"] == "new_field"
