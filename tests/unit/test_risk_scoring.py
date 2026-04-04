"""Tests for risk_scoring – RiskScoringService helpers and standalone helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.risk_scoring import RISK_MATRIX, RiskScoringService, calculate_risk_level


class TestCalculateRiskLevel:
    """Tests for the module-level calculate_risk_level function."""

    def test_low_risk(self):
        score, level, color = calculate_risk_level(1, 1)
        assert score == 1
        assert level == "very_low"

    def test_medium_risk(self):
        score, level, color = calculate_risk_level(3, 3)
        assert score == 9
        assert level == "medium"

    def test_high_risk(self):
        score, level, color = calculate_risk_level(4, 4)
        assert score == 16
        assert level == "high"

    def test_critical_risk(self):
        score, level, color = calculate_risk_level(5, 5)
        assert score == 25
        assert level == "critical"

    def test_returns_color_hex(self):
        _, _, color = calculate_risk_level(5, 5)
        assert color.startswith("#")
        assert len(color) == 7

    def test_score_equals_product(self):
        for likelihood in range(1, 6):
            for impact in range(1, 6):
                score, _, _ = calculate_risk_level(likelihood, impact)
                assert score == likelihood * impact

    def test_boundary_medium_to_high(self):
        _, level_9, _ = calculate_risk_level(3, 3)
        _, level_10, _ = calculate_risk_level(2, 5)
        assert level_9 == "medium"
        assert level_10 == "high"

    def test_out_of_range_returns_default(self):
        score, level, color = calculate_risk_level(6, 1)
        assert score == 6
        assert level == "medium"
        assert color == "#eab308"


class TestRiskMatrix:
    """Tests for the RISK_MATRIX constant."""

    def test_matrix_has_all_likelihood_rows(self):
        for likelihood in range(1, 6):
            assert likelihood in RISK_MATRIX

    def test_each_row_has_all_impacts(self):
        for likelihood in range(1, 6):
            for impact in range(1, 6):
                assert impact in RISK_MATRIX[likelihood]

    def test_matrix_values_are_tuples(self):
        for likelihood in range(1, 6):
            for impact in range(1, 6):
                val = RISK_MATRIX[likelihood][impact]
                assert isinstance(val, tuple)
                assert len(val) == 2

    def test_critical_only_at_high_scores(self):
        critical_cells = []
        for l in range(1, 6):
            for i in range(1, 6):
                level, _ = RISK_MATRIX[l][i]
                if level == "critical":
                    critical_cells.append((l, i))

        for l, i in critical_cells:
            assert l * i >= 16

    def test_very_low_only_at_lowest(self):
        for l in range(1, 6):
            for i in range(1, 6):
                level, _ = RISK_MATRIX[l][i]
                if level == "very_low":
                    assert l * i <= 1


class TestRiskScoringServiceCalculateRiskLevel:
    """Tests for the instance method _calculate_risk_level."""

    def setup_method(self):
        self.service = RiskScoringService(db=MagicMock())

    def test_negligible(self):
        assert self.service._calculate_risk_level(1) == "negligible"

    def test_low(self):
        assert self.service._calculate_risk_level(5) == "low"
        assert self.service._calculate_risk_level(9) == "low"

    def test_medium(self):
        assert self.service._calculate_risk_level(10) == "medium"
        assert self.service._calculate_risk_level(14) == "medium"

    def test_high(self):
        assert self.service._calculate_risk_level(15) == "high"
        assert self.service._calculate_risk_level(19) == "high"

    def test_critical(self):
        assert self.service._calculate_risk_level(20) == "critical"
        assert self.service._calculate_risk_level(25) == "critical"

    def test_zero_score(self):
        assert self.service._calculate_risk_level(0) == "negligible"

    def test_boundary_values(self):
        assert self.service._calculate_risk_level(4) == "negligible"
        assert self.service._calculate_risk_level(5) == "low"
        assert self.service._calculate_risk_level(10) == "medium"
        assert self.service._calculate_risk_level(15) == "high"
        assert self.service._calculate_risk_level(20) == "critical"


class TestSeverityImpactMapping:
    def test_critical_severity_gives_highest_adjustment(self):
        from src.domain.models.incident import IncidentSeverity

        assert RiskScoringService.SEVERITY_IMPACT[IncidentSeverity.CRITICAL] == 2

    def test_high_severity_gives_moderate_adjustment(self):
        from src.domain.models.incident import IncidentSeverity

        assert RiskScoringService.SEVERITY_IMPACT[IncidentSeverity.HIGH] == 1

    def test_medium_and_low_give_no_adjustment(self):
        from src.domain.models.incident import IncidentSeverity

        assert RiskScoringService.SEVERITY_IMPACT[IncidentSeverity.MEDIUM] == 0
        assert RiskScoringService.SEVERITY_IMPACT[IncidentSeverity.LOW] == 0
        assert RiskScoringService.SEVERITY_IMPACT[IncidentSeverity.NEGLIGIBLE] == 0


class TestNearMissVelocityThresholds:
    def test_velocity_thresholds_are_sensible(self):
        assert RiskScoringService.NEAR_MISS_VELOCITY_HIGH > RiskScoringService.NEAR_MISS_VELOCITY_MEDIUM
        assert RiskScoringService.NEAR_MISS_VELOCITY_MEDIUM > 0
