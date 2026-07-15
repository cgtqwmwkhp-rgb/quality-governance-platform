"""Unit tests for GKB WL5 golden-thread publish-event planner (no DB)."""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.services.gkb_golden_thread import (
    WL3_GENERATE_QUIZ_DRAFT,
    WL3_LIFECYCLE_METHOD_NAMES,
    WL3_MARK_QUIZZES_STALE_FOR_DOCUMENT,
    WL3_REMATCH_EVIDENCE_ON_VERSION,
    GoldenThreadContext,
    GoldenThreadDenyReason,
    GoldenThreadStep,
    decide_golden_thread_publish,
)


def _ctx(**overrides: Any) -> GoldenThreadContext:
    values: dict[str, Any] = {
        "tenant_id": 7,
        "controlled_document_id": 101,
        "library_document_id": 202,
        "hard_fk_present": True,
        "publish_event_requested": True,
    }
    values.update(overrides)
    return GoldenThreadContext(
        tenant_id=values["tenant_id"],
        controlled_document_id=values["controlled_document_id"],
        library_document_id=values["library_document_id"],
        hard_fk_present=bool(values["hard_fk_present"]),
        publish_event_requested=bool(values["publish_event_requested"]),
    )


@pytest.mark.parametrize(
    ("overrides", "deny_reason"),
    [
        ({"tenant_id": None}, GoldenThreadDenyReason.TENANT_CONTEXT_REQUIRED),
        (
            {"controlled_document_id": None},
            GoldenThreadDenyReason.CONTROLLED_DOCUMENT_REQUIRED,
        ),
    ],
)
def test_decide_denies_without_required_context(
    overrides: dict[str, object], deny_reason: GoldenThreadDenyReason
) -> None:
    plan = decide_golden_thread_publish(_ctx(**overrides))

    assert plan.denied is True
    assert plan.should_run is False
    assert plan.deny_reason is deny_reason
    assert plan.emit_publish_event is False
    assert plan.documents_hard_fk_gap is False
    assert plan.steps == ()
    assert plan.wl3_lifecycle_methods == ()


def test_decide_documents_gap_when_hard_fk_absent() -> None:
    plan = decide_golden_thread_publish(_ctx(hard_fk_present=False))

    assert plan.denied is True
    assert plan.should_run is False
    assert plan.deny_reason is GoldenThreadDenyReason.HARD_FK_ABSENT
    assert plan.emit_publish_event is False
    assert plan.documents_hard_fk_gap is True
    assert plan.steps == (GoldenThreadStep.DOCUMENT_HARD_FK_GAP,)
    assert plan.wl3_lifecycle_methods == ()
    assert plan.library_document_id == 202


def test_decide_denies_when_publish_not_requested() -> None:
    plan = decide_golden_thread_publish(_ctx(publish_event_requested=False))

    assert plan.denied is True
    assert plan.should_run is False
    assert plan.deny_reason is GoldenThreadDenyReason.PUBLISH_EVENT_NOT_REQUESTED
    assert plan.emit_publish_event is False
    assert plan.documents_hard_fk_gap is False
    assert plan.steps == ()
    assert plan.wl3_lifecycle_methods == ()


def test_decide_emits_publish_event_when_hard_fk_and_requested() -> None:
    plan = decide_golden_thread_publish(_ctx())

    assert plan.denied is False
    assert plan.should_run is True
    assert plan.emit_publish_event is True
    assert plan.documents_hard_fk_gap is False
    assert plan.deny_reason is None
    assert plan.steps == (GoldenThreadStep.EMIT_PUBLISH_EVENT,)
    assert plan.wl3_lifecycle_methods == WL3_LIFECYCLE_METHOD_NAMES
    assert plan.library_document_id == 202


def test_wl3_method_constants_match_tip_names() -> None:
    assert WL3_REMATCH_EVIDENCE_ON_VERSION == "rematch_evidence_on_version"
    assert WL3_MARK_QUIZZES_STALE_FOR_DOCUMENT == "mark_quizzes_stale_for_document"
    assert WL3_GENERATE_QUIZ_DRAFT == "generate_quiz_draft"
    assert WL3_LIFECYCLE_METHOD_NAMES == (
        "rematch_evidence_on_version",
        "mark_quizzes_stale_for_document",
        "generate_quiz_draft",
    )


def test_optional_library_document_id_may_be_none_when_emitting() -> None:
    plan = decide_golden_thread_publish(_ctx(library_document_id=None))

    assert plan.should_run is True
    assert plan.library_document_id is None
    assert plan.wl3_lifecycle_methods == WL3_LIFECYCLE_METHOD_NAMES


def test_hard_fk_gap_takes_precedence_over_publish_request() -> None:
    plan = decide_golden_thread_publish(_ctx(hard_fk_present=False, publish_event_requested=True))

    assert plan.deny_reason is GoldenThreadDenyReason.HARD_FK_ABSENT
    assert plan.documents_hard_fk_gap is True
    assert plan.emit_publish_event is False
