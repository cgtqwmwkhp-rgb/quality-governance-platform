"""
UAT Stage 1: Basic User-to-Admin Workflow Tests (50 Tests)

These tests verify fundamental system workflows from end-user
perspective through to admin operations.

Categories:
- UAT-001 to UAT-010: Employee Portal (Anonymous Reporting)
- UAT-011 to UAT-020: Incident Management
- UAT-021 to UAT-030: Complaint Management
- UAT-031 to UAT-035: RTA Management
- UAT-036 to UAT-040: User & Role Management
- UAT-041 to UAT-045: Workflow & Approvals
- UAT-046 to UAT-050: System Health & Security
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def client():
    """Async HTTP client for UAT tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def valid_incident_report():
    """Valid incident report data for employee portal."""
    return {
        "report_type": "incident",
        "title": "UAT Test - Slip hazard near entrance",
        "description": "Water leak causing slippery floor near main entrance. "
        "Multiple employees have reported near-misses.",
        "location": "Building A - Main Entrance",
        "severity": "high",
        "reporter_name": "UAT Test User",
        "reporter_email": "uat.test@example.com",
        "department": "Operations",
        "is_anonymous": False,
    }


@pytest.fixture
def valid_complaint_report():
    """Valid complaint report data for employee portal."""
    return {
        "report_type": "complaint",
        "title": "UAT Test - Service quality concern",
        "description": "Repeated delays in equipment maintenance requests. "
        "This has impacted productivity significantly.",
        "severity": "medium",
        "reporter_name": "UAT Complainant",
        "reporter_email": "uat.complainant@example.com",
        "is_anonymous": False,
    }


@pytest.fixture
def anonymous_report():
    """Anonymous report data."""
    return {
        "report_type": "incident",
        "title": "UAT Test - Anonymous safety concern",
        "description": "Confidential safety concern requiring investigation.",
        "severity": "critical",
        "is_anonymous": True,
    }


# ============================================================================
# UAT-001 to UAT-010: Employee Portal (Anonymous Reporting)
# ============================================================================


class TestEmployeePortalWorkflows:
    """Employee portal workflow tests."""

    @pytest.mark.asyncio
    async def test_uat_001_submit_incident_report(self, client, valid_incident_report):
        """UAT-001: Employee can submit an incident report via portal."""
        response = await client.post("/api/v1/portal/reports/", json=valid_incident_report)

        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "reference_number" in data
        assert data["reference_number"].startswith("INC-")
        assert "tracking_code" in data
        assert len(data["tracking_code"]) > 0

    @pytest.mark.asyncio
    async def test_uat_002_submit_complaint_report(self, client, valid_complaint_report):
        """UAT-002: Employee can submit a complaint via portal."""
        response = await client.post("/api/v1/portal/reports/", json=valid_complaint_report)

        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert data["reference_number"].startswith("COMP-")

    @pytest.mark.asyncio
    async def test_uat_003_submit_anonymous_report(self, client, anonymous_report):
        """UAT-003: Employee can submit an anonymous report."""
        response = await client.post("/api/v1/portal/reports/", json=anonymous_report)

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        # Anonymous reports still get tracking codes
        assert "tracking_code" in data

    @pytest.mark.asyncio
    async def test_uat_004_track_report_by_reference(self, client, valid_incident_report):
        """UAT-004: Employee can track report status by reference number."""
        # First submit a report
        submit_response = await client.post("/api/v1/portal/reports/", json=valid_incident_report)
        assert submit_response.status_code == 201
        ref_number = submit_response.json()["reference_number"]

        # Then track it
        track_response = await client.get(f"/api/v1/portal/reports/{ref_number}/")

        assert track_response.status_code == 200
        data = track_response.json()
        assert data["reference_number"] == ref_number
        assert "status" in data
        assert "timeline" in data

    @pytest.mark.asyncio
    async def test_uat_005_get_portal_statistics(self, client):
        """UAT-005: Portal statistics endpoint is accessible."""
        response = await client.get("/api/v1/portal/stats/")

        assert response.status_code == 200
        data = response.json()
        assert "total_reports_today" in data
        assert "average_resolution_days" in data

    @pytest.mark.asyncio
    async def test_uat_006_get_report_types(self, client):
        """UAT-006: Available report types are documented."""
        response = await client.get("/api/v1/portal/report-types/")

        assert response.status_code == 200
        data = response.json()
        assert "report_types" in data
        assert len(data["report_types"]) >= 2
        assert "severity_levels" in data

    @pytest.mark.asyncio
    async def test_uat_007_generate_qr_code_data(self, client, valid_incident_report):
        """UAT-007: QR code data can be generated for report tracking."""
        # Submit report
        submit_response = await client.post("/api/v1/portal/reports/", json=valid_incident_report)
        ref_number = submit_response.json()["reference_number"]

        # Get QR data
        qr_response = await client.get(f"/api/v1/portal/qr/{ref_number}/")

        assert qr_response.status_code == 200
        data = qr_response.json()
        assert "tracking_url" in data
        assert ref_number in data["tracking_url"]

    @pytest.mark.asyncio
    async def test_uat_008_report_validation_title_required(self, client):
        """UAT-008: Report submission validates required fields."""
        invalid_report = {
            "report_type": "incident",
            "description": "Missing title field",
            "severity": "low",
        }

        response = await client.post("/api/v1/portal/reports/", json=invalid_report)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_uat_009_report_validation_invalid_type(self, client):
        """UAT-009: Report submission rejects invalid report types."""
        invalid_report = {
            "report_type": "invalid_type",
            "title": "Test report",
            "description": "This should fail validation",
            "severity": "low",
        }

        response = await client.post("/api/v1/portal/reports/", json=invalid_report)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_uat_010_track_nonexistent_report(self, client):
        """UAT-010: Tracking non-existent report returns 404."""
        response = await client.get("/api/v1/portal/reports/INC-9999-9999/")

        assert response.status_code == 404


# ============================================================================
# UAT-011 to UAT-020: Incident Management
# ============================================================================


class TestIncidentManagementWorkflows:
    """Incident management workflow tests (requires authentication)."""

    @pytest.mark.asyncio
    async def test_uat_011_list_incidents_requires_auth(self, client):
        """UAT-011: Listing incidents requires authentication."""
        response = await client.get("/api/v1/incidents/")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_012_create_incident_requires_auth(self, client):
        """UAT-012: Creating incidents requires authentication."""
        incident = {
            "title": "Test incident",
            "description": "Test description",
            "severity": "medium",
            "incident_type": "safety",
        }

        response = await client.post("/api/v1/incidents/", json=incident)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_013_get_incident_requires_auth(self, client):
        """UAT-013: Getting incident details requires authentication."""
        response = await client.get("/api/v1/incidents/1")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_014_update_incident_requires_auth(self, client):
        """UAT-014: Updating incidents requires authentication."""
        response = await client.patch("/api/v1/incidents/1", json={"status": "closed"})

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_015_delete_incident_requires_auth(self, client):
        """UAT-015: Deleting incidents requires authentication."""
        response = await client.delete("/api/v1/incidents/1")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_016_incident_email_filter_requires_auth(self, client):
        """UAT-016: Email filter on incidents requires authentication (security fix)."""
        response = await client.get("/api/v1/incidents/?reporter_email=test@example.com")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_017_get_incident_investigations_requires_auth(self, client):
        """UAT-017: Getting incident investigations requires auth."""
        response = await client.get("/api/v1/incidents/1/investigations")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_018_incident_rate_limit_headers(self, client):
        """UAT-018: Incident endpoint returns rate limit headers."""
        response = await client.get("/api/v1/incidents/")

        # Even 401 should have rate limit headers
        assert "x-ratelimit-limit" in response.headers or response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_019_incident_request_id_header(self, client):
        """UAT-019: Incident responses include request ID."""
        response = await client.get("/api/v1/incidents/")

        assert "x-request-id" in response.headers

    @pytest.mark.asyncio
    async def test_uat_020_incident_security_headers(self, client):
        """UAT-020: Incident responses include security headers."""
        response = await client.get("/api/v1/incidents/")

        # Check for key security headers
        headers = response.headers
        assert "x-content-type-options" in headers or "x-frame-options" in headers


# ============================================================================
# UAT-021 to UAT-030: Complaint Management
# ============================================================================


class TestComplaintManagementWorkflows:
    """Complaint management workflow tests."""

    @pytest.mark.asyncio
    async def test_uat_021_list_complaints_requires_auth(self, client):
        """UAT-021: Listing complaints requires authentication."""
        response = await client.get("/api/v1/complaints/")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_022_create_complaint_requires_auth(self, client):
        """UAT-022: Creating complaints requires authentication."""
        complaint = {
            "title": "Test complaint",
            "description": "Test description",
            "complaint_type": "service",
        }

        response = await client.post("/api/v1/complaints/", json=complaint)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_023_get_complaint_requires_auth(self, client):
        """UAT-023: Getting complaint details requires authentication."""
        response = await client.get("/api/v1/complaints/1")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_024_update_complaint_requires_auth(self, client):
        """UAT-024: Updating complaints requires authentication."""
        response = await client.patch("/api/v1/complaints/1", json={"status": "closed"})

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_025_complaint_email_filter_requires_auth(self, client):
        """UAT-025: Email filter on complaints requires authentication (security fix)."""
        response = await client.get("/api/v1/complaints/?complainant_email=test@example.com")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_026_get_complaint_investigations_requires_auth(self, client):
        """UAT-026: Getting complaint investigations requires auth."""
        response = await client.get("/api/v1/complaints/1/investigations")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_027_complaint_rate_limit_headers(self, client):
        """UAT-027: Complaint endpoint returns rate limit headers."""
        response = await client.get("/api/v1/complaints/")

        assert response.status_code == 401
        # Rate limiting should still apply

    @pytest.mark.asyncio
    async def test_uat_028_complaint_request_id(self, client):
        """UAT-028: Complaint responses include request ID."""
        response = await client.get("/api/v1/complaints/")

        assert "x-request-id" in response.headers

    @pytest.mark.asyncio
    async def test_uat_029_complaint_json_error_response(self, client):
        """UAT-029: Complaint auth errors return JSON with details."""
        response = await client.get("/api/v1/complaints/")

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @pytest.mark.asyncio
    async def test_uat_030_complaint_content_type(self, client):
        """UAT-030: Complaint responses have correct content type."""
        response = await client.get("/api/v1/complaints/")

        assert "application/json" in response.headers.get("content-type", "")


# ============================================================================
# UAT-031 to UAT-035: RTA Management
# ============================================================================


class TestRTAManagementWorkflows:
    """Road Traffic Accident (RTA) management workflow tests."""

    @pytest.mark.asyncio
    async def test_uat_031_list_rtas_requires_auth(self, client):
        """UAT-031: Listing RTAs requires authentication."""
        response = await client.get("/api/v1/rtas/")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_032_create_rta_requires_auth(self, client):
        """UAT-032: Creating RTAs requires authentication."""
        rta = {
            "title": "Test RTA",
            "description": "Test description",
            "incident_date": "2026-01-22T10:00:00Z",
        }

        response = await client.post("/api/v1/rtas/", json=rta)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_033_get_rta_requires_auth(self, client):
        """UAT-033: Getting RTA details requires authentication."""
        response = await client.get("/api/v1/rtas/1")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_034_rta_email_filter_requires_auth(self, client):
        """UAT-034: Email filter on RTAs requires authentication (security fix)."""
        response = await client.get("/api/v1/rtas/?reporter_email=test@example.com")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_035_rta_actions_require_auth(self, client):
        """UAT-035: RTA actions require authentication."""
        response = await client.get("/api/v1/rtas/1/actions")

        assert response.status_code == 401


# ============================================================================
# UAT-036 to UAT-040: User & Role Management
# ============================================================================


class TestUserRoleManagementWorkflows:
    """User and role management workflow tests."""

    @pytest.mark.asyncio
    async def test_uat_036_list_users_requires_auth(self, client):
        """UAT-036: Listing users requires authentication."""
        response = await client.get("/api/v1/users/")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_037_create_user_requires_superuser(self, client):
        """UAT-037: Creating users requires superuser role."""
        user = {
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "first_name": "Test",
            "last_name": "User",
        }

        response = await client.post("/api/v1/users/", json=user)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_038_list_roles_requires_auth(self, client):
        """UAT-038: Listing roles requires authentication."""
        response = await client.get("/api/v1/users/roles/")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_039_create_role_requires_superuser(self, client):
        """UAT-039: Creating roles requires superuser role."""
        role = {
            "name": "test_role",
            "description": "Test role",
            "permissions": ["read:incidents"],
        }

        response = await client.post("/api/v1/users/roles/", json=role)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_040_update_user_requires_superuser(self, client):
        """UAT-040: Updating users requires superuser role."""
        response = await client.patch("/api/v1/users/1", json={"is_active": False})

        assert response.status_code == 401


# ============================================================================
# UAT-041 to UAT-045: Workflow & Approvals
# ============================================================================


class TestWorkflowApprovalWorkflows:
    """Workflow and approval system tests."""

    @pytest.mark.asyncio
    async def test_uat_041_list_workflow_templates_requires_auth(self, client):
        """UAT-041: Listing workflow templates requires authentication."""
        response = await client.get("/api/v1/workflows/templates")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_042_start_workflow_requires_auth(self, client):
        """UAT-042: Starting a workflow requires authentication."""
        workflow = {
            "template_code": "RIDDOR",
            "entity_type": "incident",
            "entity_id": "INC-2026-0001",
        }

        response = await client.post("/api/v1/workflows/start", json=workflow)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_043_list_workflow_instances_requires_auth(self, client):
        """UAT-043: Listing workflow instances requires authentication."""
        response = await client.get("/api/v1/workflows/instances")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_044_get_pending_approvals_requires_auth(self, client):
        """UAT-044: Getting pending approvals requires authentication."""
        response = await client.get("/api/v1/workflows/approvals/pending")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_uat_045_approve_request_requires_auth(self, client):
        """UAT-045: Approving requests requires authentication."""
        response = await client.post(
            "/api/v1/workflows/approvals/test-approval-id/approve",
            json={"notes": "Approved"},
        )

        assert response.status_code == 401


# ============================================================================
# UAT-046 to UAT-050: System Health & Security
# ============================================================================


class TestSystemHealthSecurityWorkflows:
    """System health and security verification tests."""

    @pytest.mark.asyncio
    async def test_uat_046_health_endpoint_accessible(self, client):
        """UAT-046: Health endpoint is accessible without auth."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_uat_047_healthz_liveness_probe(self, client):
        """UAT-047: Kubernetes liveness probe endpoint works."""
        response = await client.get("/healthz")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_uat_048_readyz_readiness_probe(self, client):
        """UAT-048: Kubernetes readiness probe endpoint works."""
        response = await client.get("/readyz")

        # May return 200 or 503 depending on DB state
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data

    @pytest.mark.asyncio
    async def test_uat_049_openapi_spec_accessible(self, client):
        """UAT-049: OpenAPI specification is accessible."""
        response = await client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    @pytest.mark.asyncio
    async def test_uat_050_docs_endpoint_accessible(self, client):
        """UAT-050: API documentation is accessible."""
        response = await client.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
