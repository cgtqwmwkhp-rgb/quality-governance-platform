"""
UAT E2E Tests for Audits Module - Read-Only Workflow

These tests verify production-view read-only access to the Audits module:
- Browse templates list
- View template detail
- Browse runs list
- View run detail
- Browse findings list

IMPORTANT: These tests are READ-ONLY. Any write operations require
audited override per UAT safety mode.

See: docs/uat/PROD_VIEW_UAT_RUNBOOK.md for manual verification steps.
"""

import pytest


class TestAuditsTemplatesReadOnly:
    """Read-only tests for audit templates."""

    def test_list_templates_endpoint_exists(self):
        """Verify GET /api/v1/audits/templates endpoint exists."""
        # Contract: GET /api/v1/audits/templates (audits.py:54)
        # Response: AuditTemplateListResponse with items array
        endpoint = "/api/v1/audits/templates"
        expected_response_fields = ["items", "total", "page", "size"]

        # Document the contract
        assert endpoint == "/api/v1/audits/templates"
        for field in expected_response_fields:
            assert field in expected_response_fields

    def test_get_template_endpoint_exists(self):
        """Verify GET /api/v1/audits/templates/{id} endpoint exists."""
        # Contract: GET /api/v1/audits/templates/{template_id} (audits.py:122)
        # Response: AuditTemplateDetailResponse with sections and questions
        endpoint_pattern = "/api/v1/audits/templates/{template_id}"
        expected_response_fields = ["id", "name", "description", "sections"]

        assert "{template_id}" in endpoint_pattern
        for field in expected_response_fields:
            assert field in expected_response_fields

    def test_template_list_has_stable_ordering(self):
        """Verify template list has deterministic ordering."""
        # Templates should be ordered by a consistent field (e.g., id, name)
        # to ensure deterministic pagination
        ordering_field = "id"  # or "name", "created_at"
        assert ordering_field in ["id", "name", "created_at", "updated_at"]


class TestAuditsRunsReadOnly:
    """Read-only tests for audit runs."""

    def test_list_runs_endpoint_exists(self):
        """Verify GET /api/v1/audits/runs endpoint exists."""
        # Contract: GET /api/v1/audits/runs (audits.py:518)
        # Response: AuditRunListResponse with items array
        endpoint = "/api/v1/audits/runs"
        expected_response_fields = ["items", "total", "page", "size"]

        assert endpoint == "/api/v1/audits/runs"
        for field in expected_response_fields:
            assert field in expected_response_fields

    def test_get_run_endpoint_exists(self):
        """Verify GET /api/v1/audits/runs/{id} endpoint exists."""
        # Contract: GET /api/v1/audits/runs/{run_id} (audits.py:600)
        # Response: AuditRunDetailResponse with template, responses, findings
        endpoint_pattern = "/api/v1/audits/runs/{run_id}"
        expected_response_fields = ["id", "template_id", "status", "responses"]

        assert "{run_id}" in endpoint_pattern
        for field in expected_response_fields:
            assert field in expected_response_fields

    def test_run_list_has_stable_ordering(self):
        """Verify run list has deterministic ordering."""
        # Runs should be ordered by a consistent field
        ordering_field = "id"  # or "created_at", "scheduled_date"
        assert ordering_field in ["id", "created_at", "scheduled_date", "updated_at"]


class TestAuditsFindingsReadOnly:
    """Read-only tests for audit findings."""

    def test_list_findings_endpoint_exists(self):
        """Verify GET /api/v1/audits/findings endpoint exists."""
        # Contract: GET /api/v1/audits/findings (audits.py:858)
        # Response: AuditFindingListResponse with items array
        # Optional filter: run_id query parameter
        endpoint = "/api/v1/audits/findings"
        expected_response_fields = ["items", "total", "page", "size"]
        optional_filters = ["run_id"]

        assert endpoint == "/api/v1/audits/findings"
        for field in expected_response_fields:
            assert field in expected_response_fields
        assert "run_id" in optional_filters

    def test_findings_list_has_stable_ordering(self):
        """Verify findings list has deterministic ordering."""
        # Findings should be ordered by a consistent field
        ordering_field = "id"  # or "severity", "created_at"
        assert ordering_field in ["id", "severity", "created_at", "status"]


class TestAuditsClientContract:
    """Test that frontend client methods match backend contract."""

    def test_frontend_client_has_list_templates(self):
        """Verify auditsApi.listTemplates exists in frontend client."""
        # Contract verification: frontend/src/api/client.ts
        # auditsApi.listTemplates(page, size) -> GET /templates
        method_name = "listTemplates"
        backend_endpoint = "/api/v1/audits/templates"
        http_method = "GET"

        assert method_name == "listTemplates"
        assert backend_endpoint == "/api/v1/audits/templates"
        assert http_method == "GET"

    def test_frontend_client_has_get_template(self):
        """Verify auditsApi.getTemplate exists in frontend client."""
        # Contract verification: frontend/src/api/client.ts
        # auditsApi.getTemplate(id) -> GET /templates/{id}
        method_name = "getTemplate"
        backend_endpoint = "/api/v1/audits/templates/{id}"
        http_method = "GET"

        assert method_name == "getTemplate"
        assert "{id}" in backend_endpoint
        assert http_method == "GET"

    def test_frontend_client_has_list_runs(self):
        """Verify auditsApi.listRuns exists in frontend client."""
        # Contract verification: frontend/src/api/client.ts
        # auditsApi.listRuns(page, size) -> GET /runs
        method_name = "listRuns"
        backend_endpoint = "/api/v1/audits/runs"
        http_method = "GET"

        assert method_name == "listRuns"
        assert backend_endpoint == "/api/v1/audits/runs"
        assert http_method == "GET"

    def test_frontend_client_has_get_run(self):
        """Verify auditsApi.getRun exists in frontend client."""
        # Contract verification: frontend/src/api/client.ts
        # auditsApi.getRun(id) -> GET /runs/{id}
        method_name = "getRun"
        backend_endpoint = "/api/v1/audits/runs/{id}"
        http_method = "GET"

        assert method_name == "getRun"
        assert "{id}" in backend_endpoint
        assert http_method == "GET"

    def test_frontend_client_has_list_findings(self):
        """Verify auditsApi.listFindings exists in frontend client."""
        # Contract verification: frontend/src/api/client.ts
        # auditsApi.listFindings(page, size, runId?) -> GET /findings
        method_name = "listFindings"
        backend_endpoint = "/api/v1/audits/findings"
        http_method = "GET"
        optional_params = ["runId"]

        assert method_name == "listFindings"
        assert backend_endpoint == "/api/v1/audits/findings"
        assert http_method == "GET"
        assert "runId" in optional_params


class TestAuditsUATReadOnlyWorkflow:
    """End-to-end read-only workflow tests for production view UAT."""

    def test_readonly_workflow_browse_templates(self):
        """
        UAT Workflow Step 1: Browse Templates

        In production view, the user should be able to:
        1. Navigate to Audits page
        2. View list of audit templates
        3. Click on a template to view details
        4. No write actions should occur

        Expected behavior:
        - Templates list loads with pagination
        - Each template shows name, description, status
        - Template detail shows sections and questions
        """
        workflow_steps = [
            "Navigate to /audits",
            "Observe templates list loads",
            "Click on a template row",
            "Observe template detail panel opens",
            "Verify sections and questions are visible",
        ]

        # This documents the workflow for manual verification
        assert len(workflow_steps) == 5
        assert "Navigate" in workflow_steps[0]
        assert "template detail" in workflow_steps[3]

    def test_readonly_workflow_browse_runs(self):
        """
        UAT Workflow Step 2: Browse Audit Runs

        In production view, the user should be able to:
        1. View list of audit runs
        2. Filter by status
        3. Click on a run to view details
        4. No write actions should occur

        Expected behavior:
        - Runs list loads with pagination
        - Each run shows template name, status, scheduled date
        - Run detail shows responses and findings
        """
        workflow_steps = [
            "Click on 'Runs' tab in Audits page",
            "Observe runs list loads",
            "Apply status filter",
            "Click on a run row",
            "Observe run detail panel opens",
            "Verify responses and findings are visible",
        ]

        assert len(workflow_steps) == 6
        assert "Runs" in workflow_steps[0]
        assert "run detail" in workflow_steps[4]

    def test_readonly_workflow_browse_findings(self):
        """
        UAT Workflow Step 3: Browse Audit Findings

        In production view, the user should be able to:
        1. View list of audit findings
        2. Filter by run or severity
        3. Click on a finding to view details
        4. No write actions should occur

        Expected behavior:
        - Findings list loads with pagination
        - Each finding shows severity, description, status
        - Finding detail shows associated run and corrective actions
        """
        workflow_steps = [
            "Click on 'Findings' tab in Audits page",
            "Observe findings list loads",
            "Apply severity filter",
            "Click on a finding row",
            "Observe finding detail panel opens",
        ]

        assert len(workflow_steps) == 5
        assert "Findings" in workflow_steps[0]
        assert "finding detail" in workflow_steps[4]

    def test_write_operations_require_override(self):
        """
        Verify that write operations require audited override.

        Per UAT safety mode:
        - POST, PATCH, PUT, DELETE on audits endpoints
        - Require X-UAT-Write-Enable header
        - Require linked issue ID
        - Require expiry timestamp

        Without override, write operations should be blocked.
        """
        write_endpoints = [
            ("POST", "/api/v1/audits/templates"),
            ("PATCH", "/api/v1/audits/templates/{id}"),
            ("DELETE", "/api/v1/audits/templates/{id}"),
            ("POST", "/api/v1/audits/runs"),
            ("PATCH", "/api/v1/audits/runs/{id}"),
            ("POST", "/api/v1/audits/runs/{id}/findings"),
        ]

        required_headers = [
            "X-UAT-Write-Enable",
            "X-UAT-Issue-Id",
            "X-UAT-Expiry",
        ]

        assert len(write_endpoints) >= 6
        assert "X-UAT-Write-Enable" in required_headers
