"""
E2E Tests for Workflow Automation (Phase 3)

Tests cover:
- Workflow template management
- Workflow instance creation and tracking
- Approval chain processing
- Delegation management
- Escalation detection

PHASE 5 FIX (PR #104):
- GOVPLAT-001 RESOLVED: Fixed path + async conversion
- Changed /api/workflows/* to /api/v1/workflows/*
- Uses async_client + async_auth_headers from conftest.py
"""

from datetime import datetime, timedelta

import pytest


class TestWorkflowTemplates:
    """Test workflow template operations."""

    @pytest.mark.asyncio
    async def test_list_workflow_templates(self, async_client, async_auth_headers) -> None:
        """Test listing available workflow templates."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/templates", headers=async_auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "templates" in data
        templates = data["templates"]

        # Should have built-in templates
        assert len(templates) >= 3

        # Verify template structure
        template_codes = [t["code"] for t in templates]
        assert "RIDDOR" in template_codes
        assert "CAPA" in template_codes

    @pytest.mark.asyncio
    async def test_get_workflow_template_details(self, async_client, async_auth_headers) -> None:
        """Test getting detailed template information."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/templates/RIDDOR", headers=async_auth_headers)
        assert response.status_code == 200

        template = response.json()
        assert template["code"] == "RIDDOR"
        assert "name" in template
        assert "steps" in template

    @pytest.mark.asyncio
    async def test_get_nonexistent_template(self, async_client, async_auth_headers) -> None:
        """Test getting a template that doesn't exist."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/templates/NONEXISTENT", headers=async_auth_headers)
        assert response.status_code == 404


class TestWorkflowInstances:
    """Test workflow instance operations."""

    @pytest.mark.asyncio
    async def test_start_workflow(self, async_client, async_auth_headers) -> None:
        """Test starting a new workflow instance."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        payload = {
            "template_code": "CAPA",
            "entity_type": "action",
            "entity_id": "ACT-TEST-001",
            "context": {"description": "Test corrective action"},
            "priority": "high",
        }

        response = await async_client.post("/api/v1/workflows/start", json=payload, headers=async_auth_headers)
        assert response.status_code == 200

        instance = response.json()
        assert "id" in instance
        assert instance["template_code"] == "CAPA"
        assert instance["status"] in ["in_progress", "awaiting_approval", "pending"]

    @pytest.mark.asyncio
    async def test_start_workflow_invalid_template(self, async_client, async_auth_headers) -> None:
        """Test starting workflow with invalid template."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        payload = {
            "template_code": "INVALID",
            "entity_type": "action",
            "entity_id": "ACT-TEST-002",
        }

        response = await async_client.post("/api/v1/workflows/start", json=payload, headers=async_auth_headers)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_workflow_instances(self, async_client, async_auth_headers) -> None:
        """Test listing workflow instances."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/instances", headers=async_auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "instances" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_filter_workflow_instances_by_status(self, async_client, async_auth_headers) -> None:
        """Test filtering workflows by status."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/instances?status=in_progress", headers=async_auth_headers)
        assert response.status_code == 200

        data = response.json()
        for instance in data.get("instances", []):
            assert instance["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_get_workflow_instance_details(self, async_client, async_auth_headers) -> None:
        """Test getting workflow instance details."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/instances/WF-20260119001", headers=async_auth_headers)
        assert response.status_code == 200

        instance = response.json()
        assert "id" in instance
        assert "steps" in instance
        assert "history" in instance


class TestApprovals:
    """Test approval management."""

    @pytest.mark.asyncio
    async def test_get_pending_approvals(self, async_client, async_auth_headers) -> None:
        """Test getting pending approvals for current user."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/approvals/pending", headers=async_auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "approvals" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_approve_request(self, async_client, async_auth_headers) -> None:
        """Test approving a request."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        payload = {"notes": "Approved after review"}

        response = await async_client.post(
            "/api/v1/workflows/approvals/APR-001/approve",
            json=payload,
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        result = response.json()
        assert result["status"] == "approved"

    @pytest.mark.asyncio
    async def test_reject_request_requires_reason(self, async_client, async_auth_headers) -> None:
        """Test that rejection requires a reason."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        payload = {"notes": "Some notes but no reason"}

        response = await async_client.post(
            "/api/v1/workflows/approvals/APR-002/reject",
            json=payload,
            headers=async_auth_headers,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_reject_request_with_reason(self, async_client, async_auth_headers) -> None:
        """Test rejecting a request with valid reason."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        payload = {"reason": "Insufficient documentation provided"}

        response = await async_client.post(
            "/api/v1/workflows/approvals/APR-002/reject",
            json=payload,
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        result = response.json()
        assert result["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_bulk_approve(self, async_client, async_auth_headers) -> None:
        """Test bulk approval of multiple requests."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        payload = {
            "approval_ids": ["APR-001", "APR-002", "APR-003"],
            "notes": "Bulk approved after batch review",
        }

        response = await async_client.post(
            "/api/v1/workflows/approvals/bulk-approve",
            json=payload,
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        result = response.json()
        assert result["processed"] == 3
        assert result["successful"] >= 0


class TestDelegation:
    """Test out-of-office delegation."""

    @pytest.mark.asyncio
    async def test_get_delegations(self, async_client, async_auth_headers) -> None:
        """Test getting current delegations."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/delegations", headers=async_auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "delegations" in data

    @pytest.mark.asyncio
    async def test_set_delegation(self, async_client, async_auth_headers) -> None:
        """Test setting up a delegation."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        payload = {
            "delegate_id": 5,
            "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            "reason": "Annual leave",
        }

        response = await async_client.post("/api/v1/workflows/delegations", json=payload, headers=async_auth_headers)
        assert response.status_code == 200

        result = response.json()
        assert "id" in result
        assert result["delegate_id"] == 5
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_cancel_delegation(self, async_client, async_auth_headers) -> None:
        """Test cancelling a delegation."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.delete("/api/v1/workflows/delegations/DEL-001", headers=async_auth_headers)
        assert response.status_code == 200

        result = response.json()
        assert result["status"] == "cancelled"


class TestEscalation:
    """Test escalation features."""

    @pytest.mark.asyncio
    async def test_get_pending_escalations(self, async_client, async_auth_headers) -> None:
        """Test getting workflows pending escalation."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/escalations/pending", headers=async_auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "escalations" in data

    @pytest.mark.asyncio
    async def test_escalate_workflow(self, async_client, async_auth_headers) -> None:
        """Test escalating a workflow."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        payload = {
            "escalate_to": 10,
            "reason": "SLA breach - requires immediate attention",
            "new_priority": "critical",
        }

        response = await async_client.post(
            "/api/v1/workflows/instances/WF-001/escalate",
            json=payload,
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        result = response.json()
        assert result["new_priority"] == "critical"


class TestWorkflowStats:
    """Test workflow statistics."""

    @pytest.mark.asyncio
    async def test_get_workflow_stats(self, async_client, async_auth_headers) -> None:
        """Test getting workflow statistics."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/stats", headers=async_auth_headers)
        assert response.status_code == 200

        stats = response.json()
        assert "active_workflows" in stats
        assert "pending_approvals" in stats
        assert "overdue" in stats
        assert "sla_compliance_rate" in stats
        assert "by_template" in stats
