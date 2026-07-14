"""Unit tests for near-miss ↔ risk bidirectional link helpers."""

from unittest.mock import AsyncMock

import pytest

from src.domain.services.near_miss_risk_links import (
    append_linked_risk_id,
    map_treatment_strategy,
    near_miss_risk_source,
    parse_linked_risk_ids,
    parse_near_miss_id_from_risk_source,
    resolve_enterprise_category,
    resolve_fk_safe_owner_id,
    risk_register_href,
)


def test_parse_and_append_linked_risk_ids() -> None:
    assert parse_linked_risk_ids(None) == []
    assert parse_linked_risk_ids("1, 2,2,x,3") == [1, 2, 3]
    assert append_linked_risk_id("1,2", 2) == "1,2"
    assert append_linked_risk_id("1,2", 9) == "1,2,9"
    assert append_linked_risk_id(None, 4) == "4"


def test_near_miss_risk_source_round_trip() -> None:
    source = near_miss_risk_source(42, "NM-42")
    assert source == "near_miss:42|NM-42"
    assert parse_near_miss_id_from_risk_source(source) == 42
    assert parse_near_miss_id_from_risk_source("near_miss:7") == 7
    assert parse_near_miss_id_from_risk_source("unrelated") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("mitigate", "treat"),
        ("accept", "tolerate"),
        ("transfer", "transfer"),
        ("avoid", "terminate"),
        ("exploit", "treat"),
        ("treat", "treat"),
        ("tolerate", "tolerate"),
        ("terminate", "terminate"),
        (None, "treat"),
        ("unknown", "treat"),
    ],
)
def test_map_treatment_strategy(raw: str | None, expected: str) -> None:
    assert map_treatment_strategy(raw) == expected


@pytest.mark.parametrize(
    ("preferred", "near_miss_category", "expected"),
    [
        (None, "safety", "safety"),
        ("operational", None, "operational"),
        ("not-a-category", "financial", "financial"),
        ("bogus", "also-bogus", "safety"),
    ],
)
def test_resolve_enterprise_category(preferred: str | None, near_miss_category: str | None, expected: str) -> None:
    assert resolve_enterprise_category(preferred, near_miss_category) == expected


def test_risk_register_href() -> None:
    assert risk_register_href() == "/risk-register"
    assert risk_register_href(9) == "/risk-register?riskId=9"
    assert risk_register_href(9, near_miss_ref="NM-1") == "/risk-register?riskId=9&nearMissRef=NM-1"
    assert risk_register_href(near_miss_ref="NM-1") == "/risk-register?nearMissRef=NM-1"


@pytest.mark.asyncio
async def test_resolve_fk_safe_owner_id_prefers_existing_user() -> None:
    class _Result:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_Result(None), _Result(7)])
    owner = await resolve_fk_safe_owner_id(db, preferred_owner_id=99, fallback_user_id=7)
    assert owner == 7
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_resolve_fk_safe_owner_id_returns_none_when_missing() -> None:
    class _Result:
        def scalar_one_or_none(self):
            return None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result())
    owner = await resolve_fk_safe_owner_id(db, preferred_owner_id=99, fallback_user_id=7)
    assert owner is None
