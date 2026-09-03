"""`audit_responses` must be attributed to the tenant that owns the run.

The column has existed in the database since
``20260308_add_tenant_id_to_all_models`` but was never declared on
``AuditResponse``, so no write path ever populated it: every row written since
that migration is unattributed. These tests pin the three things that keeps
fixed — the column is declared, both write paths stamp it, and the value comes
from the *run* rather than from whoever is writing.

Nothing below asserts that any database-level mechanism prevents a
cross-tenant write. In this deployment none does: the application connects as a
role with ``rolbypassrls``, so every row-level security policy is bypassed and
the application layer is the only layer enforcing isolation.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.responses import Response

from src.api.routes.audits import create_response
from src.api.schemas.audit import AuditResponseCreate
from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.audit import AuditQuestion, AuditResponse, AuditRun, AuditStatus
from src.domain.services.audit_service import AuditService, require_run_tenant_id

SRC = Path(__file__).resolve().parents[2] / "src"

RUN_TENANT = 7
CALLER_TENANT = 42


# ---------------------------------------------------------------------------
# The declaration itself
# ---------------------------------------------------------------------------


def test_audit_response_tenant_id_is_declared_required_indexed_and_keyed_to_tenants() -> None:
    """The model, not the database, is what makes the write path populate this.

    Relaxing the column to ``nullable=True`` would make every test below pass
    while silently restoring the defect, so the declaration is asserted directly.
    """
    column = AuditResponse.__table__.c.tenant_id
    assert column.nullable is False
    assert column.index is True
    assert {fk.target_fullname for fk in column.foreign_keys} == {"tenants.id"}


def test_declaring_the_column_does_not_change_the_api_contract() -> None:
    """The response schema is unchanged, so no client sees a new field."""
    from src.api.schemas.audit import AuditResponseCreate as _Create
    from src.api.schemas.audit import AuditResponseResponse as _Response

    assert "tenant_id" not in _Response.model_fields
    assert "tenant_id" not in _Create.model_fields


def test_a_client_supplied_tenant_id_is_rejected_by_the_write_schema() -> None:
    """B-10: unknown fields (including tenant_id) are forbidden, not ignored.

    Previously Pydantic dropped ``tenant_id`` under ``extra="ignore"``. With
    ``extra="forbid"`` the request fails validation instead — still preventing
    a client from steering tenancy via the body, and failing loudly.
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        AuditResponseCreate.model_validate({"question_id": 1, "tenant_id": 999})
    assert "tenant_id" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Where the value comes from
# ---------------------------------------------------------------------------


def test_require_run_tenant_id_returns_the_tenant_recorded_on_the_run() -> None:
    run = SimpleNamespace(id=1, tenant_id=RUN_TENANT)
    assert require_run_tenant_id(run) == RUN_TENANT


def test_require_run_tenant_id_refuses_a_run_with_no_tenant() -> None:
    """`audit_runs.tenant_id` is nullable in the migrated schema.

    Neither CI harness can hold such a row — SQLite builds the schema from the
    model (``nullable=False``) and a fresh CI Postgres has zero NULLs, so
    ``20260710_ar_tenant_nn`` applies ``SET NOT NULL`` there. The migrated
    production schema kept the column nullable because it had NULLs at the time,
    which is why this branch is reachable in production and is asserted here
    rather than through either harness.

    Writing the caller's tenant instead would invent an attribution that no
    authorisation decision supports; writing NULL is the defect being removed.
    """
    run = SimpleNamespace(id=4242, tenant_id=None)

    with pytest.raises(BadRequestError) as excinfo:
        require_run_tenant_id(run)

    assert excinfo.value.http_status == 400
    assert excinfo.value.details == {"run_id": 4242}
    assert "not attributed to a tenant" in excinfo.value.message


def test_every_audit_response_construction_derives_its_tenant_from_the_run() -> None:
    """A new write path that forgets this reintroduces unattributed rows.

    Requiring the ``require_run_tenant_id(run)`` call rather than any expression
    mentioning ``run`` also means a new site inherits the refusal above instead
    of writing a NULL of its own.
    """
    sites = _audit_response_construction_sites()

    assert len(sites) >= 2, "scan found no AuditResponse(...) constructions in src/ — it cannot pass vacuously"
    assert {path for path, _, _ in sites} == {
        "api/routes/audits.py",
        "domain/services/audit_service.py",
    }

    for path, lineno, expression in sites:
        assert expression is not None, f"{path}:{lineno} constructs AuditResponse without a tenant_id"
        assert expression == "require_run_tenant_id(run)", (
            f"{path}:{lineno} stamps tenant_id from {expression!r}. It must be "
            "require_run_tenant_id(run): the run is the object the caller's "
            "authorisation check passed against, and stamping the caller's own "
            "tenant relabels the row to match whoever wrote it."
        )


def _audit_response_construction_sites() -> list[tuple[str, int, str | None]]:
    """Return ``(path, lineno, tenant_id expression)`` for each construction."""
    sites: list[tuple[str, int, str | None]] = []
    for path in sorted(SRC.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call) or getattr(node.func, "id", None) != "AuditResponse":
                continue
            expression = next(
                (ast.get_source_segment(source, kw.value) for kw in node.keywords if kw.arg == "tenant_id"),
                None,
            )
            sites.append((str(path.relative_to(SRC)), node.lineno, expression))
    return sites


# ---------------------------------------------------------------------------
# The route, exercised against a session that does not filter for it
# ---------------------------------------------------------------------------


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
    """Returns queued results in order and records what was added.

    Standing in for the session is what makes the assertion below possible: the
    real query filters the run to the caller's own tenant, so through a database
    the run's tenant and the caller's can never differ at the point the row is
    built, and no end-to-end test can tell the two sources apart.
    """

    def __init__(self, results: list[object]) -> None:
        self._results = list(results)
        self.statements: list[object] = []
        self.added: list[object] = []

    async def execute(self, statement: object) -> _FakeResult:
        self.statements.append(statement)
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
        # Stand in for the DEFAULTs the database would supply on insert.
        entity.id = 1
        entity.created_at = datetime.now(timezone.utc)
        entity.updated_at = entity.created_at


class _ServiceRecordingSession(_RecordingSession):
    def __init__(self, results: list[object], question: AuditQuestion) -> None:
        super().__init__(results)
        self.question = question

    async def get(self, model: type, entity_id: int) -> AuditQuestion:
        assert model is AuditQuestion
        assert entity_id == self.question.id
        return self.question


def _run(*, tenant_id: int | None, template_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        id=11,
        tenant_id=tenant_id,
        template_id=template_id,
        template=None,
        status=AuditStatus.IN_PROGRESS,
        started_at=None,
        assigned_to_id=1,
        updated_at=datetime.now(timezone.utc),
    )


def _question(*, question_id: int = 5, template_id: int = 1) -> AuditQuestion:
    return AuditQuestion(
        id=question_id,
        template_id=template_id,
        question_text="Are the guards fitted?",
        question_type="yes_no",
    )


# Queued in the order the route asks for them: the run, the question, then the
# existing answer row for (run, question). The question is resolved before the
# row because the upsert needs it to score whichever branch it takes.
@pytest.mark.asyncio
async def test_created_response_is_stamped_with_the_runs_tenant_not_the_callers() -> None:
    """Fails if the stamp is ever "simplified" to ``current_user.tenant_id``."""
    run = _run(tenant_id=RUN_TENANT)
    db = _RecordingSession([run, _question(), None])

    await create_response(
        run_id=run.id,
        response_data=AuditResponseCreate(question_id=5, response_value="yes"),
        db=db,
        current_user=SimpleNamespace(id=1, tenant_id=CALLER_TENANT),
        http_response=Response(),
    )

    assert len(db.added) == 1
    assert db.added[0].tenant_id == RUN_TENANT
    assert db.added[0].tenant_id != CALLER_TENANT


@pytest.mark.asyncio
async def test_service_discards_a_caller_supplied_tenant_id_before_constructing_response() -> None:
    """Internal callers pass dictionaries and do not benefit from schema filtering."""
    run = _run(tenant_id=RUN_TENANT)
    run.template = SimpleNamespace(audit_type="inspection", tags_json=[])
    question = _question()
    db = _ServiceRecordingSession([run, None], question)
    supplied = {
        "question_id": question.id,
        "response_value": "yes",
        "tenant_id": CALLER_TENANT,
    }

    await AuditService(db).create_audit_response(
        run.id,
        supplied,
        tenant_id=RUN_TENANT,
    )

    assert len(db.added) == 1
    assert db.added[0].tenant_id == RUN_TENANT
    assert db.added[0].tenant_id != CALLER_TENANT
    assert supplied["tenant_id"] == CALLER_TENANT


@pytest.mark.asyncio
async def test_create_response_refuses_a_run_that_is_not_attributed_to_a_tenant() -> None:
    """No row is written, rather than one carrying the caller's tenant."""
    run = _run(tenant_id=None)
    db = _RecordingSession([run, _question(), None])

    with pytest.raises(BadRequestError, match="not attributed to a tenant"):
        await create_response(
            run_id=run.id,
            response_data=AuditResponseCreate(question_id=5, response_value="yes"),
            db=db,
            current_user=SimpleNamespace(id=1, tenant_id=CALLER_TENANT),
            http_response=Response(),
        )

    assert db.added == []


@pytest.mark.asyncio
async def test_create_response_looks_up_the_run_on_an_exact_tenant_match() -> None:
    """The filter used to be ``or_(tenant_id == caller, tenant_id IS NULL)``.

    That second branch is live: the migrated schema still allows NULL and
    production holds 37 such runs out of 83, so any authenticated caller could
    write into an unattributed run belonging to another organisation. RLS does
    not cover it — the application role bypasses RLS entirely.

    This is asserted on the compiled statement rather than end to end because
    the row the removed branch matched cannot exist in either test harness:
    ``audit_runs.tenant_id`` is NOT NULL in both. The shape of the query is
    therefore the strongest available evidence.
    """
    db = _RecordingSession([None])

    with pytest.raises(NotFoundError, match="Audit run not found"):
        await create_response(
            run_id=11,
            response_data=AuditResponseCreate(question_id=5, response_value="yes"),
            db=db,
            current_user=SimpleNamespace(id=1, tenant_id=CALLER_TENANT),
            http_response=Response(),
        )

    assert len(db.statements) == 1
    sql = str(db.statements[0].compile(compile_kwargs={"literal_binds": True})).upper()
    assert "TENANT_ID" in sql
    assert "IS NULL" not in sql
    assert " OR " not in sql


@pytest.mark.asyncio
async def test_create_response_matches_nothing_when_the_caller_has_no_tenant() -> None:
    """A tenant-less caller must not fall through to an unscoped query."""
    db = _RecordingSession([None])

    with pytest.raises(NotFoundError, match="Audit run not found"):
        await create_response(
            run_id=11,
            response_data=AuditResponseCreate(question_id=5, response_value="yes"),
            db=db,
            current_user=SimpleNamespace(id=1, tenant_id=None),
            http_response=Response(),
        )

    sql = str(db.statements[0].compile(compile_kwargs={"literal_binds": True})).upper()
    assert "FALSE" in sql or "1 != 1" in sql


def test_answer_write_run_lookup_has_no_permissive_tenant_branch() -> None:
    """Guards the shape as well as one compiled statement.

    The lookup itself now lives in ``_load_run_for_answer_write``, which the
    POST and the by-question PUT both go through, so both handlers and the
    shared helper are scanned. Scanning only ``create_response`` would leave the
    branch that matched NULL-tenant runs free to come back one level down.
    """
    import inspect

    from src.api.routes.audits import _load_run_for_answer_write, upsert_response_by_question

    for handler in (create_response, upsert_response_by_question, _load_run_for_answer_write):
        source = inspect.getsource(handler)
        assert "is_(None)" not in source, handler.__name__
        assert "or_(" not in source, handler.__name__
        assert "AuditRun.tenant_id" not in source, handler.__name__


# ---------------------------------------------------------------------------
# Reading rows written before the column was declared
# ---------------------------------------------------------------------------


def test_a_row_loaded_with_a_null_tenant_is_still_readable() -> None:
    """315 production rows have NULL tenant_id and must keep loading.

    Declaring ``nullable=False`` changes what the *test* schema enforces, not
    what production holds: no migration lands in this step, so the column stays
    nullable there. SQLAlchemy validates nullability on flush, not on load, and
    this asserts that rather than assuming it.
    """
    response = AuditResponse()
    state = response.__dict__
    state.update({"id": 1, "run_id": 1, "question_id": 1, "tenant_id": None})

    assert response.tenant_id is None
    assert repr(response).startswith("<AuditResponse(id=1")


def test_audit_response_tenancy_matches_its_already_hardened_sibling() -> None:
    """``audit_findings`` is the same relationship to ``audit_runs``."""
    from src.domain.models.audit import AuditFinding

    finding = AuditFinding.__table__.c.tenant_id
    response = AuditResponse.__table__.c.tenant_id
    assert (response.nullable, response.index) == (finding.nullable, finding.index)
    assert {fk.target_fullname for fk in response.foreign_keys} == {fk.target_fullname for fk in finding.foreign_keys}


def test_audit_run_is_a_credible_source_of_truth_for_its_childrens_tenant() -> None:
    """The run is only an authority if it is itself required to be attributed."""
    assert AuditRun.__table__.c.tenant_id.nullable is False
