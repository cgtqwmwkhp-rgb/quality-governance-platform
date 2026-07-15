"""Unit tests for GKB WL4 recurrence pattern decisions (no DB)."""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.services.gkb_recurrence_patterns import (
    ClauseHitRecord,
    RecurrencePatternContext,
    RecurrencePatternDenyReason,
    RecurrencePatternStep,
    decide_recurrence_patterns,
)


def _hit(**overrides: Any) -> ClauseHitRecord:
    values: dict[str, Any] = {
        "clause_id": "9001-7.5",
        "entity_id": "inc-1",
        "entity_type": "incident",
        "tenant_id": 7,
    }
    values.update(overrides)
    return ClauseHitRecord(
        clause_id=values["clause_id"],
        entity_id=values["entity_id"],
        entity_type=values["entity_type"],
        tenant_id=values["tenant_id"],
    )


def _ctx(**overrides: Any) -> RecurrencePatternContext:
    values: dict[str, Any] = {
        "tenant_id": 7,
        "hits": (
            _hit(entity_id="inc-1"),
            _hit(entity_id="inc-2"),
            _hit(clause_id="9001-9.2", entity_id="aud-1", entity_type="audit"),
        ),
        "include_entity_type_window": True,
        "sample_limit": 5,
    }
    values.update(overrides)
    return RecurrencePatternContext(
        tenant_id=values["tenant_id"],
        hits=tuple(values["hits"]),
        include_entity_type_window=bool(values["include_entity_type_window"]),
        sample_limit=int(values["sample_limit"]),
    )


@pytest.mark.parametrize(
    ("overrides", "deny_reason"),
    [
        ({"tenant_id": None}, RecurrencePatternDenyReason.TENANT_CONTEXT_REQUIRED),
        ({"hits": ()}, RecurrencePatternDenyReason.HITS_REQUIRED),
        (
            {"hits": (_hit(clause_id="", entity_id="inc-1"),)},
            RecurrencePatternDenyReason.HITS_REQUIRED,
        ),
        (
            {"hits": (_hit(clause_id="9001-7.5", entity_id=""),)},
            RecurrencePatternDenyReason.HITS_REQUIRED,
        ),
    ],
)
def test_decide_denies_without_required_context(
    overrides: dict[str, object], deny_reason: RecurrencePatternDenyReason
) -> None:
    plan = decide_recurrence_patterns(_ctx(**overrides))

    assert plan.denied is True
    assert plan.should_run is False
    assert plan.deny_reason is deny_reason
    assert plan.patterns == ()
    assert plan.steps == ()
    assert plan.pattern_count == 0


def test_decide_clusters_by_clause_and_entity_type_window() -> None:
    plan = decide_recurrence_patterns(_ctx())

    assert plan.denied is False
    assert plan.should_run is True
    assert plan.steps == (
        RecurrencePatternStep.CLUSTER_HITS,
        RecurrencePatternStep.EMIT_PATTERNS,
    )
    assert plan.pattern_count == 2

    by_clause = {p.clause_id: p for p in plan.patterns}
    assert by_clause["9001-7.5"].hit_count == 2
    assert by_clause["9001-7.5"].sample_entity_ids == ("inc-1", "inc-2")
    assert by_clause["9001-7.5"].entity_type == "incident"
    assert by_clause["9001-7.5"].pattern_key == ("tenant:7|clause:9001-7.5|entity_type:incident")
    assert by_clause["9001-9.2"].hit_count == 1
    assert by_clause["9001-9.2"].sample_entity_ids == ("aud-1",)
    assert by_clause["9001-9.2"].pattern_key == ("tenant:7|clause:9001-9.2|entity_type:audit")


def test_decide_ignores_foreign_tenant_hits() -> None:
    plan = decide_recurrence_patterns(
        _ctx(
            hits=(
                _hit(entity_id="inc-1", tenant_id=7),
                _hit(entity_id="inc-99", tenant_id=99),
            )
        )
    )

    assert plan.denied is False
    assert plan.pattern_count == 1
    assert plan.patterns[0].hit_count == 1
    assert plan.patterns[0].sample_entity_ids == ("inc-1",)


def test_decide_denies_when_all_hits_are_foreign_tenant() -> None:
    plan = decide_recurrence_patterns(_ctx(hits=(_hit(entity_id="inc-99", tenant_id=99),)))

    assert plan.denied is True
    assert plan.deny_reason is RecurrencePatternDenyReason.HITS_REQUIRED


def test_decide_without_entity_type_window_merges_clause_clusters() -> None:
    plan = decide_recurrence_patterns(
        _ctx(
            include_entity_type_window=False,
            hits=(
                _hit(clause_id="9001-7.5", entity_id="inc-1", entity_type="incident"),
                _hit(clause_id="9001-7.5", entity_id="aud-1", entity_type="audit"),
            ),
        )
    )

    assert plan.pattern_count == 1
    pattern = plan.patterns[0]
    assert pattern.clause_id == "9001-7.5"
    assert pattern.entity_type is None
    assert pattern.hit_count == 2
    assert pattern.sample_entity_ids == ("inc-1", "aud-1")
    assert pattern.pattern_key == "tenant:7|clause:9001-7.5"


def test_decide_sample_limit_caps_entity_ids_preserving_order() -> None:
    plan = decide_recurrence_patterns(
        _ctx(
            sample_limit=2,
            hits=(
                _hit(entity_id="inc-1"),
                _hit(entity_id="inc-2"),
                _hit(entity_id="inc-3"),
                _hit(entity_id="inc-2"),  # duplicate hit still counts
            ),
        )
    )

    assert plan.pattern_count == 1
    pattern = plan.patterns[0]
    assert pattern.hit_count == 4
    assert pattern.sample_entity_ids == ("inc-1", "inc-2")


def test_decide_accepts_hits_without_tenant_on_record() -> None:
    plan = decide_recurrence_patterns(
        _ctx(
            hits=(
                _hit(entity_id="inc-1", tenant_id=None),
                _hit(entity_id="inc-2", tenant_id=None),
            )
        )
    )

    assert plan.denied is False
    assert plan.patterns[0].hit_count == 2
    assert plan.patterns[0].sample_entity_ids == ("inc-1", "inc-2")
