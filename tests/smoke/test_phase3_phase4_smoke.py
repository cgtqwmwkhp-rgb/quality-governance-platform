"""
Smoke Tests for Phase 3 & 4 Features

Quick validation tests to ensure critical paths are working:
- Workflow Center functionality
- Compliance Automation features
- API endpoint availability
- Frontend page accessibility

Requires authenticated API context (CI seeds default users via ``scripts/seed_ci_locust_users.py``).
"""

from typing import Any

import pytest
import requests


@pytest.fixture(autouse=True)
def _phase34_smoke_requires_auth(auth_headers: dict) -> None:
    if not auth_headers.get("Authorization"):
        pytest.skip(
            "Phase 3/4 smoke requires a logged-in test user "
            "(run seed_ci_locust_users or set TEST_USER_EMAIL / credentials)."
        )


class TestWorkflowCenterSmoke:
    """Smoke tests for Workflow Center (Phase 3)."""

    def test_workflow_templates_endpoint_available(self, auth_client: Any) -> None:
        """Verify workflow templates endpoint is accessible."""
        response = auth_client.get("/api/v1/workflows/templates")
        assert response.status_code == 200
        assert "templates" in response.json()

    def test_workflow_instances_endpoint_available(self, auth_client: Any) -> None:
        """Verify workflow instances endpoint is accessible."""
        response = auth_client.get("/api/v1/workflows/instances")
        assert response.status_code == 200
        assert "instances" in response.json()

    def test_pending_approvals_endpoint_available(self, auth_client: Any) -> None:
        """Verify pending approvals endpoint is accessible."""
        response = auth_client.get("/api/v1/workflows/approvals/pending")
        assert response.status_code == 200
        assert "approvals" in response.json()

    def test_delegations_endpoint_available(self, auth_client: Any) -> None:
        """Verify delegations endpoint is accessible."""
        response = auth_client.get("/api/v1/workflows/delegations")
        assert response.status_code == 200
        assert "delegations" in response.json()

    def test_workflow_stats_endpoint_available(self, auth_client: Any) -> None:
        """Verify workflow stats endpoint is accessible."""
        response = auth_client.get("/api/v1/workflows/stats")
        assert response.status_code == 200
        stats = response.json()
        assert "active_workflows" in stats
        assert "pending_approvals" in stats

    def test_can_start_workflow(self, auth_client: Any) -> None:
        """Verify workflow can be started."""
        payload = {
            "template_code": "CAPA",
            "entity_type": "action",
            "entity_id": f"SMOKE-{pytest.importorskip('time').time()}",
        }
        response = auth_client.post("/api/v1/workflows/start", json=payload)
        assert response.status_code == 200
        assert "id" in response.json()


class TestComplianceAutomationSmoke:
    """Smoke tests for Compliance Automation (Phase 4)."""

    def test_regulatory_updates_endpoint_available(self, auth_client: Any) -> None:
        """Verify regulatory updates endpoint is accessible."""
        response = auth_client.get("/api/v1/compliance-automation/regulatory-updates")
        assert response.status_code == 200
        assert "updates" in response.json()

    def test_gap_analyses_endpoint_available(self, auth_client: Any) -> None:
        """Verify gap analyses endpoint is accessible."""
        response = auth_client.get("/api/v1/compliance-automation/gap-analyses")
        assert response.status_code == 200
        assert "analyses" in response.json()

    def test_certificates_endpoint_available(self, auth_client: Any) -> None:
        """Verify certificates endpoint is accessible."""
        response = auth_client.get("/api/v1/compliance-automation/certificates")
        assert response.status_code == 200
        assert "certificates" in response.json()

    def test_certificates_summary_endpoint_available(self, auth_client: Any) -> None:
        """Verify certificate expiry summary endpoint is accessible."""
        response = auth_client.get("/api/v1/compliance-automation/certificates/expiring-summary")
        assert response.status_code == 200
        summary = response.json()
        assert "expired" in summary
        assert "expiring_30_days" in summary

    def test_scheduled_audits_endpoint_available(self, auth_client: Any) -> None:
        """Verify scheduled audits endpoint is accessible."""
        response = auth_client.get("/api/v1/compliance-automation/scheduled-audits")
        assert response.status_code == 200
        assert "audits" in response.json()

    def test_compliance_score_endpoint_available(self, auth_client: Any) -> None:
        """Verify compliance score endpoint is accessible."""
        response = auth_client.get("/api/v1/compliance-automation/score")
        assert response.status_code == 200
        score = response.json()
        assert "overall_score" in score
        assert "breakdown" in score

    def test_compliance_trend_endpoint_available(self, auth_client: Any) -> None:
        """Verify compliance trend endpoint is accessible."""
        response = auth_client.get("/api/v1/compliance-automation/score/trend")
        assert response.status_code == 200
        assert "trend" in response.json()

    def test_riddor_check_endpoint_available(self, auth_client: Any) -> None:
        """Verify RIDDOR check endpoint is accessible."""
        payload = {"injury_type": "fracture", "fatality": False}
        response = auth_client.post("/api/v1/compliance-automation/riddor/check", json=payload)
        assert response.status_code == 200
        assert "is_riddor" in response.json()


class TestFrontendPagesSmoke:
    """Smoke tests for frontend page availability."""

    @pytest.fixture
    def base_url(self) -> str:
        """Get the base URL for frontend tests."""
        import os

        return os.environ.get("FRONTEND_URL", "http://localhost:5173")

    def test_workflow_center_page_loads(self, base_url: str) -> None:
        """Verify Workflow Center page is accessible."""
        try:
            response = requests.get(f"{base_url}/workflows", timeout=10)
            assert response.status_code in [200, 302]
        except requests.exceptions.ConnectionError:
            pytest.skip("Frontend not available")

    def test_compliance_automation_page_loads(self, base_url: str) -> None:
        """Verify Compliance Automation page is accessible."""
        try:
            response = requests.get(f"{base_url}/compliance-automation", timeout=10)
            assert response.status_code in [200, 302]
        except requests.exceptions.ConnectionError:
            pytest.skip("Frontend not available")


class TestIntegrationSmoke:
    """Integration smoke tests."""

    def test_workflow_approval_flow(self, auth_client: Any) -> None:
        """Test basic workflow approval flow."""
        templates_resp = auth_client.get("/api/v1/workflows/templates")
        assert templates_resp.status_code == 200

        approvals_resp = auth_client.get("/api/v1/workflows/approvals/pending")
        assert approvals_resp.status_code == 200

        stats_resp = auth_client.get("/api/v1/workflows/stats")
        assert stats_resp.status_code == 200

    def test_compliance_monitoring_flow(self, auth_client: Any) -> None:
        """Test basic compliance monitoring flow."""
        updates_resp = auth_client.get("/api/v1/compliance-automation/regulatory-updates")
        assert updates_resp.status_code == 200

        score_resp = auth_client.get("/api/v1/compliance-automation/score")
        assert score_resp.status_code == 200

        certs_resp = auth_client.get("/api/v1/compliance-automation/certificates")
        assert certs_resp.status_code == 200

    def test_riddor_detection_flow(self, auth_client: Any) -> None:
        """Test RIDDOR detection and preparation flow."""
        check_payload = {
            "fatality": False,
            "injury_type": "fracture",
            "days_off_work": 5,
        }
        check_resp = auth_client.post("/api/v1/compliance-automation/riddor/check", json=check_payload)
        assert check_resp.status_code == 200
        result = check_resp.json()
        assert result["is_riddor"] is True

        prep_resp = auth_client.post(
            "/api/v1/compliance-automation/riddor/prepare/1",
            params={"riddor_type": "specified_injury"},
        )
        assert prep_resp.status_code == 200
        assert "submission_data" in prep_resp.json()


class TestDataIntegritySmoke:
    """Data integrity smoke tests."""

    def test_workflow_template_structure(self, auth_client: Any) -> None:
        """Verify workflow templates have required structure."""
        response = auth_client.get("/api/v1/workflows/templates")
        assert response.status_code == 200

        templates = response.json()["templates"]
        for template in templates:
            assert "code" in template
            assert "name" in template
            assert "category" in template
            assert "steps_count" in template
            assert template["steps_count"] > 0

    def test_compliance_score_structure(self, auth_client: Any) -> None:
        """Verify compliance score has required structure."""
        response = auth_client.get("/api/v1/compliance-automation/score")
        assert response.status_code == 200

        score = response.json()
        assert 0 <= score["overall_score"] <= 100
        assert "breakdown" in score
        assert isinstance(score["breakdown"], dict)

        for _standard, data in score["breakdown"].items():
            assert "score" in data
            assert 0 <= data["score"] <= 100

    def test_certificate_expiry_dates_valid(self, auth_client: Any) -> None:
        """Verify certificate expiry dates are valid."""
        response = auth_client.get("/api/v1/compliance-automation/certificates")
        assert response.status_code == 200

        certificates = response.json()["certificates"]
        for cert in certificates:
            assert "expiry_date" in cert
            assert "status" in cert
            assert cert["status"] in ["valid", "expiring_soon", "expired"]
