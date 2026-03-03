"""End-to-End tests for Form Configuration workflow.

These tests verify the complete workflow from admin creating a form
to portal user submitting data through that form.

Run with: pytest tests/test_e2e_form_workflow.py -v
"""

import pytest
from httpx import AsyncClient


class TestAdminFormBuilderE2E:
    """E2E tests for admin form builder workflow."""

    @pytest.mark.asyncio
    async def test_complete_form_creation_workflow(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test complete workflow: create template -> add steps -> add fields -> publish."""

        # Step 1: Create a new form template
        template_response = await async_client.post(
            "/api/v1/admin/config/templates",
            headers=auth_headers,
            json={
                "name": "E2E Test Incident Form",
                "slug": "e2e-test-incident",
                "description": "Complete E2E test form",
                "form_type": "incident",
                "icon": "AlertTriangle",
                "color": "#ef4444",
                "allow_drafts": True,
                "allow_attachments": True,
                "require_signature": False,
                "auto_assign_reference": True,
                "reference_prefix": "E2E",
                "notify_on_submit": True,
            },
        )
        assert template_response.status_code == 201
        template_data = template_response.json()
        template_id = template_data["id"]
        assert template_data["is_active"] is True
        assert template_data["is_published"] is False

        # Step 2: Add first step - Contract Selection
        step1_response = await async_client.post(
            f"/api/v1/admin/config/templates/{template_id}/steps",
            headers=auth_headers,
            json={
                "name": "Contract Selection",
                "description": "Select the relevant contract",
                "order": 0,
                "icon": "Building",
            },
        )
        assert step1_response.status_code == 201
        step1_id = step1_response.json()["id"]

        # Step 3: Add field to step 1 - Contract dropdown
        field1_response = await async_client.post(
            f"/api/v1/admin/config/steps/{step1_id}/fields",
            headers=auth_headers,
            json={
                "name": "contract",
                "label": "Select Contract",
                "field_type": "select",
                "order": 0,
                "is_required": True,
                "placeholder": "Choose a contract...",
                "width": "full",
            },
        )
        assert field1_response.status_code == 201

        # Step 4: Add second step - Incident Details
        step2_response = await async_client.post(
            f"/api/v1/admin/config/templates/{template_id}/steps",
            headers=auth_headers,
            json={
                "name": "Incident Details",
                "description": "Describe what happened",
                "order": 1,
                "icon": "FileText",
            },
        )
        assert step2_response.status_code == 201
        step2_id = step2_response.json()["id"]

        # Step 5: Add multiple fields to step 2
        fields_to_add = [
            {
                "name": "title",
                "label": "Incident Title",
                "field_type": "text",
                "order": 0,
                "is_required": True,
                "placeholder": "Brief summary",
                "max_length": 200,
                "width": "full",
            },
            {
                "name": "incident_date",
                "label": "Date of Incident",
                "field_type": "date",
                "order": 1,
                "is_required": True,
                "width": "half",
            },
            {
                "name": "incident_time",
                "label": "Time of Incident",
                "field_type": "time",
                "order": 2,
                "is_required": True,
                "width": "half",
            },
            {
                "name": "location",
                "label": "Location",
                "field_type": "location",
                "order": 3,
                "is_required": True,
                "placeholder": "Where did this happen?",
                "help_text": "Use GPS button for automatic detection",
                "width": "full",
            },
            {
                "name": "description",
                "label": "Full Description",
                "field_type": "textarea",
                "order": 4,
                "is_required": True,
                "placeholder": "Describe what happened in detail...",
                "min_length": 50,
                "help_text": "Use voice input for hands-free entry",
                "width": "full",
            },
        ]

        for field_data in fields_to_add:
            response = await async_client.post(
                f"/api/v1/admin/config/steps/{step2_id}/fields",
                headers=auth_headers,
                json=field_data,
            )
            assert response.status_code == 201

        # Step 6: Add third step - Injuries
        step3_response = await async_client.post(
            f"/api/v1/admin/config/templates/{template_id}/steps",
            headers=auth_headers,
            json={
                "name": "Injuries & Evidence",
                "description": "Document any injuries and attach evidence",
                "order": 2,
                "icon": "Heart",
            },
        )
        assert step3_response.status_code == 201
        step3_id = step3_response.json()["id"]

        # Step 7: Add body map and file upload fields
        injury_fields = [
            {
                "name": "has_injuries",
                "label": "Any injuries sustained?",
                "field_type": "toggle",
                "order": 0,
                "is_required": True,
                "width": "full",
            },
            {
                "name": "injuries",
                "label": "Injury Location",
                "field_type": "body_map",
                "order": 1,
                "is_required": False,
                "help_text": "Click on body parts to mark injuries",
                "width": "full",
            },
            {
                "name": "photos",
                "label": "Evidence Photos",
                "field_type": "image",
                "order": 2,
                "is_required": False,
                "help_text": "Upload photos of the scene or injuries",
                "width": "full",
            },
        ]

        for field_data in injury_fields:
            response = await async_client.post(
                f"/api/v1/admin/config/steps/{step3_id}/fields",
                headers=auth_headers,
                json=field_data,
            )
            assert response.status_code == 201

        # Step 8: Verify the complete template
        get_response = await async_client.get(
            f"/api/v1/admin/config/templates/{template_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 200
        final_template = get_response.json()
        assert len(final_template["steps"]) == 3
        assert final_template["is_published"] is False

        # Step 9: Publish the template
        publish_response = await async_client.post(
            f"/api/v1/admin/config/templates/{template_id}/publish",
            headers=auth_headers,
        )
        assert publish_response.status_code == 200
        published_template = publish_response.json()
        assert published_template["is_published"] is True
        assert published_template["published_at"] is not None

        # Step 10: Verify public endpoint can access published template
        public_response = await async_client.get(
            f"/api/v1/admin/config/templates/by-slug/e2e-test-incident",
        )
        assert public_response.status_code == 200
        public_template = public_response.json()
        assert public_template["name"] == "E2E Test Incident Form"
        assert public_template["is_published"] is True


class TestContractManagementE2E:
    """E2E tests for contract management workflow."""

    @pytest.mark.asyncio
    async def test_complete_contract_workflow(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test complete workflow: create -> update -> list -> delete."""

        # Step 1: Create multiple contracts
        contracts_to_create = [
            {
                "name": "E2E Test Contract A",
                "code": "e2e-contract-a",
                "client_name": "Test Client A",
                "is_active": True,
                "display_order": 1,
            },
            {
                "name": "E2E Test Contract B",
                "code": "e2e-contract-b",
                "client_name": "Test Client B",
                "is_active": True,
                "display_order": 2,
            },
            {
                "name": "E2E Test Contract C",
                "code": "e2e-contract-c",
                "client_name": "Test Client C",
                "is_active": False,  # Inactive contract
                "display_order": 3,
            },
        ]

        created_ids = []
        for contract_data in contracts_to_create:
            response = await async_client.post(
                "/api/v1/admin/config/contracts",
                headers=auth_headers,
                json=contract_data,
            )
            assert response.status_code == 201
            created_ids.append(response.json()["id"])

        # Step 2: List all contracts
        list_response = await async_client.get(
            "/api/v1/admin/config/contracts",
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        all_contracts = list_response.json()
        assert all_contracts["total"] >= 3

        # Step 3: List only active contracts
        active_response = await async_client.get(
            "/api/v1/admin/config/contracts?is_active=true",
            headers=auth_headers,
        )
        assert active_response.status_code == 200

        # Step 4: Update a contract
        update_response = await async_client.patch(
            f"/api/v1/admin/config/contracts/{created_ids[0]}",
            headers=auth_headers,
            json={
                "name": "E2E Updated Contract A",
                "description": "Updated description",
            },
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "E2E Updated Contract A"

        # Step 5: Deactivate a contract
        deactivate_response = await async_client.patch(
            f"/api/v1/admin/config/contracts/{created_ids[1]}",
            headers=auth_headers,
            json={"is_active": False},
        )
        assert deactivate_response.status_code == 200
        assert deactivate_response.json()["is_active"] is False

        # Step 6: Delete a contract
        delete_response = await async_client.delete(
            f"/api/v1/admin/config/contracts/{created_ids[2]}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 204


class TestLookupOptionsE2E:
    """E2E tests for lookup options workflow."""

    @pytest.mark.asyncio
    async def test_complete_lookup_workflow(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test complete workflow for managing lookup options."""

        # Step 1: Create lookup options for a new category
        options_to_create = [
            {
                "category": "e2e_test_category",
                "code": "option-1",
                "label": "Option One",
                "description": "First option",
                "is_active": True,
                "display_order": 1,
            },
            {
                "category": "e2e_test_category",
                "code": "option-2",
                "label": "Option Two",
                "description": "Second option",
                "is_active": True,
                "display_order": 2,
            },
        ]

        created_ids = []
        for option_data in options_to_create:
            response = await async_client.post(
                f"/api/v1/admin/config/lookup/{option_data['category']}",
                headers=auth_headers,
                json=option_data,
            )
            assert response.status_code == 201
            created_ids.append(response.json()["id"])

        # Step 2: List options by category
        list_response = await async_client.get(
            "/api/v1/admin/config/lookup/e2e_test_category",
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 2

        # Step 3: Update an option
        update_response = await async_client.patch(
            f"/api/v1/admin/config/lookup/e2e_test_category/{created_ids[0]}",
            headers=auth_headers,
            json={"label": "Updated Option One"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["label"] == "Updated Option One"

        # Step 4: Deactivate an option
        deactivate_response = await async_client.patch(
            f"/api/v1/admin/config/lookup/e2e_test_category/{created_ids[1]}",
            headers=auth_headers,
            json={"is_active": False},
        )
        assert deactivate_response.status_code == 200
        assert deactivate_response.json()["is_active"] is False

        # Step 5: List only active options
        active_response = await async_client.get(
            "/api/v1/admin/config/lookup/e2e_test_category?is_active=true",
        )
        assert active_response.status_code == 200
        assert active_response.json()["total"] == 1


class TestSystemSettingsE2E:
    """E2E tests for system settings workflow."""

    @pytest.mark.asyncio
    async def test_complete_settings_workflow(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test complete workflow for managing system settings."""

        # Step 1: Create settings
        settings_to_create = [
            {
                "key": "e2e.test.company_name",
                "value": "E2E Test Company",
                "category": "branding",
                "description": "Company name for testing",
                "value_type": "string",
                "is_public": True,
                "is_editable": True,
            },
            {
                "key": "e2e.test.sla_hours",
                "value": "48",
                "category": "workflow",
                "description": "SLA hours for testing",
                "value_type": "number",
                "is_public": False,
                "is_editable": True,
            },
        ]

        for setting_data in settings_to_create:
            response = await async_client.post(
                "/api/v1/admin/config/settings",
                headers=auth_headers,
                json=setting_data,
            )
            assert response.status_code == 201

        # Step 2: List all settings
        list_response = await async_client.get(
            "/api/v1/admin/config/settings",
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] >= 2

        # Step 3: List settings by category
        category_response = await async_client.get(
            "/api/v1/admin/config/settings?category=branding",
            headers=auth_headers,
        )
        assert category_response.status_code == 200

        # Step 4: Update a setting
        update_response = await async_client.patch(
            "/api/v1/admin/config/settings/e2e.test.company_name",
            headers=auth_headers,
            json={"value": "Updated E2E Company"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["value"] == "Updated E2E Company"


class TestFormFieldTypesE2E:
    """E2E tests for all supported field types."""

    @pytest.mark.asyncio
    async def test_all_field_types(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test creating a form with all supported field types."""

        # Create a template for testing all field types
        template_response = await async_client.post(
            "/api/v1/admin/config/templates",
            headers=auth_headers,
            json={
                "name": "All Field Types Test",
                "slug": "all-field-types-test",
                "form_type": "test",
            },
        )
        assert template_response.status_code == 201
        template_id = template_response.json()["id"]

        # Create a step
        step_response = await async_client.post(
            f"/api/v1/admin/config/templates/{template_id}/steps",
            headers=auth_headers,
            json={"name": "All Fields", "order": 0},
        )
        assert step_response.status_code == 201
        step_id = step_response.json()["id"]

        # All supported field types
        field_types = [
            {"name": "text_field", "field_type": "text", "label": "Text"},
            {"name": "textarea_field", "field_type": "textarea", "label": "Textarea"},
            {"name": "number_field", "field_type": "number", "label": "Number"},
            {"name": "email_field", "field_type": "email", "label": "Email"},
            {"name": "phone_field", "field_type": "phone", "label": "Phone"},
            {"name": "date_field", "field_type": "date", "label": "Date"},
            {"name": "time_field", "field_type": "time", "label": "Time"},
            {"name": "datetime_field", "field_type": "datetime", "label": "DateTime"},
            {
                "name": "select_field",
                "field_type": "select",
                "label": "Select",
                "options": [{"value": "a", "label": "A"}],
            },
            {
                "name": "multi_select_field",
                "field_type": "multi_select",
                "label": "Multi Select",
            },
            {"name": "radio_field", "field_type": "radio", "label": "Radio"},
            {"name": "checkbox_field", "field_type": "checkbox", "label": "Checkbox"},
            {"name": "toggle_field", "field_type": "toggle", "label": "Toggle"},
            {"name": "file_field", "field_type": "file", "label": "File Upload"},
            {"name": "image_field", "field_type": "image", "label": "Image Upload"},
            {
                "name": "signature_field",
                "field_type": "signature",
                "label": "Signature",
            },
            {"name": "location_field", "field_type": "location", "label": "Location"},
            {"name": "body_map_field", "field_type": "body_map", "label": "Body Map"},
            {"name": "rating_field", "field_type": "rating", "label": "Rating"},
            {
                "name": "heading_field",
                "field_type": "heading",
                "label": "Section Heading",
            },
            {
                "name": "paragraph_field",
                "field_type": "paragraph",
                "label": "Info text",
            },
            {"name": "divider_field", "field_type": "divider", "label": "---"},
        ]

        for order, field_data in enumerate(field_types):
            response = await async_client.post(
                f"/api/v1/admin/config/steps/{step_id}/fields",
                headers=auth_headers,
                json={
                    **field_data,
                    "order": order,
                    "is_required": False,
                    "width": "full",
                },
            )
            assert (
                response.status_code == 201
            ), f"Failed to create field type: {field_data['field_type']}"

        # Verify all fields were created
        get_response = await async_client.get(
            f"/api/v1/admin/config/templates/{template_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 200
        template_data = get_response.json()
        assert len(template_data["steps"][0]["fields"]) == len(field_types)
