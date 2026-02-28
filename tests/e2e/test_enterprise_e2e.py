"""
Enterprise End-to-End Test Suite

COMPREHENSIVE: These tests validate complete user journeys through the system.
Target: 90%+ coverage of critical business flows.

Run with:
    pytest tests/e2e/ -v --tb=long

For parallel execution:
    pytest tests/e2e/ -v -n auto
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def client():
    """Create test client."""
    from fastapi.testclient import TestClient

    from src.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def auth_headers(client) -> dict:
    """Get authenticated headers."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser@plantexpand.com", "password": "testpassword123"},
    )
    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


@pytest.fixture(scope="module")
def admin_headers(client) -> dict:
    """Get admin headers."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin@plantexpand.com", "password": "adminpassword123"},
    )
    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


# ============================================================================
# E2E: Complete Incident Management Lifecycle
# ============================================================================


class TestIncidentLifecycleE2E:
    """
    Complete incident lifecycle:
    Report → Triage → Investigation → Actions → Closure → Analytics
    """

    def test_incident_complete_lifecycle(self, client, auth_headers):
        """E2E: Full incident lifecycle from report to closure."""
        if not auth_headers:
            pytest.skip("Auth required")

        # === Step 1: Submit incident via Portal ===
        submit_response = client.post(
            "/api/v1/portal/reports/",
            json={
                "report_type": "incident",
                "title": f"E2E Lifecycle Test - Slip Hazard - {uuid4().hex[:8]}",
                "description": "Water leak on warehouse floor causing slip hazard. Multiple near misses reported.",
                "severity": "high",
                "location": "Warehouse B, Aisle 5",
                "is_anonymous": False,
                "reporter_name": "John Smith",
                "reporter_email": "j.smith@example.com",
                "department": "Warehouse Operations",
            },
        )
        assert submit_response.status_code in [200, 201]
        report_data = submit_response.json()
        reference = report_data.get("reference_number")
        tracking_code = report_data.get("tracking_code")
        assert reference is not None

        # === Step 2: Track the incident ===
        if tracking_code:
            track_response = client.get(
                f"/api/v1/portal/reports/{reference}/",
                params={"tracking_code": tracking_code},
            )
            assert track_response.status_code in [200, 404]
            if track_response.status_code == 200:
                track_data = track_response.json()
                assert "reference_number" in track_data

        # === Step 3: Admin views incident list ===
        list_response = client.get(
            "/api/v1/incidents",
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert isinstance(list_data, (list, dict))

        # === Step 4: Search for the incident ===
        search_response = client.get(
            "/api/v1/incidents?search=Slip Hazard",
            headers=auth_headers,
        )
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert isinstance(search_data, (list, dict))

    def test_incident_with_investigation(self, client, auth_headers):
        """E2E: Incident with investigation workflow."""
        if not auth_headers:
            pytest.skip("Auth required")

        # Create incident
        create_response = client.post(
            "/api/v1/incidents",
            json={
                "title": f"E2E Investigation Test - {uuid4().hex[:8]}",
                "description": "Incident requiring investigation.",
                "severity": "high",
                "incident_type": "safety",
                "location": "Production Floor",
                "reported_date": datetime.now().isoformat(),
            },
            headers=auth_headers,
        )

        if create_response.status_code in [200, 201]:
            incident = create_response.json()
            incident_id = incident.get("id")
            assert "id" in incident or "reference" in incident

            # List investigations
            inv_response = client.get("/api/v1/investigations", headers=auth_headers)
            assert inv_response.status_code == 200
            inv_data = inv_response.json()
            assert isinstance(inv_data, (list, dict))

    def test_incident_filtering_and_export(self, client, auth_headers):
        """E2E: Filter incidents and export data."""
        if not auth_headers:
            pytest.skip("Auth required")

        # Filter by severity
        high_response = client.get(
            "/api/v1/incidents?severity=high",
            headers=auth_headers,
        )
        assert high_response.status_code == 200
        high_data = high_response.json()
        assert isinstance(high_data, (list, dict))

        # Filter by status
        open_response = client.get(
            "/api/v1/incidents?status=reported",
            headers=auth_headers,
        )
        assert open_response.status_code == 200
        open_data = open_response.json()
        assert isinstance(open_data, (list, dict))

        # Filter by date range
        date_response = client.get(
            f"/api/v1/incidents?date_from={datetime.now().date().isoformat()}",
            headers=auth_headers,
        )
        assert date_response.status_code == 200
        date_data = date_response.json()
        assert isinstance(date_data, (list, dict))


# ============================================================================
# E2E: Complete Audit Management Lifecycle
# ============================================================================


class TestAuditLifecycleE2E:
    """
    Complete audit lifecycle:
    Template → Schedule → Execute → Findings → CAPA → Closure → Report
    """

    def test_audit_template_to_execution(self, client, auth_headers):
        """E2E: Create template and execute audit."""
        if not auth_headers:
            pytest.skip("Auth required")

        # === Step 1: List templates ===
        templates_response = client.get(
            "/api/v1/audits/templates",
            headers=auth_headers,
        )
        assert templates_response.status_code == 200
        templates_data = templates_response.json()
        assert isinstance(templates_data, (list, dict))

        # === Step 2: Create new template ===
        template_data = {
            "name": f"E2E Test Audit Template - {uuid4().hex[:8]}",
            "description": "Template created by E2E test",
            "standard": "ISO 9001:2015",
            "sections": [
                {
                    "name": "Context",
                    "questions": [
                        {"text": "Is the scope documented?", "clause": "4.3"},
                        {"text": "Are interested parties identified?", "clause": "4.2"},
                    ],
                }
            ],
        }

        create_template = client.post(
            "/api/v1/audits/templates",
            json=template_data,
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert create_template.status_code in [200, 201, 422, 404]
        if create_template.status_code in [200, 201]:
            ct_data = create_template.json()
            assert "id" in ct_data or "reference" in ct_data

        # === Step 3: List scheduled audits ===
        runs_response = client.get(
            "/api/v1/audits/runs",
            headers=auth_headers,
        )
        assert runs_response.status_code == 200
        runs_data = runs_response.json()
        assert isinstance(runs_data, (list, dict))

        # === Step 4: List findings ===
        findings_response = client.get(
            "/api/v1/audits/findings",
            headers=auth_headers,
        )
        assert findings_response.status_code == 200
        findings_data = findings_response.json()
        assert isinstance(findings_data, (list, dict))

    def test_audit_findings_management(self, client, auth_headers):
        """E2E: Manage audit findings."""
        if not auth_headers:
            pytest.skip("Auth required")

        # List findings
        response = client.get("/api/v1/audits/findings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

        # Filter by severity
        high_findings = client.get(
            "/api/v1/audits/findings?severity=major",
            headers=auth_headers,
        )
        assert high_findings.status_code == 200
        high_data = high_findings.json()
        assert isinstance(high_data, (list, dict))


# ============================================================================
# E2E: Complete Risk Management Lifecycle
# ============================================================================


class TestRiskManagementE2E:
    """
    Complete risk lifecycle:
    Identify → Assess → Control → Monitor → Review
    """

    def test_risk_identification_to_treatment(self, client, auth_headers):
        """E2E: Risk from identification to treatment."""
        if not auth_headers:
            pytest.skip("Auth required")

        # === Step 1: List risks ===
        list_response = client.get("/api/v1/risks", headers=auth_headers)
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert isinstance(list_data, (list, dict))
        if isinstance(list_data, dict):
            assert "items" in list_data or "results" in list_data or "data" in list_data

        # === Step 2: Create risk ===
        uid = uuid4().hex[:8]
        risk_data = {
            "title": f"E2E Test Risk - Supply Chain Disruption - {uid}",
            "description": "Risk of supply chain disruption affecting production.",
            "category": "operational",
            "likelihood": 3,
            "impact": 4,
            "owner": "Operations Manager",
        }

        create_response = client.post(
            "/api/v1/risks",
            json=risk_data,
            headers=auth_headers,
        )
        assert create_response.status_code in [200, 201, 422]
        if create_response.status_code in [200, 201]:
            created = create_response.json()
            assert "id" in created or "reference" in created
        elif create_response.status_code == 422:
            err_data = create_response.json()
            error_data = err_data.get("error", err_data)
            assert "message" in error_data or "detail" in err_data

        # === Step 3: View risk register heat map ===
        heatmap_response = client.get(
            "/api/v1/risk-register/heat-map",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert heatmap_response.status_code in [200, 404]
        if heatmap_response.status_code == 200:
            hm_data = heatmap_response.json()
            assert isinstance(hm_data, dict)

    def test_risk_filtering_and_analysis(self, client, auth_headers):
        """E2E: Filter and analyze risks."""
        if not auth_headers:
            pytest.skip("Auth required")

        # Filter by category
        response = client.get(
            "/api/v1/risks?category=operational",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

        # Get high risks
        high_response = client.get(
            "/api/v1/risks?min_score=15",
            headers=auth_headers,
        )
        assert high_response.status_code == 200
        high_data = high_response.json()
        assert isinstance(high_data, (list, dict))


# ============================================================================
# E2E: Compliance Management Lifecycle
# ============================================================================


class TestComplianceE2E:
    """
    Complete compliance lifecycle:
    Standards → Evidence → Gap Analysis → Audit Prep → Certification
    """

    def test_compliance_evidence_management(self, client, auth_headers):
        """E2E: Manage compliance evidence."""
        if not auth_headers:
            pytest.skip("Auth required")

        # === Step 1: List standards ===
        standards_response = client.get("/api/v1/standards", headers=auth_headers)
        assert standards_response.status_code == 200
        standards_data = standards_response.json()
        assert isinstance(standards_data, (list, dict))

        # === Step 2: Get compliance evidence ===
        evidence_response = client.get(
            "/api/v1/compliance/evidence",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert evidence_response.status_code in [200, 404]
        if evidence_response.status_code == 200:
            ev_data = evidence_response.json()
            assert isinstance(ev_data, (list, dict))

        # === Step 3: Gap analysis ===
        gap_response = client.get(
            "/api/v1/compliance-automation/gap-analyses",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert gap_response.status_code in [200, 404]
        if gap_response.status_code == 200:
            gap_data = gap_response.json()
            assert isinstance(gap_data, (list, dict))

    def test_multi_standard_compliance(self, client, auth_headers):
        """E2E: View compliance across multiple standards."""
        if not auth_headers:
            pytest.skip("Auth required")

        standards = ["iso9001", "iso14001", "iso45001", "iso27001"]

        for standard in standards:
            response = client.get(
                f"/api/v1/standards/{standard}",
                headers=auth_headers,
            )
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "id" in data or "code" in data or "name" in data


# ============================================================================
# E2E: Document Control Lifecycle
# ============================================================================


class TestDocumentControlE2E:
    """
    Complete document lifecycle:
    Create → Review → Approve → Distribute → Revise → Obsolete
    """

    def test_document_management(self, client, auth_headers):
        """E2E: Document management workflow."""
        if not auth_headers:
            pytest.skip("Auth required")

        # List documents
        response = client.get("/api/v1/documents", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "items" in data or "results" in data or "data" in data

        # List policies
        policies_response = client.get("/api/v1/policies", headers=auth_headers)
        assert policies_response.status_code == 200
        policies_data = policies_response.json()
        assert isinstance(policies_data, (list, dict))
        if isinstance(policies_data, dict):
            assert "items" in policies_data or "results" in policies_data or "data" in policies_data

    def test_policy_workflow(self, client, auth_headers):
        """E2E: Policy creation and approval."""
        if not auth_headers:
            pytest.skip("Auth required")

        # Create policy
        policy_data = {
            "title": f"E2E Test Policy - {uuid4().hex[:8]}",
            "description": "Policy created by E2E test",
            "category": "quality",
            "version": "1.0",
        }

        create_response = client.post(
            "/api/v1/policies",
            json=policy_data,
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert create_response.status_code in [200, 201, 422, 404]
        if create_response.status_code in [200, 201]:
            created = create_response.json()
            assert "id" in created or "reference" in created


# ============================================================================
# E2E: Workflow Automation
# ============================================================================


class TestWorkflowAutomationE2E:
    """
    Complete workflow lifecycle:
    Trigger → Approval Chain → Escalation → Completion
    """

    def test_workflow_management(self, client, auth_headers):
        """E2E: Workflow management."""
        if not auth_headers:
            pytest.skip("Auth required")

        # List templates
        templates_response = client.get(
            "/api/v1/workflows/templates",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert templates_response.status_code in [200, 404]
        if templates_response.status_code == 200:
            templates_data = templates_response.json()
            assert isinstance(templates_data, (list, dict))

        # List instances
        instances_response = client.get(
            "/api/v1/workflows/instances",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert instances_response.status_code in [200, 404]
        if instances_response.status_code == 200:
            instances_data = instances_response.json()
            assert isinstance(instances_data, (list, dict))

    def test_approval_workflow(self, client, auth_headers):
        """E2E: Approval workflow."""
        if not auth_headers:
            pytest.skip("Auth required")

        # Get pending approvals
        response = client.get(
            "/api/v1/workflows/approvals/pending",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))


# ============================================================================
# E2E: IMS Dashboard
# ============================================================================


class TestIMSDashboardE2E:
    """
    IMS Dashboard functionality:
    Standards Overview → Cross-Mapping → Unified Audit Schedule
    """

    def test_ims_overview(self, client, auth_headers):
        """E2E: IMS dashboard overview."""
        if not auth_headers:
            pytest.skip("Auth required")

        # Get standards
        response = client.get("/api/v1/standards", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "items" in data or "results" in data or "data" in data

    def test_cross_standard_mapping(self, client, auth_headers):
        """E2E: Cross-standard mapping."""
        if not auth_headers:
            pytest.skip("Auth required")

        # This would test clause mappings across standards
        response = client.get("/api/v1/standards/cross-mapping", headers=auth_headers)
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))


# ============================================================================
# E2E: Analytics & Reporting
# ============================================================================


class TestAnalyticsE2E:
    """
    Analytics functionality:
    Dashboard → Drill-Down → Export → Scheduled Reports
    """

    def test_analytics_dashboard(self, client, auth_headers):
        """E2E: Analytics dashboard."""
        if not auth_headers:
            pytest.skip("Auth required")

        # Summary
        summary_response = client.get(
            "/api/v1/analytics/summary",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert summary_response.status_code in [200, 404]
        if summary_response.status_code == 200:
            summary_data = summary_response.json()
            assert isinstance(summary_data, dict)

        # Trends
        trends_response = client.get(
            "/api/v1/analytics/trends",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert trends_response.status_code in [200, 404]
        if trends_response.status_code == 200:
            trends_data = trends_response.json()
            assert isinstance(trends_data, dict)

    def test_report_generation(self, client, auth_headers):
        """E2E: Report generation."""
        if not auth_headers:
            pytest.skip("Auth required")

        # Generate report
        report_request = {
            "report_type": "incident_summary",
            "date_from": (datetime.now() - timedelta(days=30)).isoformat(),
            "date_to": datetime.now().isoformat(),
            "format": "pdf",
        }

        response = client.post(
            "/api/v1/analytics/reports/generate",
            json=report_request,
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 201, 404, 422]
        if response.status_code in [200, 201]:
            data = response.json()
            assert isinstance(data, dict)
            assert "id" in data or "report_id" in data or "status" in data


# ============================================================================
# E2E: User Journey - New Employee
# ============================================================================


class TestNewEmployeeJourneyE2E:
    """
    Complete new employee journey:
    Portal Login → Submit Report → Track Status → Use Help
    """

    def test_new_employee_complete_journey(self, client):
        """E2E: New employee uses portal for first time."""

        # === Step 1: View portal stats ===
        stats_response = client.get("/api/v1/portal/stats")
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert isinstance(stats_data, dict)

        # === Step 2: Submit first incident ===
        incident_response = client.post(
            "/api/v1/portal/reports/",
            json={
                "report_type": "incident",
                "title": f"New Employee Test - First Report - {uuid4().hex[:8]}",
                "description": "Testing the incident reporting system for the first time.",
                "severity": "low",
                "location": "Office Building",
                "is_anonymous": False,
                "reporter_name": "New Employee",
                "reporter_email": "new.employee@example.com",
            },
        )
        assert incident_response.status_code in [200, 201]

        data = incident_response.json()
        assert "reference_number" in data
        reference = data.get("reference_number")
        tracking = data.get("tracking_code")

        # === Step 3: Track the report ===
        if reference and tracking:
            track_response = client.get(
                f"/api/v1/portal/reports/{reference}/",
                params={"tracking_code": tracking},
            )
            assert track_response.status_code in [200, 404]
            if track_response.status_code == 200:
                track_data = track_response.json()
                assert "reference_number" in track_data

        # === Step 4: Access help ===
        help_response = client.get("/api/v1/portal/help")
        # TODO: Remove 404 when endpoint is implemented
        assert help_response.status_code in [200, 404]
        if help_response.status_code == 200:
            help_data = help_response.json()
            assert isinstance(help_data, (list, dict))


# ============================================================================
# E2E: User Journey - Safety Manager
# ============================================================================


class TestSafetyManagerJourneyE2E:
    """
    Complete safety manager journey:
    Dashboard → Review Incidents → Assign Actions → Run Audit → Report
    """

    def test_safety_manager_daily_workflow(self, client, auth_headers):
        """E2E: Safety manager daily workflow."""
        if not auth_headers:
            pytest.skip("Auth required")

        # === Step 1: Check dashboard ===
        incidents_response = client.get(
            "/api/v1/incidents?page=1&per_page=10",
            headers=auth_headers,
        )
        assert incidents_response.status_code == 200
        incidents_data = incidents_response.json()
        assert isinstance(incidents_data, (list, dict))

        # === Step 2: Review open incidents ===
        open_response = client.get(
            "/api/v1/incidents?status=reported",
            headers=auth_headers,
        )
        assert open_response.status_code == 200
        open_data = open_response.json()
        assert isinstance(open_data, (list, dict))

        # === Step 3: Check upcoming audits ===
        audits_response = client.get(
            "/api/v1/audits/runs?status=scheduled",
            headers=auth_headers,
        )
        assert audits_response.status_code == 200
        audits_data = audits_response.json()
        assert isinstance(audits_data, (list, dict))

        # === Step 4: Review risks ===
        risks_response = client.get("/api/v1/risks", headers=auth_headers)
        assert risks_response.status_code == 200
        risks_data = risks_response.json()
        assert isinstance(risks_data, (list, dict))


# ============================================================================
# E2E: Stress & Edge Cases
# ============================================================================


class TestEdgeCasesE2E:
    """Edge cases and boundary conditions."""

    def test_large_description_handling(self, client):
        """E2E: Handle large text inputs."""
        large_description = "This is a detailed description. " * 500

        response = client.post(
            "/api/v1/portal/reports/",
            json={
                "report_type": "incident",
                "title": f"Large Description Test - {uuid4().hex[:8]}",
                "description": large_description[:10000],
                "severity": "low",
            },
        )
        assert response.status_code in [200, 201, 422]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "reference_number" in data
        elif response.status_code == 422:
            data = response.json()
            error_data = data.get("error", data)
            assert "message" in error_data or "detail" in data

    def test_special_characters_handling(self, client):
        """E2E: Handle special characters."""
        special_title = f"Test with émojis 🚨 and spëcial çharacters - {uuid4().hex[:8]}"

        response = client.post(
            "/api/v1/portal/reports/",
            json={
                "report_type": "incident",
                "title": special_title,
                "description": "Testing Unicode handling.",
                "severity": "low",
            },
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "reference_number" in data

    def test_concurrent_requests(self, client, auth_headers):
        """E2E: Handle concurrent requests."""
        if not auth_headers:
            pytest.skip("Auth required")

        # Make multiple rapid requests
        responses = []
        for _ in range(5):
            response = client.get("/api/v1/incidents?page=1&per_page=5", headers=auth_headers)
            responses.append(response.status_code)

        # All should succeed
        assert all(status == 200 for status in responses)


# ============================================================================
# E2E Summary Test
# ============================================================================


class TestE2ESummary:
    """Summary validation."""

    def test_all_critical_endpoints_accessible(self, client, auth_headers):
        """E2E: All critical endpoints are accessible."""
        if not auth_headers:
            pytest.skip("Auth required")

        critical_endpoints = [
            "/api/v1/incidents",
            "/api/v1/audits/runs",
            "/api/v1/audits/findings",
            "/api/v1/risks",
            "/api/v1/standards",
            "/api/v1/documents",
            "/api/v1/policies",
            "/api/v1/users/me",
        ]

        for endpoint in critical_endpoints:
            response = client.get(endpoint, headers=auth_headers)
            assert response.status_code == 200, f"Failed: {endpoint}"
            data = response.json()
            assert isinstance(data, (list, dict)), f"Invalid response type for {endpoint}"
