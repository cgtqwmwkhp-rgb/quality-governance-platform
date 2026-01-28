"""
E2E Tests for Compliance Automation (Phase 4)

Tests cover:
- Regulatory change monitoring
- Gap analysis
- Certificate expiry tracking
- Scheduled audits
- Compliance scoring
- RIDDOR automation

PHASE 5 FIX (PR #104):
- GOVPLAT-001 RESOLVED: Fixed path + async conversion
- Changed /api/compliance-automation/* to /api/v1/compliance-automation/*
- Uses async_client + async_auth_headers from conftest.py
"""

import pytest


class TestRegulatoryMonitoring:
    """Test regulatory update monitoring."""

    @pytest.mark.asyncio
    async def test_list_regulatory_updates(self, async_client, async_auth_headers) -> None:
        """Test listing regulatory updates."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/regulatory-updates",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert "updates" in data
        assert "total" in data
        assert "unreviewed" in data

    @pytest.mark.asyncio
    async def test_filter_updates_by_source(self, async_client, async_auth_headers) -> None:
        """Test filtering updates by source."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/regulatory-updates?source=hse_uk",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        for update in data.get("updates", []):
            assert update["source"] == "hse_uk"

    @pytest.mark.asyncio
    async def test_filter_updates_by_impact(self, async_client, async_auth_headers) -> None:
        """Test filtering updates by impact level."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/regulatory-updates?impact=critical",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        for update in data.get("updates", []):
            assert update["impact"] == "critical"

    @pytest.mark.asyncio
    async def test_filter_unreviewed_updates(self, async_client, async_auth_headers) -> None:
        """Test filtering to unreviewed updates only."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/regulatory-updates?reviewed=false",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        for update in data.get("updates", []):
            assert update["is_reviewed"] is False

    @pytest.mark.asyncio
    async def test_mark_update_reviewed(self, async_client, async_auth_headers) -> None:
        """Test marking a regulatory update as reviewed."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.post(
            "/api/v1/compliance-automation/regulatory-updates/1/review",
            params={"requires_action": True, "action_notes": "Gap analysis required"},
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        result = response.json()
        assert result["is_reviewed"] is True
        assert result["requires_action"] is True


class TestGapAnalysis:
    """Test gap analysis functionality."""

    @pytest.mark.asyncio
    async def test_run_gap_analysis(self, async_client, async_auth_headers) -> None:
        """Test running automated gap analysis."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.post(
            "/api/v1/compliance-automation/gap-analysis/run",
            params={"regulatory_update_id": 1},
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        analysis = response.json()
        assert "id" in analysis
        assert "gaps" in analysis
        assert "total_gaps" in analysis
        assert "recommendations" in analysis
        assert "estimated_effort_hours" in analysis

    @pytest.mark.asyncio
    async def test_list_gap_analyses(self, async_client, async_auth_headers) -> None:
        """Test listing gap analyses."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/compliance-automation/gap-analyses", headers=async_auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "analyses" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_filter_gap_analyses_by_status(self, async_client, async_auth_headers) -> None:
        """Test filtering gap analyses by status."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/gap-analyses?status=pending",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        for analysis in data.get("analyses", []):
            assert analysis["status"] == "pending"


class TestCertificateTracking:
    """Test certificate expiry tracking."""

    @pytest.mark.asyncio
    async def test_list_certificates(self, async_client, async_auth_headers) -> None:
        """Test listing all certificates."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/compliance-automation/certificates", headers=async_auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "certificates" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_filter_certificates_by_type(self, async_client, async_auth_headers) -> None:
        """Test filtering certificates by type."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/certificates?certificate_type=training",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        for cert in data.get("certificates", []):
            assert cert["certificate_type"] == "training"

    @pytest.mark.asyncio
    async def test_filter_certificates_by_entity(self, async_client, async_auth_headers) -> None:
        """Test filtering certificates by entity type."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/certificates?entity_type=equipment",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        for cert in data.get("certificates", []):
            assert cert["entity_type"] == "equipment"

    @pytest.mark.asyncio
    async def test_filter_expiring_certificates(self, async_client, async_auth_headers) -> None:
        """Test filtering certificates expiring within days."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/certificates?expiring_within_days=60",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert "certificates" in data

    @pytest.mark.asyncio
    async def test_get_expiring_summary(self, async_client, async_auth_headers) -> None:
        """Test getting expiring certificates summary."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/certificates/expiring-summary",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        summary = response.json()
        assert "expired" in summary
        assert "expiring_7_days" in summary
        assert "expiring_30_days" in summary
        assert "expiring_90_days" in summary
        assert "by_type" in summary


class TestScheduledAudits:
    """Test scheduled audit management."""

    @pytest.mark.asyncio
    async def test_list_scheduled_audits(self, async_client, async_auth_headers) -> None:
        """Test listing scheduled audits."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/compliance-automation/scheduled-audits", headers=async_auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "audits" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_filter_overdue_audits(self, async_client, async_auth_headers) -> None:
        """Test filtering to overdue audits."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/scheduled-audits?overdue=true",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        for audit in data.get("audits", []):
            assert audit["status"] == "overdue"

    @pytest.mark.asyncio
    async def test_filter_upcoming_audits(self, async_client, async_auth_headers) -> None:
        """Test filtering audits due within days."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/scheduled-audits?upcoming_days=30",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert "audits" in data


class TestComplianceScoring:
    """Test compliance score calculation."""

    @pytest.mark.asyncio
    async def test_get_compliance_score(self, async_client, async_auth_headers) -> None:
        """Test getting current compliance score."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/compliance-automation/score", headers=async_auth_headers)
        assert response.status_code == 200

        score = response.json()
        assert "overall_score" in score
        assert "breakdown" in score
        assert "key_gaps" in score
        assert "recommendations" in score

    @pytest.mark.asyncio
    async def test_get_compliance_score_by_scope(self, async_client, async_auth_headers) -> None:
        """Test getting compliance score for specific scope."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/score?scope_type=department&scope_id=safety",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        score = response.json()
        assert score["scope_type"] == "department"

    @pytest.mark.asyncio
    async def test_get_compliance_trend(self, async_client, async_auth_headers) -> None:
        """Test getting compliance score trend."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get("/api/v1/compliance-automation/score/trend", headers=async_auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "trend" in data
        assert "period_months" in data
        assert len(data["trend"]) > 0

        # Verify trend data structure
        for point in data["trend"]:
            assert "period" in point
            assert "overall_score" in point

    @pytest.mark.asyncio
    async def test_get_compliance_trend_custom_period(self, async_client, async_auth_headers) -> None:
        """Test getting compliance trend for custom period."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.get(
            "/api/v1/compliance-automation/score/trend?months=6",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["period_months"] == 6
        assert len(data["trend"]) == 6


class TestRIDDORAutomation:
    """Test RIDDOR automation features."""

    @pytest.mark.asyncio
    async def test_check_riddor_required_death(self, async_client, async_auth_headers) -> None:
        """Test RIDDOR check for fatality."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        payload = {"fatality": True, "injury_type": "fatal"}

        response = await async_client.post(
            "/api/v1/compliance-automation/riddor/check",
            json=payload,
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        result = response.json()
        assert result["is_riddor"] is True
        assert "death" in result["riddor_types"]
        assert result["deadline"] is not None

    @pytest.mark.asyncio
    async def test_check_riddor_required_fracture(self, async_client, async_auth_headers) -> None:
        """Test RIDDOR check for specified injury."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        payload = {"fatality": False, "injury_type": "fracture", "days_off_work": 2}

        response = await async_client.post(
            "/api/v1/compliance-automation/riddor/check",
            json=payload,
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        result = response.json()
        assert result["is_riddor"] is True
        assert "specified_injury" in result["riddor_types"]

    @pytest.mark.asyncio
    async def test_check_riddor_required_over_7_days(self, async_client, async_auth_headers) -> None:
        """Test RIDDOR check for over 7 day incapacitation."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        payload = {"fatality": False, "injury_type": "sprain", "days_off_work": 10}

        response = await async_client.post(
            "/api/v1/compliance-automation/riddor/check",
            json=payload,
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        result = response.json()
        assert result["is_riddor"] is True
        assert "over_7_day_incapacitation" in result["riddor_types"]

    @pytest.mark.asyncio
    async def test_check_riddor_not_required(self, async_client, async_auth_headers) -> None:
        """Test RIDDOR check for non-reportable incident."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        payload = {"fatality": False, "injury_type": "minor_cut", "days_off_work": 1}

        response = await async_client.post(
            "/api/v1/compliance-automation/riddor/check",
            json=payload,
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        result = response.json()
        assert result["is_riddor"] is False
        assert len(result["riddor_types"]) == 0

    @pytest.mark.asyncio
    async def test_prepare_riddor_submission(self, async_client, async_auth_headers) -> None:
        """Test preparing RIDDOR submission data."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.post(
            "/api/v1/compliance-automation/riddor/prepare/123",
            params={"riddor_type": "specified_injury"},
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        result = response.json()
        assert result["incident_id"] == 123
        assert "submission_data" in result
        assert result["status"] == "ready_to_submit"

    @pytest.mark.asyncio
    async def test_submit_riddor(self, async_client, async_auth_headers) -> None:
        """Test submitting RIDDOR report."""
        if not async_auth_headers:
            pytest.skip("Auth required")

        response = await async_client.post(
            "/api/v1/compliance-automation/riddor/submit/123",
            headers=async_auth_headers,
        )
        assert response.status_code == 200

        result = response.json()
        assert result["status"] == "submitted"
        assert "hse_reference" in result
        assert result["hse_reference"].startswith("RIDDOR-")
