"""AUD-F4: what completion refuses, and what it refuses to leave behind.

``complete_run`` is the only place a run's verdict, findings, CAPA actions and
risks are produced from scoring, so whatever it accepts becomes a compliance
claim. Three refusals are pinned here:

1. A run with no answer the server counts cannot be completed at all — AUD-2026-0087
   reached "completed" carrying zero ``audit_responses`` rows.
2. ``audit_responses.applicability`` is written by the client, so a row claiming
   ``hidden_by_logic`` cannot excuse a question the live template still shows.
3. ``response_json.evidence_asset_ids`` is written by the client too, and an id in
   it is on its own enough to make a row look answered, so completion resolves the
   ids against ``evidence_assets`` for this run before believing them.

Uses an isolated in-memory SQLite schema holding the audit tables plus
``evidence_assets`` — SQLite does not enforce FK targets, so tenants/users rows
are not needed for these paths.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.exceptions import ValidationError
from src.domain.models.audit import (
    AuditFinding,
    AuditQuestion,
    AuditResponse,
    AuditRun,
    AuditSection,
    AuditStatus,
    AuditTemplate,
)
from src.domain.models.evidence_asset import EvidenceAsset, EvidenceAssetType, EvidenceSourceModule
from src.domain.services.audit_service import (
    COMPLETE_EVIDENCE_NOT_RESOLVED,
    COMPLETE_NO_APPLICABLE_ANSWERS,
    AuditService,
)

TENANT_ID = 1


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for table in (
            EvidenceAsset.__table__,
            AuditTemplate.__table__,
            AuditSection.__table__,
            AuditQuestion.__table__,
            AuditRun.__table__,
            AuditResponse.__table__,
            AuditFinding.__table__,
        ):
            await conn.run_sync(table.create)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


async def _seed_run(
    db: AsyncSession,
    *,
    questions: list[dict],
    auto_create_findings: bool = True,
    section_rules: dict | None = None,
    assessment_mode: str | None = None,
) -> tuple[AuditRun, list[AuditQuestion]]:
    template = AuditTemplate(
        name="Completion integrity",
        category="Safety",
        audit_type="inspection",
        auto_create_findings=auto_create_findings,
        is_published=True,
        tenant_id=TENANT_ID,
        created_by_id=1,
        reference_number="TPL-F4",
    )
    db.add(template)
    await db.flush()

    section = AuditSection(
        template_id=template.id,
        title="Controls",
        sort_order=1,
        applicability_rules_json=section_rules,
    )
    db.add(section)
    await db.flush()

    created: list[AuditQuestion] = []
    for index, spec in enumerate(questions, start=1):
        question = AuditQuestion(
            template_id=template.id,
            section_id=section.id,
            question_text=spec.get("text", f"Question {index}"),
            question_type=spec.get("question_type", "yes_no"),
            positive_answer="yes",
            is_required=spec.get("is_required", True),
            criticality=spec.get("criticality"),
            failure_triggers_action=True,
            risk_weight=4,
            sort_order=index,
        )
        db.add(question)
        created.append(question)
    await db.flush()

    # ``show_when`` is (1-based question position, expected answer), resolved to
    # the real question id here so no test depends on autoincrement starting at 1.
    for spec, question in zip(questions, created):
        show_when = spec.get("show_when")
        if show_when is None:
            continue
        position, expected = show_when
        question.conditional_logic_json = [
            {
                "source_question_id": created[position - 1].id,
                "operator": "equals",
                "value": expected,
                "action": "show",
            }
        ]
    await db.flush()

    run = AuditRun(
        template_id=template.id,
        title="Completion integrity run",
        status=AuditStatus.IN_PROGRESS,
        assessment_mode=assessment_mode,
        tenant_id=TENANT_ID,
        assigned_to_id=1,
        created_by_id=1,
        reference_number="AUD-F4",
    )
    db.add(run)
    await db.flush()

    for spec, question in zip(questions, created):
        if "answer" not in spec:
            continue
        answer = spec["answer"]
        db.add(
            AuditResponse(
                run_id=run.id,
                question_id=question.id,
                tenant_id=TENANT_ID,
                response_value=answer.get("response_value"),
                response_json=answer.get("response_json"),
                is_na=bool(answer.get("is_na", False)),
                applicability=answer.get("applicability"),
                notes=answer.get("notes"),
            )
        )
    await db.commit()
    return run, created


async def _add_evidence(
    db: AsyncSession,
    *,
    source_id: str,
    key: str,
    deleted: bool = False,
) -> EvidenceAsset:
    asset = EvidenceAsset(
        tenant_id=TENANT_ID,
        storage_key=key,
        content_type="image/jpeg",
        asset_type=EvidenceAssetType.PHOTO,
        source_module=EvidenceSourceModule.AUDIT,
        source_id=source_id,
        description="audit_question:1",
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )
    db.add(asset)
    await db.commit()
    return asset


async def _reread_status(db: AsyncSession, run_id: int) -> AuditStatus:
    db.expire_all()
    stored = await db.get(AuditRun, run_id)
    assert stored is not None
    return stored.status


async def _finding_count(db: AsyncSession, run_id: int) -> int:
    result = await db.execute(select(AuditFinding.id).where(AuditFinding.run_id == run_id))
    return len(list(result.scalars().all()))


# ---------------------------------------------------------------------------
# Refusal 1 — no answer the server counts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_response_rows_is_refused_with_its_own_code(session_factory):
    """An optional-only template used to complete on nothing at all."""
    async with session_factory() as db:
        run, _ = await _seed_run(db, questions=[{"is_required": False, "criticality": "good_to_have"}])

        with pytest.raises(ValidationError) as refused:
            await AuditService(db).complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)

        assert refused.value.code == COMPLETE_NO_APPLICABLE_ANSWERS
        assert refused.value.details["applicable_answer_count"] == 0
        assert refused.value.details["stored_response_count"] == 0
        assert await _reread_status(db, run.id) == AuditStatus.IN_PROGRESS
        assert await _finding_count(db, run.id) == 0


@pytest.mark.asyncio
async def test_an_empty_response_row_is_not_an_answer(session_factory):
    """A row exists, so "0 rows" is not the test — "0 answers" is."""
    async with session_factory() as db:
        run, _ = await _seed_run(
            db,
            questions=[
                {
                    "is_required": False,
                    "criticality": "good_to_have",
                    "answer": {"notes": "walked the yard, nothing recorded"},
                }
            ],
        )

        with pytest.raises(ValidationError) as refused:
            await AuditService(db).complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)

        assert refused.value.code == COMPLETE_NO_APPLICABLE_ANSWERS
        assert refused.value.details["stored_response_count"] == 1
        assert await _reread_status(db, run.id) == AuditStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_answers_for_questions_the_template_hides_do_not_count(session_factory):
    """Q2 is only shown when Q1 == yes; an answer to Q2 alone closes nothing."""
    async with session_factory() as db:
        run, _ = await _seed_run(
            db,
            questions=[
                {"is_required": False, "criticality": "good_to_have"},
                {
                    "is_required": False,
                    "criticality": "good_to_have",
                    "show_when": (1, "yes"),
                    "answer": {"response_value": "yes"},
                },
            ],
        )

        with pytest.raises(ValidationError) as refused:
            await AuditService(db).complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)

        assert refused.value.code == COMPLETE_NO_APPLICABLE_ANSWERS
        assert await _reread_status(db, run.id) == AuditStatus.IN_PROGRESS


# ---------------------------------------------------------------------------
# Refusal 2 — the row cannot declare itself out of scope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_required_question_marked_hidden_on_the_row_is_still_demanded(session_factory):
    """The live template carries no rule hiding this question, so it applies."""
    async with session_factory() as db:
        run, questions = await _seed_run(
            db,
            questions=[{"is_required": True, "answer": {"applicability": "hidden_by_logic"}}],
        )

        with pytest.raises(ValidationError) as refused:
            await AuditService(db).complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)

        assert refused.value.details["missing_question_ids"] == [questions[0].id]
        assert await _reread_status(db, run.id) == AuditStatus.IN_PROGRESS
        assert await _finding_count(db, run.id) == 0


@pytest.mark.asyncio
async def test_hidden_on_the_row_cannot_turn_an_optional_run_into_a_complete_one(session_factory):
    """Nothing required is outstanding, and nothing has been answered either."""
    async with session_factory() as db:
        run, _ = await _seed_run(
            db,
            questions=[
                {
                    "is_required": False,
                    "criticality": "good_to_have",
                    "answer": {"applicability": "hidden_by_logic"},
                }
            ],
        )

        with pytest.raises(ValidationError) as refused:
            await AuditService(db).complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)

        assert refused.value.code == COMPLETE_NO_APPLICABLE_ANSWERS
        assert await _reread_status(db, run.id) == AuditStatus.IN_PROGRESS


# ---------------------------------------------------------------------------
# Refusal 3 — claimed evidence has to exist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invented_evidence_asset_ids_are_refused_and_raise_nothing(session_factory):
    """The failing answer would have produced a finding, action and risk."""
    async with session_factory() as db:
        run, questions = await _seed_run(
            db,
            auto_create_findings=True,
            questions=[
                {
                    "question_type": "photo",
                    "is_required": True,
                    "answer": {"response_value": "no", "response_json": {"evidence_asset_ids": [4242]}},
                }
            ],
        )

        with pytest.raises(ValidationError) as refused:
            await AuditService(db).complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)

        assert refused.value.code == COMPLETE_EVIDENCE_NOT_RESOLVED
        assert refused.value.details["unresolved_evidence_asset_ids"] == [4242]
        assert refused.value.details["question_ids"] == [questions[0].id]
        assert await _reread_status(db, run.id) == AuditStatus.IN_PROGRESS
        assert await _finding_count(db, run.id) == 0


@pytest.mark.asyncio
async def test_evidence_attached_to_another_run_does_not_resolve(session_factory):
    async with session_factory() as db:
        run, _ = await _seed_run(
            db,
            auto_create_findings=False,
            questions=[{"question_type": "photo", "answer": {"response_json": {"evidence_asset_ids": [1]}}}],
        )
        other = await _add_evidence(db, source_id=str(run.id + 1000), key="other-run/photo.jpg")

        with pytest.raises(ValidationError) as refused:
            await AuditService(db).complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)

        assert refused.value.code == COMPLETE_EVIDENCE_NOT_RESOLVED
        assert refused.value.details["unresolved_evidence_asset_ids"] == [other.id]


@pytest.mark.asyncio
async def test_soft_deleted_evidence_does_not_resolve(session_factory):
    """Every read path in the evidence module treats a deleted asset as gone."""
    async with session_factory() as db:
        run, _ = await _seed_run(
            db,
            auto_create_findings=False,
            questions=[{"question_type": "photo", "answer": {"response_json": {"evidence_asset_ids": [1]}}}],
        )
        await _add_evidence(db, source_id=str(run.id), key="this-run/deleted.jpg", deleted=True)

        with pytest.raises(ValidationError) as refused:
            await AuditService(db).complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)

        assert refused.value.code == COMPLETE_EVIDENCE_NOT_RESOLVED


@pytest.mark.asyncio
async def test_real_evidence_for_this_run_resolves_and_completes(session_factory):
    """A photo answer whose only content is its evidence still completes."""
    async with session_factory() as db:
        run, _ = await _seed_run(
            db,
            auto_create_findings=False,
            questions=[{"question_type": "photo", "answer": {"response_json": {"evidence_asset_ids": [1]}}}],
        )
        await _add_evidence(db, source_id=str(run.id), key="this-run/photo.jpg")

        completed = await AuditService(db).complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)
        await db.commit()

        assert completed.status == AuditStatus.COMPLETED
        assert completed.completed_at is not None


# ---------------------------------------------------------------------------
# A run with real answers still closes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_normally_answered_run_still_completes(session_factory):
    async with session_factory() as db:
        run, _ = await _seed_run(
            db,
            auto_create_findings=False,
            questions=[{"is_required": True, "answer": {"response_value": "yes"}}],
        )

        completed = await AuditService(db).complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)
        await db.commit()

        assert completed.status == AuditStatus.COMPLETED
        assert await _reread_status(db, run.id) == AuditStatus.COMPLETED


@pytest.mark.asyncio
async def test_an_na_answer_is_an_answer(session_factory):
    """An explicit N/A is a recorded judgement, not an absent answer."""
    async with session_factory() as db:
        run, _ = await _seed_run(
            db,
            auto_create_findings=False,
            questions=[{"is_required": True, "answer": {"response_value": "na", "is_na": True}}],
        )

        completed = await AuditService(db).complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)
        await db.commit()

        assert completed.status == AuditStatus.COMPLETED


# ---------------------------------------------------------------------------
# Helper-level facts, no database needed
# ---------------------------------------------------------------------------


def _question(id_, **kwargs):
    return SimpleNamespace(
        id=id_,
        is_active=kwargs.get("is_active", True),
        is_required=kwargs.get("is_required", True),
        criticality=kwargs.get("criticality"),
        section_id=kwargs.get("section_id"),
        question_type="yes_no",
        positive_answer="yes",
        options_json=None,
        evidence_requirements_json=None,
        conditional_logic_json=kwargs.get("conditional_logic_json"),
        risk_weight=None,
    )


def _response(question_id, **kwargs):
    return SimpleNamespace(
        question_id=question_id,
        response_value=kwargs.get("response_value"),
        response_text=None,
        response_number=None,
        response_bool=None,
        response_date=None,
        response_json=kwargs.get("response_json"),
        is_na=kwargs.get("is_na", False),
        applicability=kwargs.get("applicability"),
    )


def test_applicable_answered_ignores_rows_for_questions_not_on_the_template():
    """A row can outlive the question it answered, or never have belonged to it."""
    answered = AuditService._applicable_answered_question_ids(
        questions=[_question(1)],
        responses=[_response(1, response_value="yes"), _response(99, response_value="yes")],
    )
    assert answered == [1]


def test_applicable_answered_ignores_rows_for_inactive_questions():
    answered = AuditService._applicable_answered_question_ids(
        questions=[_question(1, is_active=False)],
        responses=[_response(1, response_value="yes")],
    )
    assert answered == []


def test_only_integrity_refusals_carry_their_own_code_on_the_wire():
    """Other refusals keep the BAD_REQUEST this response has always carried."""
    from src.api.routes.audits import _complete_refusal

    for code in (COMPLETE_EVIDENCE_NOT_RESOLVED, COMPLETE_NO_APPLICABLE_ANSWERS):
        assert _complete_refusal(ValidationError("refused", code=code)) == (code, code.lower())

    assert _complete_refusal(ValidationError("Only in-progress runs can be completed")) == (
        None,
        "invalid_status_transition",
    )
    assert _complete_refusal(ValidationError("All required audit questions must be answered")) == (
        None,
        "invalid_status_transition",
    )


def test_applicable_answered_ignores_out_of_composition_sections():
    section = SimpleNamespace(id=7, applicability_rules_json={"assessment_modes": ["full"]})
    answered = AuditService._applicable_answered_question_ids(
        questions=[_question(1, section_id=7)],
        responses=[_response(1, response_value="yes")],
        sections=[section],
        assessment_mode="spot_check",
    )
    assert answered == []
