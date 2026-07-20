"""
E2E Tests for Compliance Automation (Phase 4)

Tests cover:
- Regulatory change monitoring
- Gap analysis
- Certificate expiry tracking
- Scheduled audits
- Compliance scoring
- RIDDOR automation
"""

from typing import Any

import pytest


@pytest.mark.phase34
class TestRegulatoryMonitoring:
    """Test regulatory update monitoring."""

    def test_list_regulatory_updates(self, auth_client: Any) -> None:
        """Test listing regulatory updates."""
        response = auth_client.get("/api/v1/compliance-automation/regulatory-updates")
        assert response.status_code == 200

        data = response.json()
        assert "updates" in data
        assert "total" in data
        assert "unreviewed" in data

    def test_filter_updates_by_source(self, auth_client: Any) -> None:
        """Test filtering updates by source."""
        response = auth_client.get("/api/v1/compliance-automation/regulatory-updates?source=hse_uk")
        assert response.status_code == 200

        data = response.json()
        for update in data.get("updates", []):
            assert update["source"] == "hse_uk"

    def test_filter_updates_by_impact(self, auth_client: Any) -> None:
        """Test filtering updates by impact level."""
        response = auth_client.get("/api/v1/compliance-automation/regulatory-updates?impact=critical")
        assert response.status_code == 200

        data = response.json()
        for update in data.get("updates", []):
            assert update["impact"] == "critical"

    def test_filter_unreviewed_updates(self, auth_client: Any) -> None:
        """Test filtering to unreviewed updates only."""
        response = auth_client.get("/api/v1/compliance-automation/regulatory-updates?reviewed=false")
        assert response.status_code == 200

        data = response.json()
        for update in data.get("updates", []):
            assert update["is_reviewed"] is False

    def test_mark_update_reviewed(self, auth_client: Any) -> None:
        """Test marking a regulatory update as reviewed."""
        response = auth_client.post(
            "/api/v1/compliance-automation/regulatory-updates/1/review",
            params={"requires_action": True, "action_notes": "Gap analysis required"},
        )
        assert response.status_code == 200

        result = response.json()
        assert result["is_reviewed"] is True
        assert result["requires_action"] is True


@pytest.mark.phase34
class TestGapAnalysis:
    """Test gap analysis functionality."""

    def test_run_gap_analysis(self, auth_client: Any) -> None:
        """Test running automated gap analysis."""
        response = auth_client.post(
            "/api/v1/compliance-automation/gap-analysis/run",
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
        response = auth_client.get("/api/v1/compliance-automation/gap-analyses")
        assert response.status_code == 200

        data = response.json()
        assert "analyses" in data
        assert "total" in data

    def test_filter_gap_analyses_by_status(self, auth_client: Any) -> None:
        """Test filtering gap analyses by status."""
        response = auth_client.get("/api/v1/compliance-automation/gap-analyses?status=pending")
        assert response.status_code == 200

        data = response.json()
        for analysis in data.get("analyses", []):
            assert analysis["status"] == "pending"


@pytest.mark.phase34
class TestCertificateTracking:
    """Test certificate expiry tracking."""

    def test_list_certificates(self, auth_client: Any) -> None:
        """Test listing all certificates."""
        response = auth_client.get("/api/v1/compliance-automation/certificates")
        assert response.status_code == 200

        data = response.json()
        assert "certificates" in data
        assert "total" in data

    def test_filter_certificates_by_type(self, auth_client: Any) -> None:
        """Test filtering certificates by type."""
        response = auth_client.get("/api/v1/compliance-automation/certificates?certificate_type=training")
        assert response.status_code == 200

        data = response.json()
        for cert in data.get("certificates", []):
            assert cert["certificate_type"] == "training"

    def test_filter_certificates_by_entity(self, auth_client: Any) -> None:
        """Test filtering certificates by entity type."""
        response = auth_client.get("/api/v1/compliance-automation/certificates?entity_type=equipment")
        assert response.status_code == 200

        data = response.json()
        for cert in data.get("certificates", []):
            assert cert["entity_type"] == "equipment"

    def test_filter_expiring_certificates(self, auth_client: Any) -> None:
        """Test filtering certificates expiring within days."""
        response = auth_client.get("/api/v1/compliance-automation/certificates?expiring_within_days=60")
        assert response.status_code == 200

        data = response.json()
        assert "certificates" in data

    def test_get_expiring_summary(self, auth_client: Any) -> None:
        """Test getting expiring certificates summary."""
        response = auth_client.get("/api/v1/compliance-automation/certificates/expiring-summary")
        assert response.status_code == 200

        summary = response.json()
        assert "expired" in summary
        assert "expiring_7_days" in summary
        assert "expiring_30_days" in summary
        assert "expiring_90_days" in summary
        assert "by_type" in summary

    def test_get_assurance_cert_shelf(self, auth_client: Any) -> None:
        """Test unified assurance certificate shelf aggregation."""
        response = auth_client.get("/api/v1/compliance-automation/certificates/shelf")
        assert response.status_code == 200

        payload = response.json()
        assert "items" in payload
        assert "total" in payload
        assert "summary" in payload
        assert "due_soon_days" in payload
        assert "valid" in payload["summary"]
        assert "due_soon" in payload["summary"]
        assert "expired" in payload["summary"]
        assert "by_scheme" in payload["summary"]

    def test_filter_assurance_cert_shelf_by_scheme(self, auth_client: Any) -> None:
        """Test shelf scheme filter."""
        response = auth_client.get("/api/v1/compliance-automation/certificates/shelf?scheme=planet_mark")
        assert response.status_code == 200
        for item in response.json().get("items", []):
            assert item["scheme"] == "planet_mark"


@pytest.mark.phase34
class TestScheduledAudits:
    """Test scheduled audit management."""

    def test_list_scheduled_audits(self, auth_client: Any) -> None:
        """Test listing scheduled audits."""
        response = auth_client.get("/api/v1/compliance-automation/scheduled-audits")
        assert response.status_code == 200

        data = response.json()
        assert "audits" in data
        assert "total" in data

    def test_filter_overdue_audits(self, auth_client: Any) -> None:
        """Test filtering to overdue audits."""
        response = auth_client.get("/api/v1/compliance-automation/scheduled-audits?overdue=true")
        assert response.status_code == 200

        data = response.json()
        for audit in data.get("audits", []):
            assert audit["status"] == "overdue"

    def test_filter_upcoming_audits(self, auth_client: Any) -> None:
        """Test filtering audits due within days."""
        response = auth_client.get("/api/v1/compliance-automation/scheduled-audits?upcoming_days=30")
        assert response.status_code == 200

        data = response.json()
        assert "audits" in data


@pytest.mark.phase34
class TestComplianceScoring:
    """Test compliance score calculation."""

    def test_get_compliance_score(self, auth_client: Any) -> None:
        """Test getting current compliance score."""
        response = auth_client.get("/api/v1/compliance-automation/score")
        assert response.status_code == 200

        score = response.json()
        assert "overall_score" in score
        assert "breakdown" in score
        assert "key_gaps" in score
        assert "recommendations" in score

    def test_get_compliance_score_by_scope(self, auth_client: Any) -> None:
        """Test getting compliance score for specific scope."""
        response = auth_client.get("/api/v1/compliance-automation/score?scope_type=department&scope_id=safety")
        assert response.status_code == 200

        score = response.json()
        assert score["scope_type"] == "department"

    def test_get_compliance_trend(self, auth_client: Any) -> None:
        """Test getting compliance score trend."""
        response = auth_client.get("/api/v1/compliance-automation/score/trend")
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
        response = auth_client.get("/api/v1/compliance-automation/score/trend?months=6")
        assert response.status_code == 200

        data = response.json()
        assert data["period_months"] == 6
        assert len(data["trend"]) == 6


@pytest.mark.phase34
class TestRIDDORAutomation:
    """Test RIDDOR automation features."""

    def test_check_riddor_required_death(self, auth_client: Any) -> None:
        """Test RIDDOR check for fatality."""
        payload = {"fatality": True, "injury_type": "fatal"}

        response = auth_client.post("/api/v1/compliance-automation/riddor/check", json=payload)
        assert response.status_code == 200

        result = response.json()
        assert result["is_riddor"] is True
        assert "death" in result["riddor_types"]
        assert result["deadline"] is not None

    def test_check_riddor_required_fracture(self, auth_client: Any) -> None:
        """Test RIDDOR check for specified injury."""
        payload = {"fatality": False, "injury_type": "fracture", "days_off_work": 2}

        response = auth_client.post("/api/v1/compliance-automation/riddor/check", json=payload)
        assert response.status_code == 200

        result = response.json()
        assert result["is_riddor"] is True
        assert "specified_injury" in result["riddor_types"]

    def test_check_riddor_required_over_7_days(self, auth_client: Any) -> None:
        """Test RIDDOR check for over 7 day incapacitation."""
        payload = {"fatality": False, "injury_type": "sprain", "days_off_work": 10}

        response = auth_client.post("/api/v1/compliance-automation/riddor/check", json=payload)
        assert response.status_code == 200

        result = response.json()
        assert result["is_riddor"] is True
        assert "over_7_day_incapacitation" in result["riddor_types"]

    def test_check_riddor_not_required(self, auth_client: Any) -> None:
        """Test RIDDOR check for non-reportable incident."""
        payload = {"fatality": False, "injury_type": "minor_cut", "days_off_work": 1}

        response = auth_client.post("/api/v1/compliance-automation/riddor/check", json=payload)
        assert response.status_code == 200

        result = response.json()
        assert result["is_riddor"] is False
        assert len(result["riddor_types"]) == 0

    def test_prepare_riddor_submission(self, auth_client: Any) -> None:
        """Test preparing and persisting a RIDDOR draft pack from an incident."""
        incident_resp = auth_client.post(
            "/api/v1/incidents/",
            json={
                "title": "CA-W1e RIDDOR prepare fracture",
                "description": "Specified injury for RIDDOR pack persistence",
                "incident_type": "injury",
                "severity": "high",
                "incident_date": "2026-07-10T09:00:00Z",
                "location": "Workshop",
            },
        )
        assert incident_resp.status_code in (200, 201), incident_resp.text
        incident_id = incident_resp.json()["id"]

        response = auth_client.post(
            f"/api/v1/compliance-automation/riddor/prepare/{incident_id}",
            params={"riddor_type": "specified_injury"},
        )
        assert response.status_code == 200, response.text

        result = response.json()
        assert result["incident_id"] == incident_id
        assert "submission_data" in result
        assert result["status"] == "draft_pack"
        assert result["persisted"] is True
        assert result["id"] is not None
        assert "HSE portal" in result["status_label"]

        listed = auth_client.get("/api/v1/compliance-automation/riddor/submissions")
        assert listed.status_code == 200
        submissions = listed.json().get("submissions", [])
        assert any(row.get("id") == result["id"] for row in submissions)

    def test_submit_riddor(self, auth_client: Any) -> None:
        """Test honest HSE-gateway stub against a persisted pack."""
        incident_resp = auth_client.post(
            "/api/v1/incidents/",
            json={
                "title": "CA-W1e RIDDOR submit stub",
                "description": "Pack then stub filing intent",
                "incident_type": "injury",
                "severity": "high",
                "incident_date": "2026-07-11T09:00:00Z",
                "location": "Yard",
            },
        )
        assert incident_resp.status_code in (200, 201), incident_resp.text
        incident_id = incident_resp.json()["id"]

        prep = auth_client.post(
            f"/api/v1/compliance-automation/riddor/prepare/{incident_id}",
            params={"riddor_type": "specified_injury"},
        )
        assert prep.status_code == 200, prep.text

        response = auth_client.post(f"/api/v1/compliance-automation/riddor/submit/{incident_id}")
        assert response.status_code == 200, response.text

        result = response.json()
        assert result["status"] == "stubbed"
        assert result.get("gateway") == "not_connected"
        assert result.get("persisted") is True
        assert "hse_reference" in result
        assert result["hse_reference"].startswith("QGP-RIDDOR-")
        assert result["submission_status"] == "awaiting_hse_filing"
