"""Unit tests for GKB WL3 publish lifecycle decisions (no DB)."""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.services.gkb_publish_lifecycle import (
    GKS_GENERATE_QUIZ_DRAFT,
    GKS_MARK_QUIZZES_STALE_FOR_DOCUMENT,
    GKS_REMATCH_EVIDENCE_ON_VERSION,
    PAR_RE_ACKNOWLEDGE_ON_UPDATE,
    PublishLifecycleContext,
    PublishLifecycleDenyReason,
    PublishLifecycleStep,
    apply_publish_lifecycle_hooks,
    decide_publish_lifecycle,
)


def _ctx(**overrides: object) -> PublishLifecycleContext:
    values: dict[str, object] = {
        "tenant_id": 7,
        "document_id": 101,
        "new_version": "1.2.0",
        "has_library_document": True,
        "has_content": True,
        "has_existing_quizzes": True,
        "re_acknowledge_on_update": True,
        "policy_updated": True,
    }
    values.update(overrides)
    return PublishLifecycleContext(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "deny_reason"),
    [
        ({"tenant_id": None}, PublishLifecycleDenyReason.TENANT_CONTEXT_REQUIRED),
        ({"document_id": None}, PublishLifecycleDenyReason.DOCUMENT_CONTEXT_REQUIRED),
        ({"has_library_document": False}, PublishLifecycleDenyReason.LIBRARY_DOCUMENT_REQUIRED),
        ({"new_version": None}, PublishLifecycleDenyReason.VERSION_REQUIRED),
        ({"new_version": ""}, PublishLifecycleDenyReason.VERSION_REQUIRED),
    ],
)
def test_decide_denies_without_required_context(
    overrides: dict[str, object], deny_reason: PublishLifecycleDenyReason
) -> None:
    plan = decide_publish_lifecycle(_ctx(**overrides))

    assert plan.denied is True
    assert plan.should_run is False
    assert plan.deny_reason is deny_reason
    assert plan.rematch_evidence is False
    assert plan.mark_quizzes_stale is False
    assert plan.generate_quiz_draft is False
    assert plan.require_re_ack is False
    assert plan.steps == ()


def test_decide_full_lifecycle_when_content_quizzes_and_reack() -> None:
    plan = decide_publish_lifecycle(_ctx())

    assert plan.denied is False
    assert plan.should_run is True
    assert plan.rematch_evidence is True
    assert plan.mark_quizzes_stale is True
    assert plan.generate_quiz_draft is True
    assert plan.require_re_ack is True
    assert plan.steps == (
        PublishLifecycleStep.REMATCH_EVIDENCE,
        PublishLifecycleStep.MARK_QUIZZES_STALE,
        PublishLifecycleStep.GENERATE_QUIZ_DRAFT,
        PublishLifecycleStep.REQUIRE_RE_ACK,
    )
    assert plan.service_methods == (
        GKS_REMATCH_EVIDENCE_ON_VERSION,
        GKS_MARK_QUIZZES_STALE_FOR_DOCUMENT,
        GKS_GENERATE_QUIZ_DRAFT,
    )


def test_decide_skips_rematch_and_quiz_draft_without_content() -> None:
    plan = decide_publish_lifecycle(_ctx(has_content=False, has_existing_quizzes=True))

    assert plan.rematch_evidence is False
    assert plan.generate_quiz_draft is False
    assert plan.mark_quizzes_stale is True
    assert PublishLifecycleStep.MARK_QUIZZES_STALE in plan.steps
    assert PublishLifecycleStep.REMATCH_EVIDENCE not in plan.steps
    assert PublishLifecycleStep.GENERATE_QUIZ_DRAFT not in plan.steps


def test_decide_skips_mark_stale_without_existing_quizzes() -> None:
    plan = decide_publish_lifecycle(_ctx(has_existing_quizzes=False))

    assert plan.mark_quizzes_stale is False
    assert plan.generate_quiz_draft is True
    assert PublishLifecycleStep.MARK_QUIZZES_STALE not in plan.steps
    assert PublishLifecycleStep.GENERATE_QUIZ_DRAFT in plan.steps


@pytest.mark.parametrize(
    ("re_ack", "policy_updated", "expected"),
    [
        (True, True, True),
        (True, False, False),
        (False, True, False),
        (None, True, False),
    ],
)
def test_decide_re_ack_follows_requirement_flag(re_ack: bool | None, policy_updated: bool, expected: bool) -> None:
    plan = decide_publish_lifecycle(_ctx(re_acknowledge_on_update=re_ack, policy_updated=policy_updated))

    assert plan.require_re_ack is expected
    assert (PublishLifecycleStep.REQUIRE_RE_ACK in plan.steps) is expected


def test_par_field_constant_matches_tip_model_attribute() -> None:
    assert PAR_RE_ACKNOWLEDGE_ON_UPDATE == "re_acknowledge_on_update"


@pytest.mark.asyncio
async def test_apply_hooks_noop_when_service_missing() -> None:
    plan = decide_publish_lifecycle(_ctx())
    result = await apply_publish_lifecycle_hooks(plan, service=None)

    assert result.skipped_missing_service is True
    assert result.rematch_invoked is False
    assert result.quizzes_stale_invoked is False
    assert result.quiz_draft_invoked is False


@pytest.mark.asyncio
async def test_apply_hooks_noop_when_plan_denied() -> None:
    plan = decide_publish_lifecycle(_ctx(tenant_id=None))

    class _Stub:
        async def rematch_evidence_on_version(self, *args: Any, **kwargs: Any) -> list[Any]:
            raise AssertionError("should not be called when denied")

    result = await apply_publish_lifecycle_hooks(plan, service=_Stub())

    assert result.rematch_invoked is False
    assert result.planned.denied is True


@pytest.mark.asyncio
async def test_apply_hooks_invokes_tip_method_names() -> None:
    plan = decide_publish_lifecycle(_ctx())
    calls: list[str] = []

    class _Stub:
        async def rematch_evidence_on_version(self, *args: Any, **kwargs: Any) -> list[str]:
            calls.append(GKS_REMATCH_EVIDENCE_ON_VERSION)
            return ["link"]

        async def mark_quizzes_stale_for_document(self, *args: Any, **kwargs: Any) -> int:
            calls.append(GKS_MARK_QUIZZES_STALE_FOR_DOCUMENT)
            return 2

        async def generate_quiz_draft(self, *args: Any, **kwargs: Any) -> dict[str, str]:
            calls.append(GKS_GENERATE_QUIZ_DRAFT)
            return {"status": "draft"}

    result = await apply_publish_lifecycle_hooks(
        plan,
        service=_Stub(),
        db=object(),
        document_id=101,
        content="policy body",
        doc_type="policy",
        tenant_id=7,
        user=object(),
        new_version="1.2.0",
    )

    assert calls == [
        GKS_REMATCH_EVIDENCE_ON_VERSION,
        GKS_MARK_QUIZZES_STALE_FOR_DOCUMENT,
        GKS_GENERATE_QUIZ_DRAFT,
    ]
    assert result.rematch_invoked is True
    assert result.quizzes_stale_invoked is True
    assert result.quiz_draft_invoked is True
    assert result.stale_count == 2
    assert result.quiz_draft == {"status": "draft"}
