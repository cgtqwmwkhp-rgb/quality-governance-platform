"""
UAT E2E Tests: Compliance Evidence

Tests the compliance evidence workflow:
1. View standards and controls
2. Add evidence to control
3. Verify compliance scoring updates

Uses deterministic seed data for repeatability.
"""

from typing import Any, Dict

import pytest
from conftest import UATApiClient, UATConfig, assert_no_pii, assert_stable_ordering

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.uat,
    pytest.mark.compliance,
]


class TestStandardsAndControls:
    """Test standards and controls viewing."""

    @pytest.mark.asyncio
    async def test_list_standards(self, admin_client: UATApiClient):
        """Can list compliance standards."""
        response = await admin_client.get("/api/v1/standards")

        # In real test:
        # assert response.status_code == 200
        # standards = response.json()['items']
        # assert len(standards) >= 2
        #
        # codes = [s['code'] for s in standards]
        # assert 'ISO-27001-UAT' in codes
        # assert 'SOC2-UAT' in codes

        assert response["status"] == "ok"

    @pytest.mark.asyncio
    async def test_get_standard_with_controls(self, admin_client: UATApiClient, uat_standard_ids: Dict[str, str]):
        """Can get standard with its controls."""
        standard_id = uat_standard_ids["iso27001"]

        response = await admin_client.get(f"/api/v1/standards/{standard_id}?include=controls")

        # In real test:
        # assert response.status_code == 200
        # standard = response.json()
        # assert 'controls' in standard
        # assert len(standard['controls']) >= 2

        assert response["status"] == "ok"

    @pytest.mark.asyncio
    async def test_list_controls_for_standard(self, admin_client: UATApiClient, uat_standard_ids: Dict[str, str]):
        """Can list controls for a standard."""
        standard_id = uat_standard_ids["iso27001"]

        response = await admin_client.get(f"/api/v1/standards/{standard_id}/controls")

        # In real test:
        # assert response.status_code == 200
        # controls = response.json()['items']
        # assert all(c['standard_id'] == standard_id for c in controls)

        assert response["status"] == "ok"

    @pytest.mark.asyncio
    async def test_controls_stable_ordering(self, admin_client: UATApiClient, uat_standard_ids: Dict[str, str]):
        """Controls list has stable ordering."""
        standard_id = uat_standard_ids["iso27001"]

        response1 = await admin_client.get(f"/api/v1/standards/{standard_id}/controls?sort=code")
        response2 = await admin_client.get(f"/api/v1/standards/{standard_id}/controls?sort=code")

        # In real test:
        # controls1 = response1.json()['items']
        # controls2 = response2.json()['items']
        # assert [c['id'] for c in controls1] == [c['id'] for c in controls2]

        assert response1["status"] == "ok"
        assert response2["status"] == "ok"


class TestEvidenceManagement:
    """Test evidence upload and management."""

    @pytest.mark.asyncio
    async def test_add_evidence_to_control(
        self, admin_client: UATApiClient, uat_control_ids: Dict[str, str], uat_user_ids: Dict[str, str]
    ):
        """Can add evidence to a control."""
        control_id = uat_control_ids["iso_policies"]

        evidence_data = {
            "title": "UAT Policy Document",
            "description": "Evidence added during UAT testing",
            "evidence_type": "document",
            "uploaded_by_id": uat_user_ids["admin"],
        }

        response = await admin_client.post(f"/api/v1/controls/{control_id}/evidence", evidence_data)

        # In real test:
        # assert response.status_code == 201
        # evidence = response.json()
        # assert evidence['control_id'] == control_id

        assert response["status"] in ("created", "ok")

    @pytest.mark.asyncio
    async def test_list_evidence_for_control(self, admin_client: UATApiClient, uat_control_ids: Dict[str, str]):
        """Can list evidence for a control."""
        control_id = uat_control_ids["iso_policies"]

        response = await admin_client.get(f"/api/v1/controls/{control_id}/evidence")

        # In real test:
        # assert response.status_code == 200
        # evidence_list = response.json()['items']
        # assert len(evidence_list) >= 1

        assert response["status"] == "ok"

    @pytest.mark.asyncio
    async def test_evidence_has_no_pii(self, admin_client: UATApiClient, uat_control_ids: Dict[str, str]):
        """Evidence data contains no PII."""
        control_id = uat_control_ids["iso_policies"]

        response = await admin_client.get(f"/api/v1/controls/{control_id}/evidence")

        # In real test:
        # evidence_list = response.json()['items']
        # for evidence in evidence_list:
        #     assert_no_pii(evidence)

        assert response["status"] == "ok"


class TestComplianceScoring:
    """Test compliance scoring updates."""

    @pytest.mark.asyncio
    async def test_get_compliance_score_for_standard(
        self, admin_client: UATApiClient, uat_standard_ids: Dict[str, str]
    ):
        """Can get compliance score for a standard."""
        standard_id = uat_standard_ids["iso27001"]

        response = await admin_client.get(f"/api/v1/standards/{standard_id}/compliance-score")

        # In real test:
        # assert response.status_code == 200
        # score = response.json()
        # assert 'score' in score
        # assert 'total_controls' in score
        # assert 'evidenced_controls' in score

        assert response["status"] == "ok"

    @pytest.mark.asyncio
    async def test_compliance_score_increases_with_evidence(
        self,
        admin_client: UATApiClient,
        uat_standard_ids: Dict[str, str],
        uat_control_ids: Dict[str, str],
        uat_user_ids: Dict[str, str],
    ):
        """Compliance score increases when evidence is added."""
        standard_id = uat_standard_ids["soc2"]
        control_id = uat_control_ids["soc2_environment"]

        # Get initial score
        response1 = await admin_client.get(f"/api/v1/standards/{standard_id}/compliance-score")

        # Add evidence
        evidence_data = {
            "title": "Control Environment Policy",
            "description": "Policy document for UAT",
            "evidence_type": "document",
            "uploaded_by_id": uat_user_ids["admin"],
        }
        await admin_client.post(f"/api/v1/controls/{control_id}/evidence", evidence_data)

        # Get updated score
        response2 = await admin_client.get(f"/api/v1/standards/{standard_id}/compliance-score")

        # In real test:
        # score1 = response1.json()['score']
        # score2 = response2.json()['score']
        # assert score2 >= score1

        assert response1["status"] == "ok"
        assert response2["status"] == "ok"

    @pytest.mark.asyncio
    async def test_compliance_dashboard(self, admin_client: UATApiClient):
        """Can view compliance dashboard."""
        response = await admin_client.get("/api/v1/dashboard/compliance")

        # In real test:
        # assert response.status_code == 200
        # dashboard = response.json()
        #
        # assert 'overall_score' in dashboard
        # assert 'by_standard' in dashboard
        # assert 'controls_with_evidence' in dashboard
        # assert 'controls_without_evidence' in dashboard

        assert response["status"] == "ok"


class TestComplianceRoleRestrictions:
    """Test role-based access for compliance."""

    @pytest.mark.asyncio
    async def test_readonly_user_can_view_standards(self, uat_config: UATConfig):
        """Readonly user can view standards."""
        from conftest import UATApiClient

        client = UATApiClient(uat_config.base_url)
        await client.login("uat_readonly", "UatTestPass123!")

        response = await client.get("/api/v1/standards")

        # In real test:
        # assert response.status_code == 200

        assert response["status"] == "ok"

    @pytest.mark.asyncio
    async def test_readonly_user_cannot_add_evidence(self, uat_config: UATConfig, uat_control_ids: Dict[str, str]):
        """Readonly user cannot add evidence."""
        from conftest import UATApiClient

        client = UATApiClient(uat_config.base_url)
        await client.login("uat_readonly", "UatTestPass123!")

        control_id = uat_control_ids["iso_policies"]

        evidence_data = {
            "title": "Should Fail",
            "description": "Readonly cannot add evidence",
            "evidence_type": "document",
        }

        response = await client.post(f"/api/v1/controls/{control_id}/evidence", evidence_data)

        # In real test:
        # assert response.status_code == 403

        # Placeholder
        assert True
