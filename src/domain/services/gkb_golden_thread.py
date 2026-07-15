"""GKB WL5 golden-thread FK + publish-event planner (scaffold).

Documents whether a controlled document may emit a publish event along the
golden thread (hard FK from controlled → library document).

When the hard FK is present and a publish event is requested, the plan
references WL3 lifecycle tip method names as string constants only:

- ``rematch_evidence_on_version``
- ``mark_quizzes_stale_for_document``
- ``generate_quiz_draft``

This module deliberately does **not** import ``gkb_publish_lifecycle`` (avoids
cycles) and is unwired from publish routes / GovernedKnowledgeService.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# WL3 tip method names (string constants only — no import of gkb_publish_lifecycle).
WL3_REMATCH_EVIDENCE_ON_VERSION = "rematch_evidence_on_version"
WL3_MARK_QUIZZES_STALE_FOR_DOCUMENT = "mark_quizzes_stale_for_document"
WL3_GENERATE_QUIZ_DRAFT = "generate_quiz_draft"

WL3_LIFECYCLE_METHOD_NAMES: tuple[str, ...] = (
    WL3_REMATCH_EVIDENCE_ON_VERSION,
    WL3_MARK_QUIZZES_STALE_FOR_DOCUMENT,
    WL3_GENERATE_QUIZ_DRAFT,
)


class GoldenThreadStep(StrEnum):
    """Ordered golden-thread plan steps."""

    EMIT_PUBLISH_EVENT = "emit_publish_event"
    DOCUMENT_HARD_FK_GAP = "document_hard_fk_gap"


class GoldenThreadDenyReason(StrEnum):
    """Stable deny / gap reasons for golden-thread decisions."""

    TENANT_CONTEXT_REQUIRED = "tenant_context_required"
    CONTROLLED_DOCUMENT_REQUIRED = "controlled_document_required"
    HARD_FK_ABSENT = "hard_fk_absent"
    PUBLISH_EVENT_NOT_REQUESTED = "publish_event_not_requested"


@dataclass(frozen=True)
class GoldenThreadContext:
    """Minimum inputs for a golden-thread publish-event decision (no DB)."""

    tenant_id: int | None
    controlled_document_id: int | None
    library_document_id: int | None = None
    hard_fk_present: bool = False
    publish_event_requested: bool = False


@dataclass(frozen=True)
class GoldenThreadPlan:
    """Idempotent-friendly decision outcome for golden-thread publish planning."""

    emit_publish_event: bool
    documents_hard_fk_gap: bool
    steps: tuple[GoldenThreadStep, ...]
    denied: bool = False
    deny_reason: GoldenThreadDenyReason | None = None
    wl3_lifecycle_methods: tuple[str, ...] = ()
    library_document_id: int | None = None

    @property
    def should_run(self) -> bool:
        return not self.denied and self.emit_publish_event


def decide_golden_thread_publish(ctx: GoldenThreadContext) -> GoldenThreadPlan:
    """Decide whether to emit a publish event along the golden thread.

    Deny-safe defaults: missing tenant or controlled document yields an empty
    plan with a stable deny reason (no side effects implied).

    When the hard FK is absent, the plan documents the gap (no emit) with
    ``HARD_FK_ABSENT`` — still a documented outcome, not a side-effect plan.
    """
    if ctx.tenant_id is None:
        return _denied(GoldenThreadDenyReason.TENANT_CONTEXT_REQUIRED)
    if ctx.controlled_document_id is None:
        return _denied(GoldenThreadDenyReason.CONTROLLED_DOCUMENT_REQUIRED)

    if not ctx.hard_fk_present:
        return GoldenThreadPlan(
            emit_publish_event=False,
            documents_hard_fk_gap=True,
            steps=(GoldenThreadStep.DOCUMENT_HARD_FK_GAP,),
            denied=True,
            deny_reason=GoldenThreadDenyReason.HARD_FK_ABSENT,
            wl3_lifecycle_methods=(),
            library_document_id=ctx.library_document_id,
        )

    if not ctx.publish_event_requested:
        return GoldenThreadPlan(
            emit_publish_event=False,
            documents_hard_fk_gap=False,
            steps=(),
            denied=True,
            deny_reason=GoldenThreadDenyReason.PUBLISH_EVENT_NOT_REQUESTED,
            wl3_lifecycle_methods=(),
            library_document_id=ctx.library_document_id,
        )

    return GoldenThreadPlan(
        emit_publish_event=True,
        documents_hard_fk_gap=False,
        steps=(GoldenThreadStep.EMIT_PUBLISH_EVENT,),
        denied=False,
        deny_reason=None,
        wl3_lifecycle_methods=WL3_LIFECYCLE_METHOD_NAMES,
        library_document_id=ctx.library_document_id,
    )


def _denied(reason: GoldenThreadDenyReason) -> GoldenThreadPlan:
    return GoldenThreadPlan(
        emit_publish_event=False,
        documents_hard_fk_gap=False,
        steps=(),
        denied=True,
        deny_reason=reason,
        wl3_lifecycle_methods=(),
        library_document_id=None,
    )
