"""Unit tests for interactive risk heat map banding and payload."""

from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.risk_service import RiskScoringEngine, RiskService


def test_canonical_score_bands():
    assert RiskScoringEngine.get_risk_level(4) == "low"
    assert RiskScoringEngine.get_risk_level(5) == "medium"
    assert RiskScoringEngine.get_risk_level(9) == "medium"
    assert RiskScoringEngine.get_risk_level(10) == "high"
    assert RiskScoringEngine.get_risk_level(16) == "high"
    assert RiskScoringEngine.get_risk_level(17) == "critical"
    assert RiskScoringEngine.get_risk_color(10) == "#f97316"
    assert RiskScoringEngine.get_risk_color(9) == "#eab308"


def _risk(
    *,
    id: int,
    title: str,
    residual_l: int,
    residual_i: int,
    inherent_l: Optional[int] = None,
    inherent_i: Optional[int] = None,
    owner: str = "Owner",
    overdue: bool = False,
    within_appetite: bool = True,
):
    r = MagicMock()
    r.id = id
    r.title = title
    r.residual_likelihood = residual_l
    r.residual_impact = residual_i
    r.residual_score = residual_l * residual_i
    r.inherent_likelihood = inherent_l if inherent_l is not None else residual_l
    r.inherent_impact = inherent_i if inherent_i is not None else residual_i
    r.inherent_score = r.inherent_likelihood * r.inherent_impact
    r.risk_owner_name = owner
    r.is_within_appetite = within_appetite
    r.next_review_date = datetime.utcnow() - timedelta(days=1) if overdue else datetime.utcnow() + timedelta(days=30)
    r.status = "active"
    r.suggestion_triage_status = None
    return r


def _mock_db(risks):
    db = AsyncMock()

    async def _execute(_stmt):
        result = MagicMock()
        # Heatmap issues two executes: risks then appetite statements
        if not hasattr(_execute, "n"):
            _execute.n = 0
        _execute.n += 1
        if _execute.n % 2 == 1:
            result.scalars.return_value.all.return_value = risks
        else:
            result.scalars.return_value.all.return_value = []
        return result

    db.execute = _execute
    return db


@pytest.mark.asyncio
async def test_heat_map_enriched_cells_and_banding():
    risks = [
        _risk(id=1, title="A", residual_l=2, residual_i=2, owner="Alice", overdue=True),
        _risk(id=2, title="B", residual_l=2, residual_i=2, owner="Bob", within_appetite=False),
        _risk(id=3, title="C", residual_l=5, residual_i=5),
    ]
    service = RiskService(_mock_db(risks))
    data = await service.get_heat_map_data(tenant_id=1)
    assert data["summary"]["total_risks"] == 3
    assert data["summary"]["critical_risks"] == 1
    assert data["summary"]["high_risks"] == 0

    cell = next(c for row in data["matrix"] for c in row if c["likelihood"] == 2 and c["impact"] == 2)
    assert cell["risk_count"] == 2
    assert cell["overdue_count"] == 1
    assert cell["outside_appetite_count"] == 1
    assert "Alice" in cell["owners_sample"]
    assert cell["intensity"] > 0
    assert data["filters_applied"]["score_type"] == "residual"
    assert data["appetite_overlay"]["threshold"] == 12


@pytest.mark.asyncio
async def test_heat_map_inherent_placement():
    risks = [
        _risk(id=1, title="Moved", residual_l=1, residual_i=1, inherent_l=4, inherent_i=4),
    ]
    service = RiskService(_mock_db(risks))
    residual = await service.get_heat_map_data(tenant_id=1, score_type="residual")
    service = RiskService(_mock_db(risks))
    inherent = await service.get_heat_map_data(tenant_id=1, score_type="inherent")

    r_cell = next(c for row in residual["matrix"] for c in row if c["likelihood"] == 1 and c["impact"] == 1)
    i_cell = next(c for row in inherent["matrix"] for c in row if c["likelihood"] == 4 and c["impact"] == 4)
    assert r_cell["risk_count"] == 1
    assert i_cell["risk_count"] == 1


@pytest.mark.asyncio
async def test_heat_map_delta_movers():
    risks = [
        _risk(id=1, title="Moved", residual_l=2, residual_i=2, inherent_l=4, inherent_i=4),
    ]
    service = RiskService(_mock_db(risks))
    data = await service.get_heat_map_data(tenant_id=1, score_type="delta")
    cell = next(c for row in data["matrix"] for c in row if c["likelihood"] == 2 and c["impact"] == 2)
    assert cell["risk_count"] == 1
    assert len(cell["movers"]) == 1
    assert cell["movers"][0]["from"] == [4, 4]
    assert cell["movers"][0]["to"] == [2, 2]
