"""Unit tests for near-miss ↔ risk bidirectional link helpers."""

from src.domain.services.near_miss_risk_links import (
    append_linked_risk_id,
    near_miss_risk_source,
    parse_linked_risk_ids,
    parse_near_miss_id_from_risk_source,
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
