"""GKB WL3 publish lifecycle orchestrator.

Documents and decides post-publish steps for governed knowledge documents:

1. Rematch evidence — ``GovernedKnowledgeService.rematch_evidence_on_version``
2. Mark quizzes stale — ``GovernedKnowledgeService.mark_quizzes_stale_for_document``
3. Generate quiz draft — ``GovernedKnowledgeService.generate_quiz_draft``
4. Require re-ack when ``PolicyAcknowledgmentRequirement.re_acknowledge_on_update``

Wired from controlled **publish** and library **approve/publish** paths.
Opening a controlled revise draft must not invoke these hooks (ADR-0021 P0).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Optional, Protocol

from sqlalchemy import select

# Stable tip method names (GovernedKnowledgeService on origin/main).
GKS_REMATCH_EVIDENCE_ON_VERSION = "rematch_evidence_on_version"
GKS_MARK_QUIZZES_STALE_FOR_DOCUMENT = "mark_quizzes_stale_for_document"
GKS_GENERATE_QUIZ_DRAFT = "generate_quiz_draft"

# Tip model field used for re-ack decisions.
PAR_RE_ACKNOWLEDGE_ON_UPDATE = "re_acknowledge_on_update"

logger = logging.getLogger(__name__)


class PublishLifecycleStep(StrEnum):
    """Ordered post-publish lifecycle steps."""

    REMATCH_EVIDENCE = "rematch_evidence"
    MARK_QUIZZES_STALE = "mark_quizzes_stale"
    GENERATE_QUIZ_DRAFT = "generate_quiz_draft"
    REQUIRE_RE_ACK = "require_re_ack"


class PublishLifecycleDenyReason(StrEnum):
    """Stable deny reasons when the lifecycle must not run."""

    TENANT_CONTEXT_REQUIRED = "tenant_context_required"
    DOCUMENT_CONTEXT_REQUIRED = "document_context_required"
    LIBRARY_DOCUMENT_REQUIRED = "library_document_required"
    VERSION_REQUIRED = "version_required"


@dataclass(frozen=True)
class PublishLifecycleContext:
    """Minimum inputs for a publish-lifecycle decision (no DB required)."""

    tenant_id: int | None
    document_id: int | None
    new_version: str | None
    has_library_document: bool = False
    has_content: bool = False
    has_existing_quizzes: bool = False
    # Mirrors PolicyAcknowledgmentRequirement.re_acknowledge_on_update when known.
    re_acknowledge_on_update: bool | None = None
    policy_updated: bool = True


@dataclass(frozen=True)
class PublishLifecyclePlan:
    """Idempotent-friendly decision outcome for a controlled publish."""

    rematch_evidence: bool
    mark_quizzes_stale: bool
    generate_quiz_draft: bool
    require_re_ack: bool
    steps: tuple[PublishLifecycleStep, ...]
    denied: bool = False
    deny_reason: PublishLifecycleDenyReason | None = None
    service_methods: tuple[str, ...] = ()

    @property
    def should_run(self) -> bool:
        return not self.denied and bool(self.steps)


def decide_publish_lifecycle(ctx: PublishLifecycleContext) -> PublishLifecyclePlan:
    """Decide rematch / quiz / re-ack steps for a publish event.

    Deny-safe defaults: missing tenant, document, library link, or version
    yields an empty plan with a stable deny reason (no side effects implied).
    """
    if ctx.tenant_id is None:
        return _denied(PublishLifecycleDenyReason.TENANT_CONTEXT_REQUIRED)
    if ctx.document_id is None:
        return _denied(PublishLifecycleDenyReason.DOCUMENT_CONTEXT_REQUIRED)
    if not ctx.has_library_document:
        return _denied(PublishLifecycleDenyReason.LIBRARY_DOCUMENT_REQUIRED)
    if not ctx.new_version:
        return _denied(PublishLifecycleDenyReason.VERSION_REQUIRED)

    rematch = bool(ctx.has_content)
    mark_stale = bool(ctx.has_existing_quizzes)
    # Draft generation runs after stale marking when content is available so
    # the new version always has a draft candidate (matches document_control tip).
    generate_draft = bool(ctx.has_content)
    require_re_ack = bool(ctx.policy_updated and ctx.re_acknowledge_on_update is True)

    steps: list[PublishLifecycleStep] = []
    methods: list[str] = []
    if rematch:
        steps.append(PublishLifecycleStep.REMATCH_EVIDENCE)
        methods.append(GKS_REMATCH_EVIDENCE_ON_VERSION)
    if mark_stale:
        steps.append(PublishLifecycleStep.MARK_QUIZZES_STALE)
        methods.append(GKS_MARK_QUIZZES_STALE_FOR_DOCUMENT)
    if generate_draft:
        steps.append(PublishLifecycleStep.GENERATE_QUIZ_DRAFT)
        methods.append(GKS_GENERATE_QUIZ_DRAFT)
    if require_re_ack:
        steps.append(PublishLifecycleStep.REQUIRE_RE_ACK)

    return PublishLifecyclePlan(
        rematch_evidence=rematch,
        mark_quizzes_stale=mark_stale,
        generate_quiz_draft=generate_draft,
        require_re_ack=require_re_ack,
        steps=tuple(steps),
        service_methods=tuple(methods),
    )


def _denied(reason: PublishLifecycleDenyReason) -> PublishLifecyclePlan:
    return PublishLifecyclePlan(
        rematch_evidence=False,
        mark_quizzes_stale=False,
        generate_quiz_draft=False,
        require_re_ack=False,
        steps=(),
        denied=True,
        deny_reason=reason,
        service_methods=(),
    )


class SupportsGovernedKnowledgePublishHooks(Protocol):
    """Subset of GovernedKnowledgeService used by publish lifecycle wrappers."""

    async def rematch_evidence_on_version(
        self,
        db: Any,
        document_id: int,
        content: str,
        doc_type: Optional[str],
        tenant_id: int,
        user: Any,
    ) -> Any: ...

    async def mark_quizzes_stale_for_document(
        self,
        db: Any,
        *,
        document_id: int,
        tenant_id: int,
        new_version: str,
    ) -> int: ...

    async def generate_quiz_draft(
        self,
        db: Any,
        *,
        document_id: int,
        content: str,
        version: str,
        tenant_id: int,
        user: Any,
        question_count: int = 5,
        include_open: bool = True,
        include_mcq: bool = True,
        pass_mark: int = 70,
        auto_approve_if_quality: bool = False,
    ) -> Any: ...


@dataclass(frozen=True)
class PublishLifecycleExecutionResult:
    """Outcome of optional thin wrappers (no-op friendly)."""

    planned: PublishLifecyclePlan
    rematch_invoked: bool = False
    quizzes_stale_invoked: bool = False
    quiz_draft_invoked: bool = False
    skipped_missing_service: bool = False
    rematch_result: Any = None
    stale_count: int | None = None
    quiz_draft: Any = None


def library_document_hook_content(document: Any) -> str:
    """Build rematch/quiz content from library Document fields (best-effort)."""
    tags = getattr(document, "ai_tags", None) or []
    return " ".join(
        filter(
            None,
            [
                getattr(document, "title", None) or "",
                getattr(document, "description", None) or "",
                getattr(document, "ai_summary", None) or "",
                " ".join(tags) if tags else "",
            ],
        )
    )


async def document_has_quiz_drafts(db: Any, *, document_id: int, tenant_id: int) -> bool:
    from src.domain.models.governed_knowledge import DocumentQuizDraft

    result = await db.execute(
        select(DocumentQuizDraft.id)
        .where(
            DocumentQuizDraft.document_id == document_id,
            DocumentQuizDraft.tenant_id == tenant_id,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def apply_publish_lifecycle_hooks(
    plan: PublishLifecyclePlan,
    *,
    service: SupportsGovernedKnowledgePublishHooks | None,
    db: Any = None,
    document_id: int | None = None,
    content: str = "",
    doc_type: str | None = None,
    tenant_id: int | None = None,
    user: Any = None,
    new_version: str | None = None,
) -> PublishLifecycleExecutionResult:
    """Thin, idempotent-friendly wrappers around tip GKS methods.

    When ``service`` is missing or a planned method is absent, the call is a
    no-op for that step (safe for unit tests and partial inject). Re-ack is a
    decision-only step in this scaffold — persistence wiring is deferred.
    """
    if plan.denied or service is None:
        return PublishLifecycleExecutionResult(
            planned=plan,
            skipped_missing_service=service is None and not plan.denied,
        )

    # Plan decisions already require ids; skip hooks if caller omitted them.
    if document_id is None or tenant_id is None:
        return PublishLifecycleExecutionResult(planned=plan)

    rematch_invoked = False
    quizzes_stale_invoked = False
    quiz_draft_invoked = False
    rematch_result: Any = None
    stale_count: int | None = None
    quiz_draft: Any = None

    if plan.rematch_evidence and hasattr(service, GKS_REMATCH_EVIDENCE_ON_VERSION):
        rematch_result = await service.rematch_evidence_on_version(
            db,
            document_id,
            content,
            doc_type,
            tenant_id,
            user,
        )
        rematch_invoked = True

    if plan.mark_quizzes_stale and hasattr(service, GKS_MARK_QUIZZES_STALE_FOR_DOCUMENT):
        stale_count = await service.mark_quizzes_stale_for_document(
            db,
            document_id=document_id,
            tenant_id=tenant_id,
            new_version=new_version or "",
        )
        quizzes_stale_invoked = True

    if plan.generate_quiz_draft and hasattr(service, GKS_GENERATE_QUIZ_DRAFT):
        quiz_draft = await service.generate_quiz_draft(
            db,
            document_id=document_id,
            content=content,
            version=new_version or "",
            tenant_id=tenant_id,
            user=user,
            question_count=5,
            include_open=True,
            include_mcq=True,
            pass_mark=70,
            auto_approve_if_quality=True,
        )
        quiz_draft_invoked = True

    return PublishLifecycleExecutionResult(
        planned=plan,
        rematch_invoked=rematch_invoked,
        quizzes_stale_invoked=quizzes_stale_invoked,
        quiz_draft_invoked=quiz_draft_invoked,
        rematch_result=rematch_result,
        stale_count=stale_count,
        quiz_draft=quiz_draft,
    )


async def run_library_publish_lifecycle(
    *,
    db: Any,
    library_document: Any,
    new_version: str,
    user: Any,
    service: SupportsGovernedKnowledgePublishHooks | None = None,
) -> PublishLifecycleExecutionResult:
    """Decide + apply rematch/quiz hooks for a library approve or publish."""
    if service is None:
        from src.domain.services.governed_knowledge_service import governed_knowledge_service

        service = governed_knowledge_service

    tenant_id = getattr(library_document, "tenant_id", None)
    document_id = getattr(library_document, "id", None)
    content = library_document_hook_content(library_document)
    has_quizzes = False
    if tenant_id is not None and document_id is not None:
        try:
            has_quizzes = await document_has_quiz_drafts(
                db,
                document_id=int(document_id),
                tenant_id=int(tenant_id),
            )
        except Exception:
            logger.exception(
                "quiz draft presence check failed for library document %s",
                document_id,
            )

    plan = decide_publish_lifecycle(
        PublishLifecycleContext(
            tenant_id=tenant_id,
            document_id=document_id,
            new_version=new_version,
            has_library_document=True,
            has_content=bool(content.strip()),
            has_existing_quizzes=has_quizzes,
        )
    )
    return await apply_publish_lifecycle_hooks(
        plan,
        service=service,
        db=db,
        document_id=document_id,
        content=content or (getattr(library_document, "title", None) or ""),
        doc_type=getattr(library_document, "document_type", None),
        tenant_id=tenant_id,
        user=user,
        new_version=new_version,
    )


async def run_controlled_publish_lifecycle(
    *,
    db: Any,
    controlled_document: Any,
    new_version: str,
    user: Any,
    tenant_id: int,
    service: SupportsGovernedKnowledgePublishHooks | None = None,
) -> PublishLifecycleExecutionResult:
    """Decide + apply rematch/quiz hooks after controlled publish (hard FK only)."""
    from src.domain.services.gkb_control_library_link import resolve_library_for_controlled

    if service is None:
        from src.domain.services.governed_knowledge_service import governed_knowledge_service

        service = governed_knowledge_service

    library_doc, match = await resolve_library_for_controlled(
        db,
        controlled_document,
        tenant_id=tenant_id,
    )
    if match.relationship_state != "linked" or library_doc is None:
        plan = _denied(PublishLifecycleDenyReason.LIBRARY_DOCUMENT_REQUIRED)
        return PublishLifecycleExecutionResult(planned=plan)

    return await run_library_publish_lifecycle(
        db=db,
        library_document=library_doc,
        new_version=new_version,
        user=user,
        service=service,
    )
