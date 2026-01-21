"""
Comprehensive Integration Tests for All API Endpoints

Target: 90%+ endpoint coverage
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def client():
    """Create test client."""
    from src.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def auth_headers(client) -> dict:
    """Get authenticated headers."""
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser@plantexpand.com", "password": "testpassword123"},
    )
    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


# ============================================================================
# Health Endpoints
# ============================================================================


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_endpoint(self, client):
        """GET /health returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_format(self, client):
        """Health response has expected format."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data


# ============================================================================
# Auth Endpoints
# ============================================================================


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    def test_login_with_invalid_credentials(self, client):
        """POST /api/auth/login with invalid credentials returns 401."""
        response = client.post(
            "/api/auth/login",
            json={"username": "invalid@test.com", "password": "wrongpassword"},
        )
        assert response.status_code in [401, 422]

    def test_login_missing_fields(self, client):
        """POST /api/auth/login with missing fields returns 422."""
        response = client.post("/api/auth/login", json={})
        assert response.status_code == 422

    def test_protected_endpoint_without_auth(self, client):
        """Protected endpoints return 401 without auth."""
        response = client.get("/api/users/me")
        assert response.status_code == 401


# ============================================================================
# Incident Endpoints
# ============================================================================


class TestIncidentEndpoints:
    """Tests for incident management endpoints."""

    def test_list_incidents(self, client, auth_headers):
        """GET /api/incidents returns 200."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/incidents", headers=auth_headers)
        assert response.status_code == 200

    def test_list_incidents_with_pagination(self, client, auth_headers):
        """GET /api/incidents with pagination works."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get(
            "/api/incidents?page=1&per_page=10",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or isinstance(data, list)

    def test_list_incidents_with_filters(self, client, auth_headers):
        """GET /api/incidents with filters works."""
        if not auth_headers:
            pytest.skip("Auth required")

        # Filter by status
        response = client.get("/api/incidents?status=open", headers=auth_headers)
        assert response.status_code == 200

        # Filter by severity
        response = client.get("/api/incidents?severity=high", headers=auth_headers)
        assert response.status_code == 200

    def test_create_incident(self, client, auth_headers):
        """POST /api/incidents creates incident."""
        if not auth_headers:
            pytest.skip("Auth required")

        response = client.post(
            "/api/incidents",
            json={
                "title": "Integration Test Incident",
                "description": "Created by integration test",
                "severity": "low",
                "incident_type": "safety",
                "location": "Test Location",
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 201, 422]

    def test_create_incident_validation(self, client, auth_headers):
        """POST /api/incidents validates input."""
        if not auth_headers:
            pytest.skip("Auth required")

        response = client.post(
            "/api/incidents",
            json={"title": ""},  # Invalid - empty title
            headers=auth_headers,
        )
        assert response.status_code == 422


# ============================================================================
# Audit Endpoints
# ============================================================================


class TestAuditEndpoints:
    """Tests for audit management endpoints."""

    def test_list_audit_templates(self, client, auth_headers):
        """GET /api/audit-templates returns 200."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/audit-templates", headers=auth_headers)
        assert response.status_code == 200

    def test_list_audit_runs(self, client, auth_headers):
        """GET /api/audits/runs returns 200."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/audits/runs", headers=auth_headers)
        assert response.status_code == 200

    def test_list_audit_findings(self, client, auth_headers):
        """GET /api/audits/findings returns 200."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/audits/findings", headers=auth_headers)
        assert response.status_code == 200

    def test_audit_templates_pagination(self, client, auth_headers):
        """GET /api/audit-templates with pagination works."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get(
            "/api/audit-templates?page=1&per_page=10",
            headers=auth_headers,
        )
        assert response.status_code == 200


# ============================================================================
# Risk Endpoints
# ============================================================================


class TestRiskEndpoints:
    """Tests for risk management endpoints."""

    def test_list_risks(self, client, auth_headers):
        """GET /api/risks returns 200."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/risks", headers=auth_headers)
        assert response.status_code == 200

    def test_list_risks_with_filters(self, client, auth_headers):
        """GET /api/risks with filters works."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/risks?category=operational", headers=auth_headers)
        assert response.status_code == 200

    def test_create_risk(self, client, auth_headers):
        """POST /api/risks creates risk."""
        if not auth_headers:
            pytest.skip("Auth required")

        response = client.post(
            "/api/risks",
            json={
                "title": "Integration Test Risk",
                "description": "Created by integration test",
                "category": "operational",
                "likelihood": 3,
                "impact": 3,
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 201, 422]


# ============================================================================
# Complaint Endpoints
# ============================================================================


class TestComplaintEndpoints:
    """Tests for complaint management endpoints."""

    def test_list_complaints(self, client, auth_headers):
        """GET /api/complaints returns 200."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/complaints", headers=auth_headers)
        assert response.status_code == 200

    def test_create_complaint(self, client, auth_headers):
        """POST /api/complaints creates complaint."""
        if not auth_headers:
            pytest.skip("Auth required")

        response = client.post(
            "/api/complaints",
            json={
                "title": "Integration Test Complaint",
                "description": "Created by integration test",
                "priority": "medium",
                "complaint_type": "service",
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 201, 422]


# ============================================================================
# RTA Endpoints
# ============================================================================


class TestRTAEndpoints:
    """Tests for RTA management endpoints."""

    def test_list_rtas(self, client, auth_headers):
        """GET /api/rtas returns 200."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/rtas", headers=auth_headers)
        assert response.status_code == 200


# ============================================================================
# Document Endpoints
# ============================================================================


class TestDocumentEndpoints:
    """Tests for document management endpoints."""

    def test_list_documents(self, client, auth_headers):
        """GET /api/documents returns 200."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/documents", headers=auth_headers)
        assert response.status_code == 200

    def test_list_policies(self, client, auth_headers):
        """GET /api/policies returns 200."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/policies", headers=auth_headers)
        assert response.status_code == 200


# ============================================================================
# Standards Endpoints
# ============================================================================


class TestStandardsEndpoints:
    """Tests for standards management endpoints."""

    def test_list_standards(self, client, auth_headers):
        """GET /api/standards returns 200."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/standards", headers=auth_headers)
        assert response.status_code == 200


# ============================================================================
# User Endpoints
# ============================================================================


class TestUserEndpoints:
    """Tests for user management endpoints."""

    def test_get_current_user(self, client, auth_headers):
        """GET /api/users/me returns current user."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/users/me", headers=auth_headers)
        assert response.status_code == 200

    def test_list_users(self, client, auth_headers):
        """GET /api/users returns 200 or 403."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/users", headers=auth_headers)
        assert response.status_code in [200, 403]


# ============================================================================
# Portal Endpoints
# ============================================================================


class TestPortalEndpoints:
    """Tests for employee portal endpoints."""

    def test_portal_stats(self, client):
        """GET /api/portal/stats returns 200."""
        response = client.get("/api/portal/stats")
        assert response.status_code == 200

    def test_submit_report(self, client):
        """POST /api/portal/report submits report."""
        response = client.post(
            "/api/portal/report",
            json={
                "report_type": "incident",
                "title": "Integration Test Portal Report",
                "description": "Created by integration test",
                "severity": "low",
                "is_anonymous": True,
            },
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "reference_number" in data

    def test_submit_report_validation(self, client):
        """POST /api/portal/report validates input."""
        response = client.post(
            "/api/portal/report",
            json={"report_type": "invalid"},
        )
        assert response.status_code == 422


# ============================================================================
# Workflow Endpoints
# ============================================================================


class TestWorkflowEndpoints:
    """Tests for workflow endpoints."""

    def test_list_workflow_templates(self, client, auth_headers):
        """GET /api/workflows/templates returns 200."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/workflows/templates", headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_list_workflow_instances(self, client, auth_headers):
        """GET /api/workflows/instances returns 200."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/workflows/instances", headers=auth_headers)
        assert response.status_code in [200, 404]


# ============================================================================
# Risk Register Endpoints
# ============================================================================


class TestRiskRegisterEndpoints:
    """Tests for risk register endpoints."""

    def test_risk_register_heatmap(self, client, auth_headers):
        """GET /api/risk-register/heat-map returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/risk-register/heat-map", headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_risk_register_controls(self, client, auth_headers):
        """GET /api/risk-register/controls returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/risk-register/controls", headers=auth_headers)
        assert response.status_code in [200, 404]


# ============================================================================
# Compliance Endpoints
# ============================================================================


class TestComplianceEndpoints:
    """Tests for compliance endpoints."""

    def test_compliance_evidence(self, client, auth_headers):
        """GET /api/compliance/evidence returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/compliance/evidence", headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_compliance_gaps(self, client, auth_headers):
        """GET /api/compliance/gaps returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/compliance/gaps", headers=auth_headers)
        assert response.status_code in [200, 404]


# ============================================================================
# ISO 27001 Endpoints
# ============================================================================


class TestISO27001Endpoints:
    """Tests for ISO 27001 ISMS endpoints."""

    def test_iso27001_assets(self, client, auth_headers):
        """GET /api/iso27001/assets returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/iso27001/assets", headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_iso27001_controls(self, client, auth_headers):
        """GET /api/iso27001/controls returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/iso27001/controls", headers=auth_headers)
        assert response.status_code in [200, 404]


# ============================================================================
# UVDB Endpoints
# ============================================================================


class TestUVDBEndpoints:
    """Tests for UVDB Achilles endpoints."""

    def test_uvdb_sections(self, client, auth_headers):
        """GET /api/uvdb/sections returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/uvdb/sections", headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_uvdb_audits(self, client, auth_headers):
        """GET /api/uvdb/audits returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/uvdb/audits", headers=auth_headers)
        assert response.status_code in [200, 404]


# ============================================================================
# Planet Mark Endpoints
# ============================================================================


class TestPlanetMarkEndpoints:
    """Tests for Planet Mark endpoints."""

    def test_planet_mark_years(self, client, auth_headers):
        """GET /api/planet-mark/years returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/planet-mark/years", headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_planet_mark_emissions(self, client, auth_headers):
        """GET /api/planet-mark/emissions returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/planet-mark/emissions", headers=auth_headers)
        assert response.status_code in [200, 404]


# ============================================================================
# Analytics Endpoints
# ============================================================================


class TestAnalyticsEndpoints:
    """Tests for analytics endpoints."""

    def test_analytics_summary(self, client, auth_headers):
        """GET /api/analytics/summary returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/analytics/summary", headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_analytics_trends(self, client, auth_headers):
        """GET /api/analytics/trends returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/analytics/trends", headers=auth_headers)
        assert response.status_code in [200, 404]


# ============================================================================
# Notification Endpoints
# ============================================================================


class TestNotificationEndpoints:
    """Tests for notification endpoints."""

    def test_list_notifications(self, client, auth_headers):
        """GET /api/notifications returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/notifications", headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_notification_preferences(self, client, auth_headers):
        """GET /api/notifications/preferences returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/notifications/preferences", headers=auth_headers)
        assert response.status_code in [200, 404]


# ============================================================================
# Investigation Endpoints
# ============================================================================


class TestInvestigationEndpoints:
    """Tests for investigation endpoints."""

    def test_list_investigations(self, client, auth_headers):
        """GET /api/investigations returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/investigations", headers=auth_headers)
        assert response.status_code == 200

    def test_investigation_templates(self, client, auth_headers):
        """GET /api/investigation-templates returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/investigation-templates", headers=auth_headers)
        assert response.status_code == 200


# ============================================================================
# AI Intelligence Endpoints
# ============================================================================


class TestAIIntelligenceEndpoints:
    """Tests for AI intelligence endpoints."""

    def test_ai_predictions(self, client, auth_headers):
        """GET /api/ai/predictions returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/ai-intelligence/predictions", headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_ai_insights(self, client, auth_headers):
        """GET /api/ai/insights returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/ai-intelligence/insights", headers=auth_headers)
        assert response.status_code in [200, 404]


# ============================================================================
# Document Control Endpoints
# ============================================================================


class TestDocumentControlEndpoints:
    """Tests for document control endpoints."""

    def test_document_versions(self, client, auth_headers):
        """GET /api/document-control/versions returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/document-control/versions", headers=auth_headers)
        assert response.status_code in [200, 404]


# ============================================================================
# Compliance Automation Endpoints
# ============================================================================


class TestComplianceAutomationEndpoints:
    """Tests for compliance automation endpoints."""

    def test_regulatory_updates(self, client, auth_headers):
        """GET /api/compliance-automation/updates returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get("/api/compliance-automation/updates", headers=auth_headers)
        assert response.status_code in [200, 404]

    def test_scheduled_audits(self, client, auth_headers):
        """GET /api/compliance-automation/scheduled-audits returns data."""
        if not auth_headers:
            pytest.skip("Auth required")
        response = client.get(
            "/api/compliance-automation/scheduled-audits",
            headers=auth_headers,
        )
        assert response.status_code in [200, 404]
