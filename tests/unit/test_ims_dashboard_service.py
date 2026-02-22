"""Unit tests for IMSDashboardService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.domain.services.ims_dashboard_service import IMSDashboardService


def _make_mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.scalar = AsyncMock(return_value=0)
    return db


class TestGetDashboard:
    @pytest.mark.asyncio
    async def test_get_dashboard_returns_all_sections(self):
        db = _make_mock_db()

        svc = IMSDashboardService(db)

        with (
            patch.object(
                svc,
                "get_standards_compliance",
                new_callable=AsyncMock,
                return_value=[{"standard_id": 1, "compliance_percentage": 80.0, "setup_required": False}],
            ),
            patch.object(
                svc,
                "get_isms_data",
                new_callable=AsyncMock,
                return_value={
                    "assets": {"total": 10, "critical": 2},
                    "controls": {"total": 50, "applicable": 40, "implemented": 30, "implementation_percentage": 75.0},
                    "risks": {"open": 5, "high_critical": 1},
                    "incidents": {"open": 2, "last_30_days": 3},
                    "suppliers": {"high_risk": 0},
                    "compliance_score": 75.0,
                    "domains": [],
                    "recent_incidents": [],
                },
            ),
            patch.object(
                svc,
                "get_uvdb_data",
                new_callable=AsyncMock,
                return_value={
                    "total_audits": 5,
                    "active_audits": 1,
                    "completed_audits": 4,
                    "average_score": 85.0,
                    "latest_score": 90.0,
                    "status": "active",
                },
            ),
            patch.object(
                svc,
                "get_planet_mark_data",
                new_callable=AsyncMock,
                return_value={
                    "status": "active",
                    "current_year": 2025,
                    "total_emissions": 100.0,
                    "certification_status": "certified",
                    "reduction_vs_previous": 5.0,
                },
            ),
            patch.object(
                svc,
                "get_compliance_coverage",
                new_callable=AsyncMock,
                return_value={
                    "total_clauses": 100,
                    "covered_clauses": 80,
                    "coverage_percentage": 80.0,
                    "gaps": 20,
                    "total_evidence_links": 200,
                },
            ),
            patch.object(svc, "get_audit_schedule", new_callable=AsyncMock, return_value=[]),
        ):
            dashboard = await svc.get_dashboard()

        assert "generated_at" in dashboard
        assert "standards" in dashboard
        assert "isms" in dashboard
        assert "uvdb" in dashboard
        assert "planet_mark" in dashboard
        assert "compliance_coverage" in dashboard
        assert "audit_schedule" in dashboard
        assert "overall_compliance" in dashboard
        assert dashboard["overall_compliance"] == 80.0


class TestGetStandardsCompliance:
    @pytest.mark.asyncio
    async def test_get_standards_compliance_empty_db(self):
        db = _make_mock_db()

        standards_result = MagicMock()
        standards_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=standards_result)

        svc = IMSDashboardService(db)
        scores = await svc.get_standards_compliance()

        assert scores == []
