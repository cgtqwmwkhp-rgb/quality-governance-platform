"""
E2E Tests for Compliance Automation (Phase 4)

Tests cover:
- Regulatory change monitoring
- Gap analysis
- Certificate expiry tracking
- Scheduled audits
- Compliance scoring
- RIDDOR automation

QUARANTINE STATUS: All tests in this file are quarantined.
See tests/smoke/QUARANTINE_POLICY.md for details.

Quarantine Date: 2026-01-21
Expiry Date: 2026-03-23
Issue: GOVPLAT-001
Reason: Phase 4 Compliance Automation features not fully implemented; endpoints return 404.
"""

from typing import Any

import pytest

# Quarantine marker - xfail all tests in this module (run but don't block CI)
pytestmark = pytest.mark.xfail(
    reason="QUARANTINED: Phase 4 Compliance Automation features incomplete. See QUARANTINE_POLICY.md. Expires: 2026-03-23",
    strict=False,
)


class TestRegulatoryMonitoring:
    """Test regulatory update monitoring."""

    def test_list_regulatory_updates(self, auth_client: Any) -> None:
        """Test listing regulatory updates."""
        response = auth_client.get("/api/compliance-automation/regulatory-updates")
        assert response.status_code == 200

        data = response.json()
        assert "updates" in data
        assert "total" in data
        assert "unreviewed" in data

    def test_filter_updates_by_source(self, auth_client: Any) -> None:
        """Test filtering updates by source."""
        response = auth_client.get("/api/compliance-automation/regulatory-updates?source=hse_uk")
        assert response.status_code == 200

        data = response.json()
        for update in data.get("updates", []):
            assert update["source"] == "hse_uk"

    def test_filter_updates_by_impact(self, auth_client: Any) -> None:
        """Test filtering updates by impact level."""
        response = auth_client.get("/api/compliance-automation/regulatory-updates?impact=critical")
        assert response.status_code == 200

        data = response.json()
        for update in data.get("updates", []):
            assert update["impact"] == "critical"

    def test_filter_unreviewed_updates(self, auth_client: Any) -> None:
        """Test filtering to unreviewed updates only."""
        response = auth_client.get("/api/compliance-automation/regulatory-updates?reviewed=false")
        assert response.status_code == 200

        data = response.json()
        for update in data.get("updates", []):
            assert update["is_reviewed"] is False

    def test_mark_update_reviewed(self, auth_client: Any) -> None:
        """Test marking a regulatory update as reviewed."""
        response = auth_client.post(
            "/api/compliance-automation/regulatory-updates/1/review",
            params={"requires_action": True, "action_notes": "Gap analysis required"},
        )
        assert response.status_code == 200

        result = response.json()
        assert result["is_reviewed"] is True
        assert result["requires_action"] is True


class TestGapAnalysis:
    """Test gap analysis functionality."""

    def test_run_gap_analysis(self, auth_client: Any) -> None:
        """Test running automated gap analysis."""
        response = auth_client.post(
            "/api/compliance-automation/gap-analysis/run",
            params={"regulatory_update_id": 1},
        )
        assert response.status_code == 200

        analysis = response.json()
        assert "id" in analysis
        assert "gaps" in analysis
        assert "total_gaps" in analysis
        assert "recommendations" in analysis
        assert "estimated_effort_hours" in analysis

    def test_list_gap_analyses(self, auth_client: Any) -> None:
        """Test listing gap analyses."""
        response = auth_client.get("/api/compliance-automation/gap-analyses")
        assert response.status_code == 200

        data = response.json()
        assert "analyses" in data
        assert "total" in data

    def test_filter_gap_analyses_by_status(self, auth_client: Any) -> None:
        """Test filtering gap analyses by status."""
        response = auth_client.get("/api/compliance-automation/gap-analyses?status=pending")
        assert response.status_code == 200

        data = response.json()
        for analysis in data.get("analyses", []):
            assert analysis["status"] == "pending"


class TestCertificateTracking:
    """Test certificate expiry tracking."""

    def test_list_certificates(self, auth_client: Any) -> None:
        """Test listing all certificates."""
        response = auth_client.get("/api/compliance-automation/certificates")
        assert response.status_code == 200

        data = response.json()
        assert "certificates" in data
        assert "total" in data

    def test_filter_certificates_by_type(self, auth_client: Any) -> None:
        """Test filtering certificates by type."""
        response = auth_client.get("/api/compliance-automation/certificates?certificate_type=training")
        assert response.status_code == 200

        data = response.json()
        for cert in data.get("certificates", []):
            assert cert["certificate_type"] == "training"

    def test_filter_certificates_by_entity(self, auth_client: Any) -> None:
        """Test filtering certificates by entity type."""
        response = auth_client.get("/api/compliance-automation/certificates?entity_type=equipment")
        assert response.status_code == 200

        data = response.json()
        for cert in data.get("certificates", []):
            assert cert["entity_type"] == "equipment"

    def test_filter_expiring_certificates(self, auth_client: Any) -> None:
        """Test filtering certificates expiring within days."""
        response = auth_client.get("/api/compliance-automation/certificates?expiring_within_days=60")
        assert response.status_code == 200

        data = response.json()
        assert "certificates" in data

    def test_get_expiring_summary(self, auth_client: Any) -> None:
        """Test getting expiring certificates summary."""
        response = auth_client.get("/api/compliance-automation/certificates/expiring-summary")
        assert response.status_code == 200

        summary = response.json()
        assert "expired" in summary
        assert "expiring_7_days" in summary
        assert "expiring_30_days" in summary
        assert "expiring_90_days" in summary
        assert "by_type" in summary


class TestScheduledAudits:
    """Test scheduled audit management."""

    def test_list_scheduled_audits(self, auth_client: Any) -> None:
        """Test listing scheduled audits."""
        response = auth_client.get("/api/compliance-automation/scheduled-audits")
        assert response.status_code == 200

        data = response.json()
        assert "audits" in data
        assert "total" in data

    def test_filter_overdue_audits(self, auth_client: Any) -> None:
        """Test filtering to overdue audits."""
        response = auth_client.get("/api/compliance-automation/scheduled-audits?overdue=true")
        assert response.status_code == 200

        data = response.json()
        for audit in data.get("audits", []):
            assert audit["status"] == "overdue"

    def test_filter_upcoming_audits(self, auth_client: Any) -> None:
        """Test filtering audits due within days."""
        response = auth_client.get("/api/compliance-automation/scheduled-audits?upcoming_days=30")
        assert response.status_code == 200

        data = response.json()
        assert "audits" in data


class TestComplianceScoring:
    """Test compliance score calculation."""

    def test_get_compliance_score(self, auth_client: Any) -> None:
        """Test getting current compliance score."""
        response = auth_client.get("/api/compliance-automation/score")
        assert response.status_code == 200

        score = response.json()
        assert "overall_score" in score
        assert "breakdown" in score
        assert "key_gaps" in score
        assert "recommendations" in score

    def test_get_compliance_score_by_scope(self, auth_client: Any) -> None:
        """Test getting compliance score for specific scope."""
        response = auth_client.get("/api/compliance-automation/score?scope_type=department&scope_id=safety")
        assert response.status_code == 200

        score = response.json()
        assert score["scope_type"] == "department"

    def test_get_compliance_trend(self, auth_client: Any) -> None:
        """Test getting compliance score trend."""
        response = auth_client.get("/api/compliance-automation/score/trend")
        assert response.status_code == 200

        data = response.json()
        assert "trend" in data
        assert "period_months" in data
        assert len(data["trend"]) > 0

        # Verify trend data structure
        for point in data["trend"]:
            assert "period" in point
            assert "overall_score" in point

    def test_get_compliance_trend_custom_period(self, auth_client: Any) -> None:
        """Test getting compliance trend for custom period."""
        response = auth_client.get("/api/compliance-automation/score/trend?months=6")
        assert response.status_code == 200

        data = response.json()
        assert data["period_months"] == 6
        assert len(data["trend"]) == 6


class TestRIDDORAutomation:
    """Test RIDDOR automation features."""

    def test_check_riddor_required_death(self, auth_client: Any) -> None:
        """Test RIDDOR check for fatality."""
        payload = {"fatality": True, "injury_type": "fatal"}

        response = auth_client.post("/api/compliance-automation/riddor/check", json=payload)
        assert response.status_code == 200

        result = response.json()
        assert result["is_riddor"] is True
        assert "death" in result["riddor_types"]
        assert result["deadline"] is not None

    def test_check_riddor_required_fracture(self, auth_client: Any) -> None:
        """Test RIDDOR check for specified injury."""
        payload = {"fatality": False, "injury_type": "fracture", "days_off_work": 2}

        response = auth_client.post("/api/compliance-automation/riddor/check", json=payload)
        assert response.status_code == 200

        result = response.json()
        assert result["is_riddor"] is True
        assert "specified_injury" in result["riddor_types"]

    def test_check_riddor_required_over_7_days(self, auth_client: Any) -> None:
        """Test RIDDOR check for over 7 day incapacitation."""
        payload = {"fatality": False, "injury_type": "sprain", "days_off_work": 10}

        response = auth_client.post("/api/compliance-automation/riddor/check", json=payload)
        assert response.status_code == 200

        result = response.json()
        assert result["is_riddor"] is True
        assert "over_7_day_incapacitation" in result["riddor_types"]

    def test_check_riddor_not_required(self, auth_client: Any) -> None:
        """Test RIDDOR check for non-reportable incident."""
        payload = {"fatality": False, "injury_type": "minor_cut", "days_off_work": 1}

        response = auth_client.post("/api/compliance-automation/riddor/check", json=payload)
        assert response.status_code == 200

        result = response.json()
        assert result["is_riddor"] is False
        assert len(result["riddor_types"]) == 0

    def test_prepare_riddor_submission(self, auth_client: Any) -> None:
        """Test preparing RIDDOR submission data."""
        response = auth_client.post(
            "/api/compliance-automation/riddor/prepare/123",
            params={"riddor_type": "specified_injury"},
        )
        assert response.status_code == 200

        result = response.json()
        assert result["incident_id"] == 123
        assert "submission_data" in result
        assert result["status"] == "ready_to_submit"

    def test_submit_riddor(self, auth_client: Any) -> None:
        """Test submitting RIDDOR report."""
        response = auth_client.post("/api/compliance-automation/riddor/submit/123")
        assert response.status_code == 200

        result = response.json()
        assert result["status"] == "submitted"
        assert "hse_reference" in result
        assert result["hse_reference"].startswith("RIDDOR-")
