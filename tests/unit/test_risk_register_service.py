"""Unit tests for RiskRegisterService - can run standalone."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.domain.services.risk_register_service import RiskRegisterService  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_db_session(scalar_returns: list, execute_return=None):
    """Build an AsyncSession mock returning predetermined scalars."""
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=scalar_returns)

    if execute_return is not None:
        result_mock = MagicMock()
        result_mock.all.return_value = execute_return
        db.execute = AsyncMock(return_value=result_mock)
    else:
        result_mock = MagicMock()
        result_mock.all.return_value = []
        db.execute = AsyncMock(return_value=result_mock)

    return db


# ---------------------------------------------------------------------------
# get_risk_summary tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_risk_summary_totals():
    """Total risks count is returned correctly."""
    db = _mock_db_session(
        scalar_returns=[42, 2, 5, 15, 20, 3, 4, 1],
        execute_return=[("operational", 20), ("financial", 12), ("compliance", 10)],
    )
    result = await RiskRegisterService.get_risk_summary(db, tenant_id=1)
    assert result["total_risks"] == 42
    print("✓ total_risks returned correctly")


@pytest.mark.asyncio
async def test_risk_summary_by_level():
    """Risk levels (critical/high/medium/low) map correctly."""
    db = _mock_db_session(
        scalar_returns=[50, 3, 8, 22, 17, 5, 6, 2],
        execute_return=[],
    )
    result = await RiskRegisterService.get_risk_summary(db, tenant_id=1)
    assert result["by_level"]["critical"] == 3
    assert result["by_level"]["high"] == 8
    assert result["by_level"]["medium"] == 22
    assert result["by_level"]["low"] == 17
    print("✓ by_level buckets match expected values")


@pytest.mark.asyncio
async def test_risk_summary_outside_appetite():
    """outside_appetite count is the 6th scalar call."""
    db = _mock_db_session(scalar_returns=[10, 1, 2, 3, 4, 7, 0, 0])
    result = await RiskRegisterService.get_risk_summary(db, tenant_id=1)
    assert result["outside_appetite"] == 7
    print("✓ outside_appetite returned correctly")


@pytest.mark.asyncio
async def test_risk_summary_overdue_review():
    """overdue_review count is the 7th scalar call."""
    db = _mock_db_session(scalar_returns=[10, 0, 0, 0, 0, 0, 9, 0])
    result = await RiskRegisterService.get_risk_summary(db, tenant_id=1)
    assert result["overdue_review"] == 9
    print("✓ overdue_review returned correctly")


@pytest.mark.asyncio
async def test_risk_summary_escalated():
    """escalated count is the 8th scalar call."""
    db = _mock_db_session(scalar_returns=[10, 0, 0, 0, 0, 0, 0, 5])
    result = await RiskRegisterService.get_risk_summary(db, tenant_id=1)
    assert result["escalated"] == 5
    print("✓ escalated returned correctly")


@pytest.mark.asyncio
async def test_risk_summary_by_category():
    """by_category aggregates category/count tuples from the group-by query."""
    categories = [("safety", 15), ("environmental", 10), ("financial", 5)]
    db = _mock_db_session(scalar_returns=[30, 0, 0, 0, 0, 0, 0, 0], execute_return=categories)
    result = await RiskRegisterService.get_risk_summary(db, tenant_id=1)
    assert result["by_category"] == {"safety": 15, "environmental": 10, "financial": 5}
    print("✓ by_category aggregation correct")


@pytest.mark.asyncio
async def test_risk_summary_empty_register():
    """All zeros when the register is empty."""
    db = _mock_db_session(scalar_returns=[0, 0, 0, 0, 0, 0, 0, 0])
    result = await RiskRegisterService.get_risk_summary(db, tenant_id=1)
    assert result["total_risks"] == 0
    assert result["by_level"] == {"critical": 0, "high": 0, "medium": 0, "low": 0}
    assert result["by_category"] == {}
    print("✓ Empty register returns zeroes")


@pytest.mark.asyncio
async def test_risk_summary_return_keys():
    """All expected keys are present in the response."""
    db = _mock_db_session(scalar_returns=[1, 0, 0, 0, 1, 0, 0, 0])
    result = await RiskRegisterService.get_risk_summary(db, tenant_id=1)
    expected_keys = {"total_risks", "by_level", "outside_appetite", "overdue_review", "escalated", "by_category"}
    assert set(result.keys()) == expected_keys
    print("✓ All expected keys present")


if __name__ == "__main__":
    import asyncio

    print("=" * 60)
    print("RISK REGISTER SERVICE TESTS")
    print("=" * 60)
    print()

    asyncio.run(test_risk_summary_totals())
    asyncio.run(test_risk_summary_by_level())
    asyncio.run(test_risk_summary_outside_appetite())
    asyncio.run(test_risk_summary_overdue_review())
    asyncio.run(test_risk_summary_escalated())
    asyncio.run(test_risk_summary_by_category())
    asyncio.run(test_risk_summary_empty_register())
    asyncio.run(test_risk_summary_return_keys())

    print()
    print("=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)
