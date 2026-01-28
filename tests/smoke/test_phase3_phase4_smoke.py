"""
Smoke Tests for Phase 3 & 4 Features

Quick validation tests to ensure critical paths are working:
- Workflow Center functionality
- Compliance Automation features
- API endpoint availability

PHASE 5 FIX (PR #104):
- GOVPLAT-001 RESOLVED: Fixed path + async conversion
- Changed /api/workflows/* to /api/v1/workflows/*
- Changed /api/compliance-automation/* to /api/v1/compliance-automation/*
- Uses async_client + async_auth_headers from conftest.py
"""

import pytest


class TestWorkflowCenterSmoke:
    """Smoke tests for Workflow Center (Phase 3)."""

    @pytest.mark.asyncio
    async def test_workflow_templates_endpoint_available(self, async_client, async_auth_headers) -> None:
        """Verify workflow templates endpoint is accessible."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/templates", headers=async_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data

    @pytest.mark.asyncio
    async def test_workflow_instances_endpoint_available(self, async_client, async_auth_headers) -> None:
        """Verify workflow instances endpoint is accessible."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/instances", headers=async_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "instances" in data

    @pytest.mark.asyncio
    async def test_pending_approvals_endpoint_available(self, async_client, async_auth_headers) -> None:
        """Verify pending approvals endpoint is accessible."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/approvals/pending", headers=async_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "approvals" in data

    @pytest.mark.asyncio
    async def test_delegations_endpoint_available(self, async_client, async_auth_headers) -> None:
        """Verify delegations endpoint is accessible."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/delegations", headers=async_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "delegations" in data

    @pytest.mark.asyncio
    async def test_workflow_stats_endpoint_available(self, async_client, async_auth_headers) -> None:
        """Verify workflow stats endpoint is accessible."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/stats", headers=async_auth_headers)
        assert response.status_code == 200
        stats = response.json()
        assert "active_workflows" in stats
        assert "pending_approvals" in stats


class TestComplianceAutomationSmoke:
    """Smoke tests for Compliance Automation (Phase 4)."""

    @pytest.mark.asyncio
    async def test_regulatory_updates_endpoint_available(self, async_client, async_auth_headers) -> None:
        """Verify regulatory updates endpoint is accessible."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/regulatory-updates",
            headers=async_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "updates" in data

    @pytest.mark.asyncio
    async def test_gap_analyses_endpoint_available(self, async_client, async_auth_headers) -> None:
        """Verify gap analyses endpoint is accessible."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/compliance-automation/gap-analyses", headers=async_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "analyses" in data

    @pytest.mark.asyncio
    async def test_certificates_endpoint_available(self, async_client, async_auth_headers) -> None:
        """Verify certificates endpoint is accessible."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/compliance-automation/certificates", headers=async_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "certificates" in data

    @pytest.mark.asyncio
    async def test_certificates_summary_endpoint_available(self, async_client, async_auth_headers) -> None:
        """Verify certificate expiry summary endpoint is accessible."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/certificates/expiring-summary",
            headers=async_auth_headers,
        )
        assert response.status_code == 200
        summary = response.json()
        assert "expired" in summary
        assert "expiring_30_days" in summary

    @pytest.mark.asyncio
    async def test_scheduled_audits_endpoint_available(self, async_client, async_auth_headers) -> None:
        """Verify scheduled audits endpoint is accessible."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/compliance-automation/scheduled-audits", headers=async_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "audits" in data

    @pytest.mark.asyncio
    async def test_compliance_score_endpoint_available(self, async_client, async_auth_headers) -> None:
        """Verify compliance score endpoint is accessible."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/compliance-automation/score", headers=async_auth_headers)
        assert response.status_code == 200
        score = response.json()
        assert "overall_score" in score
        assert "breakdown" in score

    @pytest.mark.asyncio
    async def test_compliance_trend_endpoint_available(self, async_client, async_auth_headers) -> None:
        """Verify compliance trend endpoint is accessible."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/compliance-automation/score/trend", headers=async_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "trend" in data

    @pytest.mark.asyncio
    async def test_riddor_check_endpoint_available(self, async_client, async_auth_headers) -> None:
        """Verify RIDDOR check endpoint is accessible."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        payload = {"injury_type": "fracture", "fatality": False}
        response = await async_client.post(
            "/api/v1/compliance-automation/riddor/check",
            json=payload,
            headers=async_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_riddor" in data


class TestIntegrationSmoke:
    """Integration smoke tests."""

    @pytest.mark.asyncio
    async def test_workflow_approval_flow(self, async_client, async_auth_headers) -> None:
        """Test basic workflow approval flow."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        # 1. Get templates
        templates_resp = await async_client.get("/api/v1/workflows/templates", headers=async_auth_headers)
        assert templates_resp.status_code == 200

        # 2. Check pending approvals
        approvals_resp = await async_client.get("/api/v1/workflows/approvals/pending", headers=async_auth_headers)
        assert approvals_resp.status_code == 200

        # 3. Get stats
        stats_resp = await async_client.get("/api/v1/workflows/stats", headers=async_auth_headers)
        assert stats_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_compliance_monitoring_flow(self, async_client, async_auth_headers) -> None:
        """Test basic compliance monitoring flow."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        # 1. Check regulatory updates
        updates_resp = await async_client.get(
            "/api/v1/compliance-automation/regulatory-updates",
            headers=async_auth_headers,
        )
        assert updates_resp.status_code == 200

        # 2. Get compliance score
        score_resp = await async_client.get("/api/v1/compliance-automation/score", headers=async_auth_headers)
        assert score_resp.status_code == 200

        # 3. Check certificates
        certs_resp = await async_client.get("/api/v1/compliance-automation/certificates", headers=async_auth_headers)
        assert certs_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_riddor_detection_flow(self, async_client, async_auth_headers) -> None:
        """Test RIDDOR detection and preparation flow."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        # 1. Check if incident requires RIDDOR
        check_payload = {
            "fatality": False,
            "injury_type": "fracture",
            "days_off_work": 5,
        }
        check_resp = await async_client.post(
            "/api/v1/compliance-automation/riddor/check",
            json=check_payload,
            headers=async_auth_headers,
        )
        assert check_resp.status_code == 200
        result = check_resp.json()
        assert result["is_riddor"] is True


class TestDataIntegritySmoke:
    """Data integrity smoke tests."""

    @pytest.mark.asyncio
    async def test_workflow_template_structure(self, async_client, async_auth_headers) -> None:
        """Verify workflow templates have required structure."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/workflows/templates", headers=async_auth_headers)
        assert response.status_code == 200

        data = response.json()
        templates = data["templates"]
        for template in templates:
            assert "code" in template
            assert "name" in template
            assert "category" in template
            assert "steps_count" in template
            assert template["steps_count"] > 0

    @pytest.mark.asyncio
    async def test_compliance_score_structure(self, async_client, async_auth_headers) -> None:
        """Verify compliance score has required structure."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/compliance-automation/score", headers=async_auth_headers)
        assert response.status_code == 200

        score = response.json()
        assert 0 <= score["overall_score"] <= 100
        assert "breakdown" in score
        assert len(score["breakdown"]) > 0

        for standard, data in score["breakdown"].items():
            assert "score" in data
            assert 0 <= data["score"] <= 100

    @pytest.mark.asyncio
    async def test_certificate_expiry_dates_valid(self, async_client, async_auth_headers) -> None:
        """Verify certificate expiry dates are valid."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/compliance-automation/certificates", headers=async_auth_headers)
        assert response.status_code == 200

        data = response.json()
        certificates = data["certificates"]
        for cert in certificates:
            assert "expiry_date" in cert
            assert "status" in cert
            assert cert["status"] in ["valid", "expiring_soon", "expired"]
