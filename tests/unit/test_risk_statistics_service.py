"""Unit tests for Risk Statistics Service - can run standalone."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest  # noqa: E402


def test_risk_statistics_service_class_exists():
    """Test RiskStatisticsService class is importable and has expected methods."""
    from src.domain.services.risk_statistics_service import RiskStatisticsService

    assert hasattr(RiskStatisticsService, "get_risk_statistics")
    assert hasattr(RiskStatisticsService, "get_risk_matrix")
    print("✓ RiskStatisticsService has get_risk_statistics method")
    print("✓ RiskStatisticsService has get_risk_matrix method")

    assert callable(getattr(RiskStatisticsService, "get_risk_statistics"))
    assert callable(getattr(RiskStatisticsService, "get_risk_matrix"))
    print("✓ Both methods are callable")

    print("\n✅ RiskStatisticsService class structure verified")


def test_calculate_risk_level_used_by_statistics():
    """Test that the calculate_risk_level function used by the statistics service works."""
    from src.domain.services.risk_scoring import calculate_risk_level

    test_cases = [
        (1, 1, 1, "very_low"),
        (2, 3, 6, "medium"),
        (3, 4, 12, "high"),
        (4, 5, 20, "critical"),
        (5, 5, 25, "critical"),
        (1, 5, 5, "medium"),
        (5, 1, 5, "medium"),
    ]

    for likelihood, impact, expected_score, expected_level in test_cases:
        score, level, color = calculate_risk_level(likelihood, impact)
        assert score == expected_score, f"({likelihood},{impact}): score={score}, expected {expected_score}"
        assert level == expected_level, f"({likelihood},{impact}): level={level}, expected {expected_level}"
        print(f"✓ ({likelihood},{impact}) → score={score}, level={level}")

    print("\n✅ calculate_risk_level correctly used by statistics service")


@pytest.mark.asyncio
async def test_get_risk_statistics_returns_expected_keys():
    """Test get_risk_statistics returns dict with all required keys."""
    from src.domain.services.risk_statistics_service import RiskStatisticsService

    mock_db = AsyncMock()
    mock_scalar_result = MagicMock()
    mock_scalar_result.scalar.return_value = 0
    mock_db.execute.return_value = mock_scalar_result

    mock_category_result = MagicMock()
    mock_category_result.all.return_value = []
    mock_level_result = MagicMock()
    mock_level_result.all.return_value = []

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count in (5, 6):
            return mock_category_result
        result = MagicMock()
        result.scalar.return_value = 0
        result.all.return_value = []
        return result

    mock_db.execute = mock_execute

    stats = await RiskStatisticsService.get_risk_statistics(mock_db, tenant_id=1)

    expected_keys = {
        "total_risks",
        "active_risks",
        "risks_by_category",
        "risks_by_level",
        "risks_requiring_review",
        "overdue_treatments",
        "average_risk_score",
    }
    actual_keys = set(stats.keys())
    assert expected_keys == actual_keys, f"Missing keys: {expected_keys - actual_keys}"
    print("✓ All 7 expected keys present in statistics response")

    for key in expected_keys:
        print(f"  {key}: {stats[key]}")

    print("\n✅ get_risk_statistics response structure verified")


@pytest.mark.asyncio
async def test_get_risk_statistics_with_mocked_data():
    """Test get_risk_statistics correctly aggregates mocked data."""
    from src.domain.services.risk_statistics_service import RiskStatisticsService

    responses = [
        MagicMock(scalar=MagicMock(return_value=15)),  # total_risks
        MagicMock(scalar=MagicMock(return_value=12)),  # active_risks
        MagicMock(
            all=MagicMock(return_value=[("operational", 5), ("strategic", 4), ("compliance", 3)])  # risks_by_category
        ),
        MagicMock(all=MagicMock(return_value=[("high", 3), ("medium", 6), ("low", 3)])),  # risks_by_level
        MagicMock(scalar=MagicMock(return_value=2)),  # risks_requiring_review
        MagicMock(scalar=MagicMock(return_value=1)),  # overdue_treatments
        MagicMock(scalar=MagicMock(return_value=12.5)),  # average_risk_score
    ]

    call_idx = 0

    async def mock_execute(query):
        nonlocal call_idx
        result = responses[call_idx]
        call_idx += 1
        return result

    mock_db = MagicMock()
    mock_db.execute = mock_execute

    stats = await RiskStatisticsService.get_risk_statistics(mock_db, tenant_id=1)

    assert stats["total_risks"] == 15
    print("✓ total_risks = 15")

    assert stats["active_risks"] == 12
    print("✓ active_risks = 12")

    assert stats["risks_by_category"] == {"operational": 5, "strategic": 4, "compliance": 3}
    print("✓ risks_by_category correctly aggregated")

    assert stats["risks_by_level"] == {"high": 3, "medium": 6, "low": 3}
    print("✓ risks_by_level correctly aggregated")

    assert stats["risks_requiring_review"] == 2
    print("✓ risks_requiring_review = 2")

    assert stats["overdue_treatments"] == 1
    print("✓ overdue_treatments = 1")

    assert stats["average_risk_score"] == 12.5
    print("✓ average_risk_score = 12.5")

    print("\n✅ Statistics aggregation with mocked data correct")


@pytest.mark.asyncio
async def test_get_risk_statistics_handles_null_category():
    """Test that null category is mapped to 'uncategorized'."""
    from src.domain.services.risk_statistics_service import RiskStatisticsService

    responses = [
        MagicMock(scalar=MagicMock(return_value=5)),
        MagicMock(scalar=MagicMock(return_value=5)),
        MagicMock(all=MagicMock(return_value=[(None, 3), ("operational", 2)])),
        MagicMock(all=MagicMock(return_value=[("medium", 5)])),
        MagicMock(scalar=MagicMock(return_value=0)),
        MagicMock(scalar=MagicMock(return_value=0)),
        MagicMock(scalar=MagicMock(return_value=8.0)),
    ]

    call_idx = 0

    async def mock_execute(query):
        nonlocal call_idx
        result = responses[call_idx]
        call_idx += 1
        return result

    mock_db = MagicMock()
    mock_db.execute = mock_execute

    stats = await RiskStatisticsService.get_risk_statistics(mock_db, tenant_id=1)

    assert "uncategorized" in stats["risks_by_category"]
    assert stats["risks_by_category"]["uncategorized"] == 3
    print("✓ None category mapped to 'uncategorized' with count 3")

    assert stats["risks_by_category"]["operational"] == 2
    print("✓ Normal category preserved")

    print("\n✅ Null category handling correct")


@pytest.mark.asyncio
async def test_get_risk_statistics_handles_null_level():
    """Test that null risk_level is mapped to 'unknown'."""
    from src.domain.services.risk_statistics_service import RiskStatisticsService

    responses = [
        MagicMock(scalar=MagicMock(return_value=3)),
        MagicMock(scalar=MagicMock(return_value=3)),
        MagicMock(all=MagicMock(return_value=[("ops", 3)])),
        MagicMock(all=MagicMock(return_value=[(None, 2), ("high", 1)])),
        MagicMock(scalar=MagicMock(return_value=0)),
        MagicMock(scalar=MagicMock(return_value=0)),
        MagicMock(scalar=MagicMock(return_value=0.0)),
    ]

    call_idx = 0

    async def mock_execute(query):
        nonlocal call_idx
        result = responses[call_idx]
        call_idx += 1
        return result

    mock_db = MagicMock()
    mock_db.execute = mock_execute

    stats = await RiskStatisticsService.get_risk_statistics(mock_db, tenant_id=1)

    assert "unknown" in stats["risks_by_level"]
    assert stats["risks_by_level"]["unknown"] == 2
    print("✓ None risk_level mapped to 'unknown' with count 2")

    assert stats["risks_by_level"]["high"] == 1
    print("✓ Normal level preserved")

    print("\n✅ Null level handling correct")


@pytest.mark.asyncio
async def test_get_risk_statistics_rounds_average_score():
    """Test that average_risk_score is rounded to 2 decimal places."""
    from src.domain.services.risk_statistics_service import RiskStatisticsService

    responses = [
        MagicMock(scalar=MagicMock(return_value=1)),
        MagicMock(scalar=MagicMock(return_value=1)),
        MagicMock(all=MagicMock(return_value=[])),
        MagicMock(all=MagicMock(return_value=[])),
        MagicMock(scalar=MagicMock(return_value=0)),
        MagicMock(scalar=MagicMock(return_value=0)),
        MagicMock(scalar=MagicMock(return_value=12.3456789)),
    ]

    call_idx = 0

    async def mock_execute(query):
        nonlocal call_idx
        result = responses[call_idx]
        call_idx += 1
        return result

    mock_db = MagicMock()
    mock_db.execute = mock_execute

    stats = await RiskStatisticsService.get_risk_statistics(mock_db, tenant_id=1)

    assert stats["average_risk_score"] == 12.35, f"Expected 12.35 (rounded), got {stats['average_risk_score']}"
    print(f"✓ Average score rounded to 2 decimals: {stats['average_risk_score']}")

    print("\n✅ Score rounding correct")


def test_risk_matrix_level_distribution():
    """Test risk matrix has reasonable distribution of risk levels."""
    from src.domain.services.risk_scoring import RISK_MATRIX

    level_counts = {"very_low": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}

    for l in range(1, 6):
        for i in range(1, 6):
            level, _ = RISK_MATRIX[l][i]
            level_counts[level] += 1

    total = sum(level_counts.values())
    assert total == 25, f"Expected 25 cells, got {total}"
    print(f"✓ Total cells: {total}")

    for level, count in level_counts.items():
        assert count >= 1, f"Level '{level}' has zero cells — unreachable!"
        pct = count / total * 100
        print(f"  {level}: {count} cells ({pct:.0f}%)")

    print("\n✅ Risk matrix level distribution reasonable")


if __name__ == "__main__":
    import asyncio

    print("=" * 60)
    print("RISK STATISTICS SERVICE TESTS")
    print("=" * 60)
    print()

    test_risk_statistics_service_class_exists()
    print()
    test_calculate_risk_level_used_by_statistics()
    print()
    asyncio.run(test_get_risk_statistics_returns_expected_keys())
    print()
    asyncio.run(test_get_risk_statistics_with_mocked_data())
    print()
    asyncio.run(test_get_risk_statistics_handles_null_category())
    print()
    asyncio.run(test_get_risk_statistics_handles_null_level())
    print()
    asyncio.run(test_get_risk_statistics_rounds_average_score())
    print()
    test_risk_matrix_level_distribution()

    print()
    print("=" * 60)
    print("ALL RISK STATISTICS TESTS PASSED ✅")
    print("=" * 60)
