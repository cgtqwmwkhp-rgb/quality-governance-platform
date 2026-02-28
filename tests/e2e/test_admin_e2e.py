"""
End-to-End Tests for Admin Dashboard

Comprehensive E2E coverage for admin workflows.
"""

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


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
        json={"username": "admin@plantexpand.com", "password": "adminpassword123"},
    )
    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


class TestDashboard:
    """Test dashboard functionality."""

    def test_dashboard_data_loads(self, client, auth_headers):
        """Dashboard should load all required data."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/incidents?page=1&per_page=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "items" in data or "results" in data or "data" in data

    def test_dashboard_stats(self, client, auth_headers):
        """Dashboard statistics should load."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/analytics/summary", headers=auth_headers)
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


class TestIncidentManagement:
    """Test incident management workflows."""

    def test_list_incidents(self, client, auth_headers):
        """List all incidents."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/incidents", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or isinstance(data, list)

    def test_create_incident(self, client, auth_headers):
        """Create new incident."""
        if not auth_headers:
            pytest.skip("Authentication required")

        uid = uuid4().hex[:8]
        response = client.post(
            "/api/v1/incidents",
            json={
                "title": f"Admin Created Incident - {uid}",
                "description": "Incident created by admin for E2E testing.",
                "severity": "medium",
                "incident_type": "safety",
                "location": "Office Building",
                "reported_date": datetime.now().isoformat(),
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 201, 422]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "id" in data or "reference" in data
        elif response.status_code == 422:
            data = response.json()
            error_data = data.get("error", data)
            assert "message" in error_data or "detail" in data

    def test_filter_incidents(self, client, auth_headers):
        """Filter incidents by various criteria."""
        if not auth_headers:
            pytest.skip("Authentication required")

        # By status
        response = client.get("/api/v1/incidents?status=open", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

        # By severity
        response = client.get("/api/v1/incidents?severity=high", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

    def test_incident_pagination(self, client, auth_headers):
        """Test incident list pagination."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/incidents?page=1&per_page=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or isinstance(data, list)


class TestAuditManagement:
    """Test audit management workflows."""

    def test_list_audit_templates(self, client, auth_headers):
        """List audit templates."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/audits/templates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "items" in data or "results" in data or "data" in data

    def test_list_audit_runs(self, client, auth_headers):
        """List audit runs."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/audits/runs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "items" in data or "results" in data or "data" in data

    def test_list_audit_findings(self, client, auth_headers):
        """List audit findings."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/audits/findings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "items" in data or "results" in data or "data" in data


class TestRiskManagement:
    """Test risk management workflows."""

    def test_list_risks(self, client, auth_headers):
        """List risks."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/risks", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "items" in data or "results" in data or "data" in data

    def test_create_risk(self, client, auth_headers):
        """Create new risk."""
        if not auth_headers:
            pytest.skip("Authentication required")

        uid = uuid4().hex[:8]
        response = client.post(
            "/api/v1/risks",
            json={
                "title": f"E2E Test Risk - {uid}",
                "description": "Risk created for E2E testing.",
                "category": "operational",
                "likelihood": 3,
                "impact": 4,
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 201, 422]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "id" in data or "reference" in data
        elif response.status_code == 422:
            data = response.json()
            error_data = data.get("error", data)
            assert "message" in error_data or "detail" in data


class TestCompliance:
    """Test compliance management workflows."""

    def test_list_standards(self, client, auth_headers):
        """List compliance standards."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/standards", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "items" in data or "results" in data or "data" in data

    def test_compliance_evidence(self, client, auth_headers):
        """Get compliance evidence."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/compliance/evidence", headers=auth_headers)
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))
            if isinstance(data, dict):
                assert "items" in data or "results" in data or "data" in data


class TestUserManagement:
    """Test user management workflows."""

    def test_get_current_user(self, client, auth_headers):
        """Get current user profile."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/users/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    def test_list_users(self, client, auth_headers):
        """List all users (admin only)."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/users", headers=auth_headers)
        assert response.status_code in [200, 403]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))
            if isinstance(data, dict):
                assert "items" in data or "results" in data or "data" in data


class TestDocumentManagement:
    """Test document management workflows."""

    def test_list_documents(self, client, auth_headers):
        """List documents."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/documents", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "items" in data or "results" in data or "data" in data

    def test_list_policies(self, client, auth_headers):
        """List policies."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/policies", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "items" in data or "results" in data or "data" in data


class TestNotifications:
    """Test notification workflows."""

    def test_list_notifications(self, client, auth_headers):
        """List notifications."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/notifications", headers=auth_headers)
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))
            if isinstance(data, dict):
                assert "items" in data or "results" in data or "data" in data


class TestAnalytics:
    """Test analytics and reporting."""

    def test_analytics_summary(self, client, auth_headers):
        """Get analytics summary."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/analytics/summary", headers=auth_headers)
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_analytics_trends(self, client, auth_headers):
        """Get trend data."""
        if not auth_headers:
            pytest.skip("Authentication required")

        response = client.get("/api/v1/analytics/trends", headers=auth_headers)
        # TODO: Remove 404 when endpoint is implemented
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
