"""Tests for src.domain.services.risk_service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.risk_service import BowTieService, KRIService, RiskScoringEngine, RiskService

# ---------------------------------------------------------------------------
# RiskScoringEngine
# ---------------------------------------------------------------------------


class TestRiskScoringEngine:
    def test_calculate_score(self):
        assert RiskScoringEngine.calculate_score(1, 1) == 1
        assert RiskScoringEngine.calculate_score(5, 5) == 25
        assert RiskScoringEngine.calculate_score(3, 4) == 12

    def test_get_risk_level_low(self):
        assert RiskScoringEngine.get_risk_level(1) == "low"
        assert RiskScoringEngine.get_risk_level(4) == "low"

    def test_get_risk_level_medium(self):
        assert RiskScoringEngine.get_risk_level(5) == "medium"
        assert RiskScoringEngine.get_risk_level(9) == "medium"

    def test_get_risk_level_high(self):
        assert RiskScoringEngine.get_risk_level(10) == "high"
        assert RiskScoringEngine.get_risk_level(16) == "high"

    def test_get_risk_level_critical(self):
        assert RiskScoringEngine.get_risk_level(17) == "critical"
        assert RiskScoringEngine.get_risk_level(25) == "critical"

    def test_get_risk_color_green(self):
        assert RiskScoringEngine.get_risk_color(1) == "#22c55e"

    def test_get_risk_color_yellow(self):
        assert RiskScoringEngine.get_risk_color(5) == "#eab308"

    def test_get_risk_color_orange(self):
        assert RiskScoringEngine.get_risk_color(10) == "#f97316"

    def test_get_risk_color_red(self):
        assert RiskScoringEngine.get_risk_color(20) == "#ef4444"

    def test_generate_matrix_shape(self):
        matrix = RiskScoringEngine.generate_matrix()
        assert len(matrix) == 5
        assert all(len(row) == 5 for row in matrix)

    def test_generate_matrix_top_left_is_5x1(self):
        matrix = RiskScoringEngine.generate_matrix()
        top_left = matrix[0][0]
        assert top_left["likelihood"] == 5
        assert top_left["impact"] == 1
        assert top_left["score"] == 5

    def test_generate_matrix_bottom_right_is_1x5(self):
        matrix = RiskScoringEngine.generate_matrix()
        bottom_right = matrix[4][4]
        assert bottom_right["likelihood"] == 1
        assert bottom_right["impact"] == 5
        assert bottom_right["score"] == 5

    def test_generate_matrix_cells_have_all_keys(self):
        matrix = RiskScoringEngine.generate_matrix()
        cell = matrix[0][0]
        expected_keys = {"likelihood", "impact", "score", "level", "color", "likelihood_label", "impact_label"}
        assert set(cell.keys()) == expected_keys

    def test_likelihood_labels(self):
        assert RiskScoringEngine.LIKELIHOOD_LABELS[1] == "Rare"
        assert RiskScoringEngine.LIKELIHOOD_LABELS[5] == "Almost Certain"

    def test_impact_labels(self):
        assert RiskScoringEngine.IMPACT_LABELS[1] == "Insignificant"
        assert RiskScoringEngine.IMPACT_LABELS[5] == "Catastrophic"


# ---------------------------------------------------------------------------
# RiskService
# ---------------------------------------------------------------------------


class TestRiskService:
    @pytest.fixture
    def service(self):
        db = AsyncMock()
        return RiskService(db)

    @pytest.mark.asyncio
    async def test_create_risk_generates_reference(self, service):
        count_result = MagicMock()
        count_result.scalar_one.return_value = 5

        appetite_result = MagicMock()
        appetite_result.scalar_one_or_none.return_value = None

        service.db.execute = AsyncMock(side_effect=[count_result, appetite_result])
        service.db.refresh = AsyncMock()
        service._record_assessment = AsyncMock()

        created_kwargs = {}

        def capture_risk(**kwargs):
            created_kwargs.update(kwargs)
            mock = MagicMock()
            mock.review_frequency_days = 90
            for k, v in kwargs.items():
                setattr(mock, k, v)
            return mock

        with patch("src.domain.services.risk_service.EnterpriseRisk", side_effect=capture_risk):
            risk = await service.create_risk({"title": "Test", "tenant_id": 1})

        assert created_kwargs["reference"] == "RISK-0006"

    @pytest.mark.asyncio
    async def test_update_risk_assessment_not_found(self, service):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        service.db.execute.return_value = result

        with pytest.raises(ValueError, match="not found"):
            await service.update_risk_assessment(999, {})

    @pytest.mark.asyncio
    async def test_update_risk_assessment_recalculates_scores(self, service):
        risk = MagicMock(
            inherent_likelihood=3,
            inherent_impact=3,
            residual_likelihood=2,
            residual_impact=2,
            appetite_threshold=12,
            review_frequency_days=90,
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = risk
        service.db.execute.return_value = result
        service.db.refresh = AsyncMock()
        service._record_assessment = AsyncMock()

        updated = await service.update_risk_assessment(1, {"inherent_likelihood": 5, "inherent_impact": 4})
        assert updated.inherent_likelihood == 5
        assert updated.inherent_impact == 4

    @pytest.mark.asyncio
    async def test_get_heat_map_data_empty(self, service):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        service.db.execute.return_value = result

        data = await service.get_heat_map_data(tenant_id=1)
        assert data["summary"]["total_risks"] == 0
        assert len(data["matrix"]) == 5

    @pytest.mark.asyncio
    async def test_get_risk_trends_empty(self, service):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        service.db.execute.return_value = result

        trends = await service.get_risk_trends(tenant_id=1)
        assert trends == []

    @pytest.mark.asyncio
    async def test_forecast_returns_empty_with_insufficient_data(self, service):
        service.get_risk_trends = AsyncMock(return_value=[{"avg_residual": 10, "month": "2026-01"}])
        forecast = await service.forecast_risk_trends(tenant_id=1)
        assert forecast == []

    @pytest.mark.asyncio
    async def test_forecast_returns_predictions(self, service):
        historical = [{"avg_residual": 10, "month": f"2025-{i:02d}"} for i in range(1, 7)]
        service.get_risk_trends = AsyncMock(return_value=historical)

        forecast = await service.forecast_risk_trends(months_ahead=3, tenant_id=1)
        assert len(forecast) == 3
        assert all(f["is_forecast"] for f in forecast)
        assert all(0 <= f["predicted_residual"] <= 25 for f in forecast)


# ---------------------------------------------------------------------------
# KRIService
# ---------------------------------------------------------------------------


class TestKRIService:
    @pytest.fixture
    def service(self):
        return KRIService(AsyncMock())

    @pytest.mark.asyncio
    async def test_update_kri_not_found(self, service):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        service.db.execute.return_value = result

        with pytest.raises(ValueError, match="not found"):
            await service.update_kri_value(999, 42.0)

    @pytest.mark.asyncio
    async def test_update_kri_above_red(self, service):
        kri = MagicMock(
            threshold_direction="above",
            red_threshold=80,
            amber_threshold=60,
            green_threshold=40,
            historical_values=None,
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = kri
        service.db.execute.return_value = result
        service.db.refresh = AsyncMock()

        updated = await service.update_kri_value(1, 90.0)
        assert updated.current_status == "red"
        assert updated.current_value == 90.0

    @pytest.mark.asyncio
    async def test_update_kri_above_amber(self, service):
        kri = MagicMock(
            threshold_direction="above",
            red_threshold=80,
            amber_threshold=60,
            green_threshold=40,
            historical_values=[],
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = kri
        service.db.execute.return_value = result
        service.db.refresh = AsyncMock()

        updated = await service.update_kri_value(1, 70.0)
        assert updated.current_status == "amber"

    @pytest.mark.asyncio
    async def test_update_kri_above_green(self, service):
        kri = MagicMock(
            threshold_direction="above",
            red_threshold=80,
            amber_threshold=60,
            green_threshold=40,
            historical_values=[],
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = kri
        service.db.execute.return_value = result
        service.db.refresh = AsyncMock()

        updated = await service.update_kri_value(1, 30.0)
        assert updated.current_status == "green"

    @pytest.mark.asyncio
    async def test_update_kri_below_red(self, service):
        kri = MagicMock(
            threshold_direction="below",
            red_threshold=20,
            amber_threshold=40,
            green_threshold=60,
            historical_values=[],
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = kri
        service.db.execute.return_value = result
        service.db.refresh = AsyncMock()

        updated = await service.update_kri_value(1, 10.0)
        assert updated.current_status == "red"

    def test_calculate_trend_stable(self, service):
        assert service._calculate_trend([{"value": 10}, {"value": 10}]) == "stable"

    def test_calculate_trend_increasing(self, service):
        assert service._calculate_trend([{"value": 10}, {"value": 15}, {"value": 20}]) == "increasing"

    def test_calculate_trend_decreasing(self, service):
        assert service._calculate_trend([{"value": 20}, {"value": 15}, {"value": 5}]) == "decreasing"

    def test_calculate_trend_single_entry(self, service):
        assert service._calculate_trend([{"value": 10}]) == "stable"
