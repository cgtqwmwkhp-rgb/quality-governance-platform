"""Unit tests for AnalyticsService - can run standalone."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.domain.services.analytics_service import AnalyticsService  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def svc():
    return AnalyticsService()


# ---------------------------------------------------------------------------
# get_kpi_summary tests
# ---------------------------------------------------------------------------


def test_kpi_summary_has_all_modules(svc):
    """KPI summary includes all expected top-level modules."""
    kpis = svc.get_kpi_summary()
    expected = {"incidents", "actions", "audits", "risks", "compliance", "training"}
    assert set(kpis.keys()) == expected
    print("✓ KPI summary has all modules")


def test_kpi_summary_incident_trend(svc):
    """Incident trend is a negative number (improvement)."""
    kpis = svc.get_kpi_summary()
    assert kpis["incidents"]["trend"] < 0
    print("✓ Incident trend is negative (improving)")


# ---------------------------------------------------------------------------
# get_trend_data tests
# ---------------------------------------------------------------------------


def test_trend_data_30_days(svc):
    """30-day range produces 30 labels and 30 values."""
    trend = svc.get_trend_data("incidents", "count", time_range="last_30_days")
    assert len(trend["labels"]) == 30
    assert len(trend["datasets"][0]["data"]) == 30
    print("✓ 30-day trend has 30 data points")


def test_trend_data_90_days(svc):
    """90-day range produces 90 data points."""
    trend = svc.get_trend_data("incidents", "count", time_range="last_90_days")
    assert len(trend["labels"]) == 90
    print("✓ 90-day trend has 90 data points")


def test_trend_summary_statistics(svc):
    """Summary includes total, average, min, max, and trend direction."""
    trend = svc.get_trend_data("actions", "count")
    s = trend["summary"]
    assert s["average"] == pytest.approx(s["total"] / 30, rel=1e-5)
    assert s["min"] <= s["average"] <= s["max"]
    assert s["trend_direction"] in ("up", "down")
    print("✓ Trend summary statistics are consistent")


# ---------------------------------------------------------------------------
# forecast_trend tests
# ---------------------------------------------------------------------------


def test_forecast_insufficient_data(svc):
    """Forecast returns error when given < 3 data points."""
    result = svc.forecast_trend([1.0, 2.0])
    assert "error" in result
    print("✓ Insufficient data returns error")


def test_forecast_empty_data(svc):
    """Forecast handles empty list gracefully."""
    result = svc.forecast_trend([])
    assert "error" in result
    print("✓ Empty data returns error")


def test_forecast_produces_correct_periods(svc):
    """Forecast produces the requested number of periods."""
    data = [float(i) for i in range(20)]
    result = svc.forecast_trend(data, periods_ahead=6)
    assert len(result["forecast"]) == 6
    assert len(result["lower_bound"]) == 6
    assert len(result["upper_bound"]) == 6
    print("✓ Forecast produces 6 periods")


def test_forecast_confidence_bounds(svc):
    """Upper bound >= forecast >= lower bound for every period."""
    data = [10.0, 12.0, 11.0, 14.0, 13.0, 15.0, 16.0]
    result = svc.forecast_trend(data, periods_ahead=5)
    for i in range(5):
        assert result["lower_bound"][i] <= result["forecast"][i] <= result["upper_bound"][i]
    print("✓ Confidence bounds are consistent")


def test_forecast_increasing_trend(svc):
    """Monotonically increasing data produces an 'increasing' trend."""
    data = [float(i) for i in range(1, 15)]
    result = svc.forecast_trend(data)
    assert result["trend_direction"] == "increasing"
    assert result["trend_strength"] > 0
    print("✓ Increasing trend detected")


def test_forecast_decreasing_trend(svc):
    """Monotonically decreasing data produces a 'decreasing' trend."""
    data = [float(20 - i) for i in range(15)]
    result = svc.forecast_trend(data)
    assert result["trend_direction"] == "decreasing"
    print("✓ Decreasing trend detected")


# ---------------------------------------------------------------------------
# Benchmarking tests
# ---------------------------------------------------------------------------


def test_benchmark_known_metric(svc):
    """Known metric returns comparison data with your_percentile."""
    result = svc.get_benchmark_comparison("incident_rate")
    assert "your_value" in result
    assert "industry_average" in result
    assert "your_percentile" in result
    print("✓ Known benchmark metric returns data")


def test_benchmark_unknown_metric(svc):
    """Unknown metric returns error."""
    result = svc.get_benchmark_comparison("nonexistent_metric")
    assert "error" in result
    print("✓ Unknown benchmark returns error")


def test_benchmark_summary_overall(svc):
    """Benchmark summary includes overall_percentile and performance_rating."""
    summary = svc.get_benchmark_summary()
    assert "overall_percentile" in summary
    assert "performance_rating" in summary
    assert summary["total_metrics"] == 4
    print("✓ Benchmark summary has expected structure")


# ---------------------------------------------------------------------------
# Performance rating tests
# ---------------------------------------------------------------------------


def test_performance_rating_excellent(svc):
    assert svc._get_performance_rating(92) == "Excellent"
    print("✓ 92 percentile = Excellent")


def test_performance_rating_good(svc):
    assert svc._get_performance_rating(80) == "Good"
    print("✓ 80 percentile = Good")


def test_performance_rating_average(svc):
    assert svc._get_performance_rating(55) == "Average"
    print("✓ 55 percentile = Average")


def test_performance_rating_below_average(svc):
    assert svc._get_performance_rating(30) == "Below Average"
    print("✓ 30 percentile = Below Average")


def test_performance_rating_needs_improvement(svc):
    assert svc._get_performance_rating(10) == "Needs Improvement"
    print("✓ 10 percentile = Needs Improvement")


# ---------------------------------------------------------------------------
# ROI tests
# ---------------------------------------------------------------------------


def test_roi_all_investments(svc):
    """Overall ROI summary calculates correctly."""
    result = svc.calculate_roi()
    assert "investments" in result
    assert "summary" in result
    assert result["summary"]["overall_roi"] == pytest.approx((81000 / 115000) * 100, rel=1e-3)
    print("✓ Overall ROI calculation correct")


def test_roi_specific_investment(svc):
    """Single investment lookup by id returns that investment."""
    result = svc.calculate_roi(investment_id=2)
    assert result["investment"]["name"] == "Enhanced PPE Program"
    print("✓ Single investment lookup works")


def test_roi_not_found(svc):
    """Unknown investment id returns error."""
    result = svc.calculate_roi(investment_id=999)
    assert "error" in result
    print("✓ Unknown investment returns error")


# ---------------------------------------------------------------------------
# Executive summary tests
# ---------------------------------------------------------------------------


def test_executive_summary_structure(svc):
    """Executive summary has all top-level sections."""
    report = svc.generate_executive_summary()
    expected = {"report_date", "time_range", "executive_summary", "kpis", "financial", "benchmarks", "trends"}
    assert expected.issubset(set(report.keys()))
    print("✓ Executive summary has all sections")


if __name__ == "__main__":
    print("=" * 60)
    print("ANALYTICS SERVICE TESTS")
    print("=" * 60)
    print()

    s = AnalyticsService()
    test_kpi_summary_has_all_modules(s)
    test_kpi_summary_incident_trend(s)
    print()
    test_trend_data_30_days(s)
    test_trend_data_90_days(s)
    test_trend_summary_statistics(s)
    print()
    test_forecast_insufficient_data(s)
    test_forecast_empty_data(s)
    test_forecast_produces_correct_periods(s)
    test_forecast_confidence_bounds(s)
    test_forecast_increasing_trend(s)
    test_forecast_decreasing_trend(s)
    print()
    test_benchmark_known_metric(s)
    test_benchmark_unknown_metric(s)
    test_benchmark_summary_overall(s)
    print()
    test_performance_rating_excellent(s)
    test_performance_rating_good(s)
    test_performance_rating_average(s)
    test_performance_rating_below_average(s)
    test_performance_rating_needs_improvement(s)
    print()
    test_roi_all_investments(s)
    test_roi_specific_investment(s)
    test_roi_not_found(s)
    print()
    test_executive_summary_structure(s)

    print()
    print("=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)
