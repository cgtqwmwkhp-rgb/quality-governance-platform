"""Tests for src.domain.services.planet_mark_service (pure calculation methods)."""

from unittest.mock import MagicMock

import pytest

from src.domain.services.planet_mark_service import (
    DATA_QUALITY_CRITERIA,
    EMISSION_FACTORS,
    PlanetMarkService,
    _get_entity,
)

# ---------------------------------------------------------------------------
# get_emission_factor
# ---------------------------------------------------------------------------


class TestGetEmissionFactor:
    def test_known_diesel(self):
        ef = PlanetMarkService.get_emission_factor("diesel_litres")
        assert ef["factor"] == 2.51229
        assert ef["unit"] == "kgCO2e/litre"
        assert "DEFRA" in ef["source"]

    def test_known_petrol(self):
        ef = PlanetMarkService.get_emission_factor("petrol_litres")
        assert ef["factor"] == 2.16802

    def test_known_electricity(self):
        ef = PlanetMarkService.get_emission_factor("electricity_kwh_uk")
        assert ef["factor"] == 0.20705

    def test_unknown_returns_zero(self):
        ef = PlanetMarkService.get_emission_factor("unknown_fuel")
        assert ef["factor"] == 0
        assert ef["unit"] == ""


# ---------------------------------------------------------------------------
# calculate_co2e
# ---------------------------------------------------------------------------


class TestCalculateCO2e:
    def test_diesel_100_litres(self):
        co2e_kg, co2e_t, ef = PlanetMarkService.calculate_co2e(100, "diesel_litres")
        assert co2e_kg == pytest.approx(251.229, rel=1e-3)
        assert co2e_t == pytest.approx(0.251229, rel=1e-3)

    def test_zero_value(self):
        co2e_kg, co2e_t, _ = PlanetMarkService.calculate_co2e(0, "diesel_litres")
        assert co2e_kg == 0.0
        assert co2e_t == 0.0

    def test_unknown_type_gives_zero(self):
        co2e_kg, co2e_t, ef = PlanetMarkService.calculate_co2e(500, "magic_fuel")
        assert co2e_kg == 0.0
        assert co2e_t == 0.0

    def test_natural_gas(self):
        co2e_kg, _, _ = PlanetMarkService.calculate_co2e(1000, "natural_gas_kwh")
        assert co2e_kg == pytest.approx(182.54, rel=1e-2)


# ---------------------------------------------------------------------------
# get_data_quality_score
# ---------------------------------------------------------------------------


class TestGetDataQualityScore:
    def test_actual(self):
        assert PlanetMarkService.get_data_quality_score("actual") == 4

    def test_calculated(self):
        assert PlanetMarkService.get_data_quality_score("calculated") == 3

    def test_estimated(self):
        assert PlanetMarkService.get_data_quality_score("estimated") == 2

    def test_extrapolated(self):
        assert PlanetMarkService.get_data_quality_score("extrapolated") == 1

    def test_missing(self):
        assert PlanetMarkService.get_data_quality_score("missing") == 0

    def test_unknown_defaults_to_estimated(self):
        assert PlanetMarkService.get_data_quality_score("???") == 2


# ---------------------------------------------------------------------------
# calculate_scope_quality
# ---------------------------------------------------------------------------


class TestCalculateScopeQuality:
    def test_empty_sources(self):
        result = PlanetMarkService.calculate_scope_quality([])
        assert result["score"] == 0
        assert result["actual_pct"] == 0
        assert "No data recorded" in result["recommendations"]

    def test_all_actual(self):
        source = MagicMock(co2e_tonnes=10, data_quality_score=4, data_quality_level="actual")
        result = PlanetMarkService.calculate_scope_quality([source])
        assert result["actual_pct"] == 100.0
        assert result["source_count"] == 1

    def test_mixed_quality_recommends_improvements(self):
        s1 = MagicMock(co2e_tonnes=5, data_quality_score=2, data_quality_level="estimated")
        s2 = MagicMock(co2e_tonnes=5, data_quality_score=1, data_quality_level="extrapolated")
        result = PlanetMarkService.calculate_scope_quality([s1, s2])
        assert result["actual_pct"] == 0
        assert any("extrapolated" in r.lower() for r in result["recommendations"])

    def test_good_quality_says_good(self):
        sources = [MagicMock(co2e_tonnes=10, data_quality_score=4, data_quality_level="actual") for _ in range(5)]
        result = PlanetMarkService.calculate_scope_quality(sources)
        assert "Data quality is good" in result["recommendations"]


# ---------------------------------------------------------------------------
# calculate_overall_data_quality
# ---------------------------------------------------------------------------


class TestCalculateOverallDataQuality:
    def test_perfect_scores(self):
        assert PlanetMarkService.calculate_overall_data_quality(16, 16, 16) == 16

    def test_zero_scores(self):
        assert PlanetMarkService.calculate_overall_data_quality(0, 0, 0) == 0

    def test_mixed_scores(self):
        result = PlanetMarkService.calculate_overall_data_quality(12, 8, 4)
        assert result == 8


# ---------------------------------------------------------------------------
# calculate_avg_quality
# ---------------------------------------------------------------------------


class TestCalculateAvgQuality:
    def test_empty(self):
        assert PlanetMarkService.calculate_avg_quality([]) == 0

    def test_single_source(self):
        s = MagicMock(data_quality_score=3)
        assert PlanetMarkService.calculate_avg_quality([s]) == 12

    def test_multiple_sources(self):
        s1 = MagicMock(data_quality_score=2)
        s2 = MagicMock(data_quality_score=4)
        result = PlanetMarkService.calculate_avg_quality([s1, s2])
        assert result == 12  # (2+4)/2 * 4 = 12


# ---------------------------------------------------------------------------
# calculate_fleet_co2e
# ---------------------------------------------------------------------------


class TestCalculateFleetCO2e:
    def test_diesel(self):
        co2e_kg, ef = PlanetMarkService.calculate_fleet_co2e(100, "diesel")
        assert co2e_kg == pytest.approx(251.229, rel=1e-3)
        assert ef["source"] == "DEFRA 2024"

    def test_petrol(self):
        co2e_kg, ef = PlanetMarkService.calculate_fleet_co2e(100, "petrol")
        assert co2e_kg == pytest.approx(216.802, rel=1e-3)

    def test_unknown_fuel_falls_back_to_diesel(self):
        co2e_kg, ef = PlanetMarkService.calculate_fleet_co2e(100, "hydrogen")
        assert co2e_kg == pytest.approx(251.229, rel=1e-3)


# ---------------------------------------------------------------------------
# calculate_fuel_efficiency
# ---------------------------------------------------------------------------


class TestCalculateFuelEfficiency:
    def test_normal(self):
        result = PlanetMarkService.calculate_fuel_efficiency(50, 500)
        assert result == pytest.approx(10.0)

    def test_zero_mileage_returns_none(self):
        assert PlanetMarkService.calculate_fuel_efficiency(50, 0) is None

    def test_none_mileage_returns_none(self):
        assert PlanetMarkService.calculate_fuel_efficiency(50, None) is None


# ---------------------------------------------------------------------------
# calculate_certification_readiness
# ---------------------------------------------------------------------------


class TestCalculateCertificationReadiness:
    def test_all_uploaded(self):
        evidence = [
            {"required": True, "uploaded": True},
            {"required": True, "uploaded": True},
        ]
        assert PlanetMarkService.calculate_certification_readiness(evidence) == 100.0

    def test_none_uploaded(self):
        evidence = [
            {"required": True, "uploaded": False},
            {"required": True, "uploaded": False},
        ]
        assert PlanetMarkService.calculate_certification_readiness(evidence) == 0.0

    def test_partial(self):
        evidence = [
            {"required": True, "uploaded": True},
            {"required": True, "uploaded": False},
            {"required": False, "uploaded": False},
        ]
        assert PlanetMarkService.calculate_certification_readiness(evidence) == 50.0

    def test_no_required_returns_zero(self):
        evidence = [{"required": False, "uploaded": True}]
        assert PlanetMarkService.calculate_certification_readiness(evidence) == 0


# ---------------------------------------------------------------------------
# calculate_year_totals
# ---------------------------------------------------------------------------


class TestCalculateYearTotals:
    def test_empty(self):
        result = PlanetMarkService.calculate_year_totals([])
        assert result["total_emissions"] == 0

    def test_scope_separation(self):
        s1 = MagicMock(scope="scope_1", co2e_tonnes=10, data_quality_score=4)
        s2 = MagicMock(scope="scope_2", co2e_tonnes=20, data_quality_score=3)
        s3 = MagicMock(scope="scope_3", co2e_tonnes=30, data_quality_score=2)
        result = PlanetMarkService.calculate_year_totals([s1, s2, s3])
        assert result["scope_1_total"] == 10
        assert result["scope_2_market"] == 20
        assert result["scope_3_total"] == 30
        assert result["total_emissions"] == 60
