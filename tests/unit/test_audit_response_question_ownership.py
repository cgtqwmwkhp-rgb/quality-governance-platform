"""A response may only answer a question from the template its run is executing.

Both write paths fetched the question by bare primary key, so a caller could
attach a response to any question id in the system — including one belonging to
another tenant's private template, whose ``question_text`` is then rendered back
inside the caller's own run. Zero of the 315 existing production rows do this,
so this closes a latent cross-tenant read rather than an active leak.

There is no database constraint and no row-level security behind this: the
application role bypasses RLS, so this comparison is the whole control.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from starlette.responses import Response

from src.api.routes.audits import create_response
from src.api.schemas.audit import AuditResponseCreate
from src.domain.exceptions import NotFoundError
from src.domain.models.audit import AuditQuestion, AuditStatus
from src.domain.services.audit_service import AuditService, question_belongs_to_run

RUN_TEMPLATE_ID = 3
FOREIGN_TEMPLATE_ID = 9


def test_a_question_from_the_runs_template_belongs_to_it() -> None:
    run = SimpleNamespace(id=1, template_id=RUN_TEMPLATE_ID)
    question = SimpleNamespace(id=5, template_id=RUN_TEMPLATE_ID)
    assert question_belongs_to_run(run, question) is True


def test_a_question_from_any_other_template_does_not() -> None:
    run = SimpleNamespace(id=1, template_id=RUN_TEMPLATE_ID)
    question = SimpleNamespace(id=5, template_id=FOREIGN_TEMPLATE_ID)
    assert question_belongs_to_run(run, question) is False


def test_the_check_matches_how_the_rest_of_the_service_resolves_a_runs_questions() -> None:
    """The write path is being made to agree with the read and scoring paths.

    If those ever stop keying on ``run.template_id`` this check is the wrong
    rule, and this test is what says so.
    """
    source = inspect.getsource(AuditService)
    assert source.count("AuditQuestion.template_id == run.template_id") >= 3


class _FakeResult:
    def __init__(self, entity: object) -> None:
        self._entity = entity

    def scalar_one_or_none(self) -> object:
        return self._entity


class _Savepoint:
    """Stands in for ``AsyncSession.begin_nested()``.

    The route wraps its insert in a SAVEPOINT so a lost unique-constraint race
    can be recovered as an update without discarding the rest of the
    transaction. Nothing here races, so the savepoint is a no-op; the recovery
    itself is exercised in tests/integration/test_audit_response_upsert_by_question.py.
    """

    async def __aenter__(self) -> "_Savepoint":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _RecordingSession:
    def __init__(self, results: list[object]) -> None:
        self._results = list(results)
        self.added: list[object] = []

    async def execute(self, statement: object) -> _FakeResult:  # noqa: ARG002
        return _FakeResult(self._results.pop(0))

    def add(self, entity: object) -> None:
        self.added.append(entity)

    def begin_nested(self) -> _Savepoint:
        return _Savepoint()

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def refresh(self, entity: object) -> None:
        entity.id = 1
        entity.created_at = datetime.now(timezone.utc)
        entity.updated_at = entity.created_at


def _run() -> SimpleNamespace:
    return SimpleNamespace(
        id=11,
        tenant_id=1,
        template_id=RUN_TEMPLATE_ID,
        template=None,
        status=AuditStatus.IN_PROGRESS,
        started_at=None,
        assigned_to_id=1,
        updated_at=datetime.now(timezone.utc),
    )


def _question(template_id: int) -> AuditQuestion:
    return AuditQuestion(
        id=5,
        template_id=template_id,
        question_text="Commercially sensitive question from another organisation",
        question_type="yes_no",
    )


# Queued in the order the route asks for them: the run, the question, then the
# existing answer row for (run, question). The question is resolved before the
# row because the upsert needs it to score whichever branch it takes.
@pytest.mark.asyncio
async def test_create_response_refuses_a_question_from_another_template() -> None:
    db = _RecordingSession([_run(), _question(FOREIGN_TEMPLATE_ID), None])

    with pytest.raises(NotFoundError) as excinfo:
        await create_response(
            run_id=11,
            response_data=AuditResponseCreate(question_id=5, response_value="yes"),
            db=db,
            current_user=SimpleNamespace(id=1, tenant_id=1),
            http_response=Response(),
        )

    assert db.added == []
    # Same message as a genuinely absent question: a distinct one would confirm
    # that a question the caller cannot see exists.
    assert excinfo.value.message == "Audit question not found"
    assert "another organisation" not in excinfo.value.message


@pytest.mark.asyncio
async def test_create_response_still_accepts_a_question_from_its_own_template() -> None:
    """The check must not break the endpoint it guards."""
    db = _RecordingSession([_run(), _question(RUN_TEMPLATE_ID), None])

    result = await create_response(
        run_id=11,
        response_data=AuditResponseCreate(question_id=5, response_value="yes"),
        db=db,
        current_user=SimpleNamespace(id=1, tenant_id=1),
        http_response=Response(),
    )

    assert len(db.added) == 1
    assert result.question_id == 5
