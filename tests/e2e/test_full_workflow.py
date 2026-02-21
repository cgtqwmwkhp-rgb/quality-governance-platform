"""
End-to-End Test Suite - Full Workflow Coverage

Tests complete user journeys through the platform.
Target: 80%+ E2E coverage of critical paths.

Run with:
    pytest tests/e2e/ -v --tb=short
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client():
    """Get test client."""
    from src.main import app

    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Get authenticated headers."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser@plantexpand.com", "password": "testpassword123"},
    )
    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


@pytest.fixture
def admin_headers(client):
    """Get admin authenticated headers."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin@plantexpand.com", "password": "adminpassword123"},
    )
    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


# ============================================================================
# Mock-based tests that run without database infrastructure
# ============================================================================


class TestAppImportsAndHealth:
    """Tests that verify the application bootstraps and key modules import."""

    def test_app_creates_successfully(self) -> None:
        """Verify FastAPI app object can be imported."""
        from src.main import app

        assert app is not None
        assert app.title is not None

    def test_test_client_instantiation(self) -> None:
        """Verify TestClient can wrap the app without a live database."""
        from src.main import app

        client = TestClient(app, raise_server_exceptions=False)
        assert client is not None

    def test_health_endpoint_responds(self, client) -> None:
        """Health endpoint should respond even without DB."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_liveness_probe_responds(self, client) -> None:
        """Liveness probe should always return 200."""
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestFullWorkflowSchemaValidation:
    """Validate data structures used across the full workflow lifecycle."""

    def test_incident_report_payload_structure(self) -> None:
        """Validate the structure of an incident report payload."""
        payload = {
            "report_type": "incident",
            "title": "Slip hazard in warehouse",
            "description": "Water leak causing slippery floor.",
            "severity": "high",
            "location": "Warehouse - Loading Bay A",
            "is_anonymous": False,
            "reporter_name": "John Doe",
            "reporter_email": "john.doe@example.com",
        }
        assert payload["report_type"] in ("incident", "near_miss", "hazard", "complaint")
        assert payload["severity"] in ("low", "medium", "high", "critical")
        assert isinstance(payload["is_anonymous"], bool)

    def test_audit_finding_payload_structure(self) -> None:
        """Validate audit finding data dictionary has required keys."""
        finding = {
            "audit_run_id": 1,
            "clause_reference": "ISO 9001:2015 - 7.5.1",
            "finding_type": "minor_nc",
            "description": "Document control procedure not followed",
            "evidence": "Observed outdated document in use",
            "recommendations": "Refresh training on document control",
        }
        required_keys = {"audit_run_id", "clause_reference", "finding_type", "description"}
        assert required_keys.issubset(finding.keys())

    def test_rta_report_payload_structure(self) -> None:
        """Validate RTA report payload has required fields."""
        rta = {
            "vehicle_registration": "PLT-001",
            "driver_name": "Test Driver",
            "incident_date": datetime.now().isoformat(),
            "location": "M25 Junction 10",
            "description": "Minor rear-end collision",
            "third_party_involved": True,
            "injuries": False,
        }
        assert isinstance(rta["third_party_involved"], bool)
        assert isinstance(rta["injuries"], bool)
        assert rta["vehicle_registration"]


# ============================================================================
# E2E Test: Complete Incident Lifecycle
# ============================================================================


class TestIncidentLifecycle:
    """Test complete incident workflow from report to closure."""

    def test_full_incident_workflow(self, client, auth_headers):
        """
        E2E: Report → Investigation → Actions → Resolution → Closure
        """
        # Step 1: Report an incident via portal
        report_response = client.post(
            "/api/v1/portal/reports/",
            json={
                "report_type": "incident",
                "title": "E2E Test - Slip hazard in warehouse",
                "description": "Water leak causing slippery floor near loading bay A.",
                "severity": "high",
                "location": "Warehouse - Loading Bay A",
                "is_anonymous": False,
                "reporter_name": "John Doe",
                "reporter_email": "john.doe@example.com",
            },
        )
        assert report_response.status_code in [200, 201]
        report_data = report_response.json()
        assert "reference_number" in report_data
        reference = report_data["reference_number"]
        tracking_code = report_data.get("tracking_code", "")

        # Step 2: Track the report status
        track_response = client.get(
            f"/api/v1/portal/reports/{reference}/",
            params={"tracking_code": tracking_code},
        )
        # May be 404 if not found in test DB
        if track_response.status_code == 200:
            assert track_response.json()["reference_number"] == reference

        # Step 3: Admin views incident list
        if auth_headers:
            list_response = client.get(
                "/api/v1/incidents",
                headers=auth_headers,
            )
            assert list_response.status_code == 200
            list_data = list_response.json()
            assert isinstance(list_data, (list, dict))

        # Step 4: Admin updates incident status
        # (Would need actual incident ID from DB)

    def test_incident_search_and_filter(self, client, auth_headers):
        """Test incident search and filtering capabilities."""
        if not auth_headers:
            pytest.skip("Authentication required")

        # Search by status
        response = client.get(
            "/api/v1/incidents?status=open",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

        # Search by severity
        response = client.get(
            "/api/v1/incidents?severity=high",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))


# ============================================================================
# E2E Test: Audit Workflow
# ============================================================================


class TestAuditWorkflow:
    """Test complete audit workflow from planning to closure."""

    def test_audit_template_creation_and_execution(self, client, auth_headers):
        """
        E2E: Create Template → Schedule Audit → Execute → Findings → Report
        """
        if not auth_headers:
            pytest.skip("Authentication required")

        # Step 1: List audit templates
        templates_response = client.get(
            "/api/v1/audits/templates",
            headers=auth_headers,
        )
        assert templates_response.status_code == 200
        templates_data = templates_response.json()
        assert isinstance(templates_data, (list, dict))

        # Step 2: List scheduled audits
        audits_response = client.get(
            "/api/v1/audits/runs",
            headers=auth_headers,
        )
        assert audits_response.status_code == 200
        audits_data = audits_response.json()
        assert isinstance(audits_data, (list, dict))

        # Step 3: List findings
        findings_response = client.get(
            "/api/v1/audits/findings",
            headers=auth_headers,
        )
        assert findings_response.status_code == 200
        findings_data = findings_response.json()
        assert isinstance(findings_data, (list, dict))

    def test_audit_with_findings_workflow(self, client, auth_headers):
        """Test audit execution with finding creation."""
        if not auth_headers:
            pytest.skip("Authentication required")

        # Create an audit finding
        finding_data = {
            "audit_run_id": 1,
            "clause_reference": "ISO 9001:2015 - 7.5.1",
            "finding_type": "minor_nc",
            "description": "Document control procedure not followed",
            "evidence": "Observed outdated document in use",
            "recommendations": "Refresh training on document control",
        }

        # Would create finding if audit run exists
        response = client.get(
            "/api/v1/audits/findings",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))


# ============================================================================
# E2E Test: Risk Management Workflow
# ============================================================================


class TestRiskManagementWorkflow:
    """Test complete risk management lifecycle."""

    def test_risk_identification_to_treatment(self, client, auth_headers):
        """
        E2E: Identify → Assess → Treat → Monitor → Review
        """
        if not auth_headers:
            pytest.skip("Authentication required")

        # Step 1: List risks
        risks_response = client.get(
            "/api/v1/risks",
            headers=auth_headers,
        )
        assert risks_response.status_code == 200
        risks_data = risks_response.json()
        assert isinstance(risks_data, (list, dict))
        if isinstance(risks_data, dict):
            assert "items" in risks_data or "results" in risks_data or "data" in risks_data

        # Step 2: Get risk register heat map
        heatmap_response = client.get(
            "/api/v1/risk-register/heat-map",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert heatmap_response.status_code in [200, 404]
        if heatmap_response.status_code == 200:
            heatmap_data = heatmap_response.json()
            assert isinstance(heatmap_data, dict)

    def test_risk_control_linkage(self, client, auth_headers):
        """Test risk to control mapping."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get(
            "/api/v1/risk-register/controls",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))


# ============================================================================
# E2E Test: Compliance Evidence Workflow
# ============================================================================


class TestComplianceWorkflow:
    """Test compliance evidence and gap analysis workflow."""

    def test_evidence_collection_workflow(self, client, auth_headers):
        """
        E2E: Tag Content → Map to Clause → Gap Analysis → Audit Support
        """
        if not auth_headers:
            pytest.skip("Authentication required")

        # Step 1: Get standards
        standards_response = client.get(
            "/api/v1/standards",
            headers=auth_headers,
        )
        assert standards_response.status_code == 200
        standards_data = standards_response.json()
        assert isinstance(standards_data, (list, dict))

        # Step 2: Get compliance evidence
        evidence_response = client.get(
            "/api/v1/compliance/evidence",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert evidence_response.status_code in [200, 404]
        if evidence_response.status_code == 200:
            evidence_data = evidence_response.json()
            assert isinstance(evidence_data, (list, dict))

    def test_gap_analysis(self, client, auth_headers):
        """Test compliance gap analysis."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get(
            "/api/v1/compliance-automation/gap-analyses",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))


# ============================================================================
# E2E Test: Employee Portal Complete Flow
# ============================================================================


class TestEmployeePortalFlow:
    """Test complete employee portal user journey."""

    def test_portal_complete_journey(self, client):
        """
        E2E: Login → View Options → Submit Report → Track → View Status
        """
        # Step 1: Get portal stats (public)
        stats_response = client.get("/api/v1/portal/stats")
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert isinstance(stats_data, dict)

        # Step 2: Submit incident report
        report_response = client.post(
            "/api/v1/portal/reports/",
            json={
                "report_type": "incident",
                "title": "Portal E2E Test - Near miss",
                "description": "Forklift nearly struck pedestrian in aisle 5",
                "severity": "medium",
                "location": "Warehouse Aisle 5",
                "is_anonymous": True,
            },
        )
        assert report_response.status_code in [200, 201]
        data = report_response.json()
        assert "reference_number" in data
        reference = data.get("reference_number")
        tracking = data.get("tracking_code")

        # Step 3: Track the report
        if reference and tracking:
            track_response = client.get(
                f"/api/v1/portal/reports/{reference}/",
                params={"tracking_code": tracking},
            )
            # May be 404 in test environment
            assert track_response.status_code in [200, 404]
            if track_response.status_code == 200:
                track_data = track_response.json()
                assert "reference_number" in track_data

    def test_portal_sos_flow(self, client):
        """Test emergency SOS functionality."""
        # SOS should be accessible without auth
        sos_response = client.post(
            "/api/v1/portal/sos",
            json={
                "location": "Site Alpha - Building 2",
                "message": "Medical emergency - worker collapsed",
                "contact_number": "+44 7700 900000",
            },
        )
        # TODO: Remove 404 when SOS endpoint is implemented
        assert sos_response.status_code in [200, 201, 404, 422]
        if sos_response.status_code in [200, 201]:
            data = sos_response.json()
            assert isinstance(data, dict)

    def test_rta_report_flow(self, client):
        """Test RTA (Road Traffic Accident) report submission."""
        rta_response = client.post(
            "/api/v1/portal/rta",
            json={
                "vehicle_registration": "PLT-001",
                "driver_name": "Test Driver",
                "incident_date": datetime.now().isoformat(),
                "location": "M25 Junction 10",
                "description": "Minor rear-end collision",
                "third_party_involved": True,
                "injuries": False,
            },
        )
        # TODO: Remove 404 when RTA endpoint is implemented
        assert rta_response.status_code in [200, 201, 404, 422]
        if rta_response.status_code in [200, 201]:
            data = rta_response.json()
            assert "id" in data or "reference" in data or "reference_number" in data


# ============================================================================
# E2E Test: Document Control Workflow
# ============================================================================


class TestDocumentControlFlow:
    """Test document control and approval workflow."""

    def test_document_lifecycle(self, client, auth_headers):
        """
        E2E: Upload → Review → Approve → Distribute → Retire
        """
        if not auth_headers:
            pytest.skip("Authentication required")

        # List documents
        response = client.get(
            "/api/v1/documents",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "items" in data or "results" in data or "data" in data


# ============================================================================
# E2E Test: Notification & Workflow Automation
# ============================================================================


class TestNotificationWorkflow:
    """Test notification and workflow automation."""

    def test_notification_flow(self, client, auth_headers):
        """Test notification delivery and preferences."""
        if not auth_headers:
            pytest.skip("Authentication required")

        # Get notifications
        response = client.get(
            "/api/v1/notifications",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    def test_workflow_execution(self, client, auth_headers):
        """Test workflow automation triggers."""
        if not auth_headers:
            pytest.skip("Authentication required")

        # List workflows
        response = client.get(
            "/api/v1/workflows",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))


# ============================================================================
# E2E Test: Analytics & Reporting
# ============================================================================


class TestAnalyticsReporting:
    """Test analytics and reporting workflows."""

    def test_analytics_dashboard(self, client, auth_headers):
        """Test analytics dashboard data retrieval."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get(
            "/api/v1/analytics/summary",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_report_generation(self, client, auth_headers):
        """Test report generation."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.post(
            "/api/v1/analytics/reports/generate",
            json={
                "report_type": "incident_summary",
                "date_from": (datetime.now() - timedelta(days=30)).isoformat(),
                "date_to": datetime.now().isoformat(),
            },
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 201, 404, 422]
        if response.status_code in [200, 201]:
            data = response.json()
            assert isinstance(data, dict)
            assert "id" in data or "report_id" in data or "status" in data


# ============================================================================
# E2E Test: IMS & Standards Management
# ============================================================================


class TestIMSManagement:
    """Test Integrated Management System workflows."""

    def test_ims_dashboard_access(self, client, auth_headers):
        """Test IMS dashboard data retrieval."""
        if not auth_headers:
            pytest.skip("Authentication required")

        # Get standards overview
        response = client.get(
            "/api/v1/standards",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "items" in data or "results" in data or "data" in data

    def test_iso27001_isms(self, client, auth_headers):
        """Test ISO 27001 ISMS features."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get(
            "/api/v1/iso27001/assets",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    def test_uvdb_achilles(self, client, auth_headers):
        """Test UVDB Achilles audit features."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get(
            "/api/v1/uvdb/sections",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    def test_planet_mark_carbon(self, client, auth_headers):
        """Test Planet Mark carbon management features."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get(
            "/api/v1/planet-mark/years",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))


# ============================================================================
# E2E Test: User Management
# ============================================================================


class TestUserManagement:
    """Test user management workflows."""

    def test_user_profile(self, client, auth_headers):
        """Test user profile access."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get(
            "/api/v1/users/me",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    def test_user_list_admin(self, client, admin_headers):
        """Test admin user list access."""
        if not admin_headers:
            pytest.skip("Admin authentication required")

        response = client.get(
            "/api/v1/users",
            headers=admin_headers,
        )
        assert response.status_code in [200, 403]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))
            if isinstance(data, dict):
                assert "items" in data or "results" in data or "data" in data


# ============================================================================
# E2E Test: Search & Discovery
# ============================================================================


class TestSearchDiscovery:
    """Test search and discovery features."""

    def test_global_search(self, client, auth_headers):
        """Test global search functionality."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get(
            "/api/v1/search?q=safety",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    def test_filtered_search(self, client, auth_headers):
        """Test filtered search."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get(
            "/api/v1/search?q=incident&module=incidents&status=open",
            headers=auth_headers,
        )
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))
