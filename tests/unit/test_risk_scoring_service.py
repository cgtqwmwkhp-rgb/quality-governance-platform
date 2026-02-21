"""Unit tests for Risk Scoring Service - can run standalone."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


def test_calculate_risk_level_function():
    """Test the module-level calculate_risk_level function returns correct tuples."""
    from src.domain.services.risk_scoring import calculate_risk_level

    score, level, color = calculate_risk_level(1, 1)
    assert score == 1
    assert level == "very_low"
    assert color == "#22c55e"
    print(f"✓ 1x1 = {score}, {level}")

    score, level, color = calculate_risk_level(5, 5)
    assert score == 25
    assert level == "critical"
    assert color == "#ef4444"
    print(f"✓ 5x5 = {score}, {level}")

    score, level, color = calculate_risk_level(3, 3)
    assert score == 9
    assert level == "medium"
    assert color == "#eab308"
    print(f"✓ 3x3 = {score}, {level}")

    score, level, color = calculate_risk_level(4, 4)
    assert score == 16
    assert level == "high"
    assert color == "#f97316"
    print(f"✓ 4x4 = {score}, {level}")

    print("\n✅ calculate_risk_level function works correctly")


def test_risk_matrix_completeness():
    """Test RISK_MATRIX covers all 25 cells of the 5x5 matrix."""
    from src.domain.services.risk_scoring import RISK_MATRIX

    assert len(RISK_MATRIX) == 5, f"Expected 5 likelihood rows, got {len(RISK_MATRIX)}"
    print("✓ 5 likelihood levels present")

    for likelihood in range(1, 6):
        assert likelihood in RISK_MATRIX, f"Missing likelihood level: {likelihood}"
        assert (
            len(RISK_MATRIX[likelihood]) == 5
        ), f"Likelihood {likelihood}: expected 5 impact columns, got {len(RISK_MATRIX[likelihood])}"
        for impact in range(1, 6):
            assert impact in RISK_MATRIX[likelihood], f"Missing cell ({likelihood}, {impact})"
            level, color = RISK_MATRIX[likelihood][impact]
            assert level in (
                "very_low",
                "low",
                "medium",
                "high",
                "critical",
            ), f"Invalid level '{level}' at ({likelihood}, {impact})"
            assert color.startswith("#"), f"Invalid color at ({likelihood}, {impact})"

    print("✓ All 25 cells present and valid")
    print("\n✅ Risk matrix completeness verified")


def test_risk_matrix_monotonicity():
    """Test that risk levels generally increase with higher likelihood/impact."""
    from src.domain.services.risk_scoring import RISK_MATRIX

    level_order = {"very_low": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

    corner_low = level_order[RISK_MATRIX[1][1][0]]
    corner_high = level_order[RISK_MATRIX[5][5][0]]
    assert corner_high > corner_low, "Top-right corner should be higher risk than bottom-left"
    print(f"✓ (1,1) = {RISK_MATRIX[1][1][0]} < (5,5) = {RISK_MATRIX[5][5][0]}")

    mid = level_order[RISK_MATRIX[3][3][0]]
    assert corner_low < mid < corner_high, "Middle should be between corners"
    print(f"✓ (3,3) = {RISK_MATRIX[3][3][0]} is between extremes")

    for l in range(1, 6):
        row_levels = [level_order[RISK_MATRIX[l][i][0]] for i in range(1, 6)]
        for j in range(len(row_levels) - 1):
            assert row_levels[j] <= row_levels[j + 1], f"Row {l}: levels should not decrease as impact increases"
    print("✓ Rows are monotonically non-decreasing")

    for i in range(1, 6):
        col_levels = [level_order[RISK_MATRIX[l][i][0]] for l in range(1, 6)]
        for j in range(len(col_levels) - 1):
            assert col_levels[j] <= col_levels[j + 1], f"Column {i}: levels should not decrease as likelihood increases"
    print("✓ Columns are monotonically non-decreasing")

    print("\n✅ Risk matrix monotonicity verified")


def test_risk_scoring_service_calculate_risk_level_method():
    """Test RiskScoringService._calculate_risk_level thresholds."""
    from unittest.mock import MagicMock

    from src.domain.services.risk_scoring import RiskScoringService

    mock_db = MagicMock()
    service = RiskScoringService(db=mock_db)

    test_cases = [
        (1, "negligible"),
        (4, "negligible"),
        (5, "low"),
        (9, "low"),
        (10, "medium"),
        (14, "medium"),
        (15, "high"),
        (19, "high"),
        (20, "critical"),
        (25, "critical"),
    ]

    for score, expected_level in test_cases:
        result = service._calculate_risk_level(score)
        assert result == expected_level, f"Score {score}: expected '{expected_level}', got '{result}'"
        print(f"✓ Score {score:2d} → {result}")

    print("\n✅ All risk level thresholds correct")


def test_risk_scoring_service_severity_impact_map():
    """Test SEVERITY_IMPACT mapping values."""
    from src.domain.models.incident import IncidentSeverity
    from src.domain.services.risk_scoring import RiskScoringService

    assert RiskScoringService.SEVERITY_IMPACT[IncidentSeverity.CRITICAL] == 2
    print("✓ CRITICAL severity → impact adjustment of 2")

    assert RiskScoringService.SEVERITY_IMPACT[IncidentSeverity.HIGH] == 1
    print("✓ HIGH severity → impact adjustment of 1")

    for sev in [IncidentSeverity.MEDIUM, IncidentSeverity.LOW, IncidentSeverity.NEGLIGIBLE]:
        assert RiskScoringService.SEVERITY_IMPACT[sev] == 0
        print(f"✓ {sev.name} severity → no impact adjustment")

    print("\n✅ Severity impact mapping correct")


def test_risk_scoring_service_near_miss_velocity_thresholds():
    """Test near-miss velocity threshold constants."""
    from src.domain.services.risk_scoring import RiskScoringService

    assert RiskScoringService.NEAR_MISS_VELOCITY_HIGH == 10
    print(f"✓ High velocity threshold: {RiskScoringService.NEAR_MISS_VELOCITY_HIGH} per month")

    assert RiskScoringService.NEAR_MISS_VELOCITY_MEDIUM == 5
    print(f"✓ Medium velocity threshold: {RiskScoringService.NEAR_MISS_VELOCITY_MEDIUM} per month")

    assert RiskScoringService.NEAR_MISS_VELOCITY_HIGH > RiskScoringService.NEAR_MISS_VELOCITY_MEDIUM
    print("✓ High threshold > Medium threshold")

    print("\n✅ Near-miss velocity thresholds correct")


def test_risk_level_boundary_values():
    """Test risk level calculation at exact boundary values."""
    from unittest.mock import MagicMock

    from src.domain.services.risk_scoring import RiskScoringService

    mock_db = MagicMock()
    service = RiskScoringService(db=mock_db)

    boundaries = [
        (0, "negligible"),
        (4, "negligible"),
        (5, "low"),
        (9, "low"),
        (10, "medium"),
        (14, "medium"),
        (15, "high"),
        (19, "high"),
        (20, "critical"),
    ]

    for score, expected in boundaries:
        result = service._calculate_risk_level(score)
        assert result == expected, f"Boundary score {score}: expected '{expected}', got '{result}'"
        print(f"✓ Boundary {score:2d} → {result}")

    print("\n✅ All boundary values correct")


def test_calculate_risk_level_score_computation():
    """Test that calculate_risk_level correctly computes score as likelihood * impact."""
    from src.domain.services.risk_scoring import calculate_risk_level

    for l in range(1, 6):
        for i in range(1, 6):
            score, level, color = calculate_risk_level(l, i)
            assert score == l * i, f"({l},{i}): expected score {l*i}, got {score}"

    print("✓ All 25 score computations verified (score = likelihood × impact)")
    print("\n✅ Score computation correct")


if __name__ == "__main__":
    print("=" * 60)
    print("RISK SCORING SERVICE TESTS")
    print("=" * 60)
    print()

    test_calculate_risk_level_function()
    print()
    test_risk_matrix_completeness()
    print()
    test_risk_matrix_monotonicity()
    print()
    test_risk_scoring_service_calculate_risk_level_method()
    print()
    test_risk_scoring_service_severity_impact_map()
    print()
    test_risk_scoring_service_near_miss_velocity_thresholds()
    print()
    test_risk_level_boundary_values()
    print()
    test_calculate_risk_level_score_computation()

    print()
    print("=" * 60)
    print("ALL RISK SCORING TESTS PASSED ✅")
    print("=" * 60)
