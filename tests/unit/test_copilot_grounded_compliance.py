"""Grounded copilot intent for Compliance Schedule obligations.

Hermetic. The register queries are asserted through a recording session so the
tenant scope, the live-row predicates and the due-date predicate are checked as
compiled SQL; the real counts are checked against a real database in
``tests/integration/test_copilot_grounded_compliance.py``.
"""

from __future__ import annotations

import inspect
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.core.config import settings
from src.domain.models.user import Role, User
from src.domain.services.compliance_schedule_kill_switch import (
    KILL_SWITCH_FLAG_KEY,
    reset_compliance_schedule_kill_switch_cache,
)
from src.domain.services.compliance_schedule_policy import derive_status
from src.domain.services.copilot_grounding import (
    COMPLIANCE_SCHEDULE_INTENTS,
    GROUNDED_INTENTS,
    CopilotGroundingService,
    detect_grounded_intent,
)

CALLER_ID = 501
TENANT_ID = 77


# --------------------------------------------------------------------------- doubles


class _Result:
    def __init__(self, scalar=None, rows=None, entities=None):
        self._scalar = scalar
        self._rows = rows or []
        self._entities = entities or []

    def scalar(self):
        return self._scalar

    def all(self):
        return self._rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._entities, first=lambda: None)


class _UserResult:
    def __init__(self, user):
        self._user = user

    def scalars(self):
        return SimpleNamespace(first=lambda: self._user)


class _RecordingSession:
    """Records compiled SQL. Answers the caller lookup from ``user``, the rest in order."""

    def __init__(self, *, user=None, results=None):
        self.user = user
        self.results = list(results or [])
        self.statements: list[str] = []

    async def execute(self, statement):
        compiled = str(statement.compile(compile_kwargs={"literal_binds": False}))
        self.statements.append(compiled)
        if "FROM users" in compiled:
            return _UserResult(self.user)
        if not self.results:
            return _Result(scalar=0, rows=[])
        return self.results.pop(0)

    @property
    def register_statements(self) -> list[str]:
        return [s for s in self.statements if "compliance_requirements" in s]


def _user(*, permissions: list[str] | None, is_superuser: bool = False) -> User:
    """A real User whose real ``has_permission`` will be asked the real question."""
    user = User(
        id=CALLER_ID,
        email="caller@example.com",
        hashed_password="unused",
        first_name="Cal",
        last_name="Ler",
        is_active=True,
        is_superuser=is_superuser,
        tenant_id=TENANT_ID,
    )
    if permissions is None:
        user.roles = []
    else:
        import json

        user.roles = [Role(id=1, name="compliance-reader", permissions=json.dumps(permissions))]
    return user


@pytest.fixture
def module_on(monkeypatch):
    monkeypatch.setattr(settings, "compliance_schedule_enabled", True)
    reset_compliance_schedule_kill_switch_cache()
    yield
    reset_compliance_schedule_kill_switch_cache()


@pytest.fixture
def module_off(monkeypatch):
    monkeypatch.setattr(settings, "compliance_schedule_enabled", False)
    reset_compliance_schedule_kill_switch_cache()
    yield
    reset_compliance_schedule_kill_switch_cache()


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Answers are the deterministic fact formatter, never a provider."""
    monkeypatch.setattr(CopilotGroundingService, "_provider_available", staticmethod(lambda: False))


def _reader_session(*, count: int, statutory: int = 0, refs: list[str] | None = None) -> _RecordingSession:
    rows = [SimpleNamespace(id=i + 1, reference_number=ref) for i, ref in enumerate(refs or [])]
    return _RecordingSession(
        user=_user(permissions=["compliance_schedule:read"]),
        results=[_Result(scalar=statutory), _Result(scalar=count), _Result(rows=rows)],
    )


# --------------------------------------------------------------------------- matching


@pytest.mark.parametrize(
    "message,expected",
    [
        ("How many overdue compliance obligations do we have?", "compliance_overdue"),
        ("which obligations are overdue", "compliance_overdue"),
        ("are any statutory inspections past due?", "compliance_overdue"),
        ("total compliance requirements that are expired", "compliance_overdue"),
        ("Which compliance obligations are due soon?", "compliance_due_soon"),
        ("what obligations are coming up", "compliance_due_soon"),
        ("obligations due in the next month", "compliance_due_soon"),
        # Not the register: the simulator's ISO refusal must keep these.
        ("What's our ISO 9001 status?", None),
        ("How compliant are we with ISO 45001?", None),
        ("is our compliance good", None),
        # Register vocabulary but no due-date question at all.
        ("how many compliance obligations do we have", None),
    ],
)
def test_compliance_intents_are_matched(message, expected):
    assert detect_grounded_intent(message) == expected


@pytest.mark.parametrize(
    "message,expected",
    [
        # "action" keeps its existing owner, exactly as before this intent existed.
        ("Show overdue compliance actions", "overdue_actions"),
        ("which compliance actions are past due?", "overdue_actions"),
        # Overdue is asked first, so a question asking both resolves one way, always.
        ("which compliance obligations are overdue or due soon?", "compliance_overdue"),
        # The four original intents are untouched.
        ("How many incidents do we have?", "incident_count"),
        ("How many complaints are there?", "complaint_count"),
    ],
)
def test_ambiguous_questions_resolve_deterministically(message, expected):
    assert detect_grounded_intent(message) == expected


def test_every_grounded_intent_is_registered_and_dispatchable():
    assert COMPLIANCE_SCHEDULE_INTENTS <= GROUNDED_INTENTS


@pytest.mark.asyncio
async def test_gather_facts_has_a_branch_for_every_declared_intent():
    """A new member of GROUNDED_INTENTS must not silently answer another question."""
    for intent in sorted(GROUNDED_INTENTS):
        service = CopilotGroundingService(db=_RecordingSession())  # type: ignore[arg-type]
        facts = await service.gather_facts(intent, tenant_id=TENANT_ID)
        assert facts.intent == intent


@pytest.mark.asyncio
async def test_gather_facts_still_rejects_an_unknown_intent():
    service = CopilotGroundingService(db=_RecordingSession())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        await service.gather_facts("compliance_invented", tenant_id=TENANT_ID)


def test_due_soon_horizon_agrees_with_the_register_itself():
    """The copilot's "due soon" and the register's due_soon badge are one definition."""
    from src.domain.services import copilot_grounding

    register_default = inspect.signature(derive_status).parameters["due_soon_days"].default
    assert copilot_grounding._DUE_SOON_HORIZON_DAYS == register_default


# --------------------------------------------------------------------------- feature gate


@pytest.mark.asyncio
async def test_module_off_answers_nothing_and_reads_nothing(module_off):
    db = _reader_session(count=9, statutory=9, refs=["CSR-2026-0001"])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]

    outcome = await service.try_answer(
        "How many overdue compliance obligations do we have?",
        tenant_id=TENANT_ID,
        user_id=CALLER_ID,
    )

    assert outcome.kind == "ungrounded"
    assert outcome.content is None
    assert db.statements == [], "a tenant with the module off must not cost even a lookup"


@pytest.mark.asyncio
async def test_kill_switch_engaged_answers_nothing(module_on, monkeypatch):
    """The opener is on, but an operator has closed the module at runtime."""
    from src.domain.services import compliance_schedule_kill_switch as ks

    monkeypatch.setattr(ks, "_verdict", ks._Verdict(engaged=True, asked_at=0.0, expires_at=float("inf")))
    db = _reader_session(count=4, statutory=4, refs=["CSR-2026-0001"])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]

    outcome = await service.try_answer(
        "which obligations are overdue",
        tenant_id=TENANT_ID,
        user_id=CALLER_ID,
    )

    assert outcome.kind == "ungrounded"
    assert db.statements == []


def test_the_gate_reads_the_flag_the_module_is_deployed_with(module_off):
    """Unset COMPLIANCE_SCHEDULE_ENABLED means closed, not open."""
    from src.domain.services.compliance_schedule_kill_switch import compliance_schedule_is_open_last_known

    assert settings.compliance_schedule_enabled is False
    assert compliance_schedule_is_open_last_known() is False
    assert KILL_SWITCH_FLAG_KEY == "compliance_schedule_kill_switch"


# --------------------------------------------------------------------------- permission gate


@pytest.mark.asyncio
async def test_caller_without_the_permission_gets_no_count(module_on):
    db = _RecordingSession(
        user=_user(permissions=["incident:read", "complaint:read"]),
        results=[_Result(scalar=9), _Result(scalar=9), _Result(rows=[SimpleNamespace(id=1, reference_number="CSR-1")])],
    )
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]

    outcome = await service.try_answer(
        "How many overdue compliance obligations do we have?",
        tenant_id=TENANT_ID,
        user_id=CALLER_ID,
    )

    assert outcome.kind == "ungrounded"
    assert outcome.content is None
    assert db.register_statements == [], "the register was queried for a caller with no grant"


@pytest.mark.asyncio
async def test_caller_with_no_roles_at_all_gets_no_count(module_on):
    db = _RecordingSession(user=_user(permissions=None), results=[_Result(scalar=3), _Result(scalar=3)])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]

    outcome = await service.try_answer("which obligations are overdue", tenant_id=TENANT_ID, user_id=CALLER_ID)

    assert outcome.kind == "ungrounded"
    assert db.register_statements == []


@pytest.mark.asyncio
async def test_unidentified_caller_gets_no_count(module_on):
    """No user_id means no evidence of a grant, so no answer."""
    db = _reader_session(count=9, statutory=9, refs=["CSR-2026-0001"])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]

    outcome = await service.try_answer("which obligations are overdue", tenant_id=TENANT_ID, user_id=None)

    assert outcome.kind == "ungrounded"
    assert db.statements == []


@pytest.mark.asyncio
async def test_caller_who_does_not_resolve_gets_no_count(module_on):
    """A user id that matches nobody in this tenant is not a permission bearer."""
    db = _RecordingSession(user=None, results=[_Result(scalar=9), _Result(scalar=9)])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]

    outcome = await service.try_answer("which obligations are overdue", tenant_id=TENANT_ID, user_id=CALLER_ID)

    assert outcome.kind == "ungrounded"
    assert db.register_statements == []


@pytest.mark.asyncio
async def test_caller_lookup_is_scoped_and_excludes_disabled_accounts(module_on):
    db = _reader_session(count=0, refs=[])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]

    await service.try_answer("which obligations are overdue", tenant_id=TENANT_ID, user_id=CALLER_ID)

    lookup = next(s for s in db.statements if "FROM users" in s)
    assert "users.tenant_id" in lookup
    assert "users.is_active" in lookup
    assert "users.deleted_at IS NULL" in lookup


@pytest.mark.asyncio
async def test_superuser_is_a_reader(module_on):
    db = _RecordingSession(
        user=_user(permissions=None, is_superuser=True),
        results=[
            _Result(scalar=1),
            _Result(scalar=2),
            _Result(rows=[SimpleNamespace(id=1, reference_number="CSR-2026-0001")]),
        ],
    )
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]

    outcome = await service.try_answer("which obligations are overdue", tenant_id=TENANT_ID, user_id=CALLER_ID)

    assert outcome.kind == "answered"


# --------------------------------------------------------------------------- facts


@pytest.mark.asyncio
async def test_overdue_answer_states_the_count_and_cites_only_real_refs(module_on):
    db = _reader_session(count=3, statutory=2, refs=["CSR-2026-0001", "CSR-2026-0002"])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]

    outcome = await service.try_answer(
        "How many overdue compliance obligations do we have?",
        tenant_id=TENANT_ID,
        user_id=CALLER_ID,
    )

    assert outcome.kind == "answered"
    assert outcome.model_used == "grounded-facts"
    assert outcome.content is not None
    assert "Overdue compliance obligation count: 3." in outcome.content
    assert "Statutory overdue: 2." in outcome.content
    assert "CSR-2026-0001" in outcome.content and "CSR-2026-0002" in outcome.content
    assert "showing 2 of 3" in outcome.content


@pytest.mark.asyncio
async def test_zero_overdue_says_so_without_inventing_a_reference(module_on):
    db = _reader_session(count=0, statutory=0, refs=[])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]

    outcome = await service.try_answer("which obligations are overdue", tenant_id=TENANT_ID, user_id=CALLER_ID)

    assert outcome.kind == "answered"
    assert outcome.content is not None
    assert "Overdue compliance obligation count: 0." in outcome.content
    assert "No matching records in this organisation." in outcome.content
    assert "CSR-" not in outcome.content


@pytest.mark.asyncio
async def test_the_plain_formatter_passes_its_own_citation_check(module_on):
    db = _reader_session(count=2, statutory=1, refs=["CSR-2026-0001", "CSR-2026-0002"])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]
    facts = await service.gather_facts("compliance_overdue", tenant_id=TENANT_ID)

    plain = service.format_facts_plain(facts)
    assert service.validate_citations(plain, facts) is True


@pytest.mark.asyncio
async def test_an_invented_obligation_reference_is_still_rejected(module_on):
    db = _reader_session(count=2, statutory=1, refs=["CSR-2026-0001"])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]
    facts = await service.gather_facts("compliance_overdue", tenant_id=TENANT_ID)

    assert service.validate_citations("Two are overdue, including CSR-2026-9999.", facts) is False


@pytest.mark.asyncio
async def test_due_soon_reports_its_horizon(module_on):
    db = _RecordingSession(
        user=_user(permissions=["compliance_schedule:read"]),
        results=[_Result(scalar=5), _Result(rows=[SimpleNamespace(id=1, reference_number="CSR-2026-0003")])],
    )
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]

    outcome = await service.try_answer(
        "Which compliance obligations are due soon?",
        tenant_id=TENANT_ID,
        user_id=CALLER_ID,
    )

    assert outcome.kind == "answered"
    assert outcome.content is not None
    assert "Compliance obligations due soon: 5." in outcome.content
    assert "Horizon days: 30." in outcome.content


# --------------------------------------------------------------------------- SQL shape


@pytest.mark.asyncio
async def test_register_queries_are_tenant_scoped_and_live_rows_only(module_on):
    db = _reader_session(count=1, statutory=1, refs=["CSR-2026-0001"])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]

    await service.gather_facts("compliance_overdue", tenant_id=TENANT_ID)

    assert db.register_statements, "expected register SQL to be recorded"
    for stmt in db.register_statements:
        assert "compliance_requirements.tenant_id" in stmt
        assert "compliance_requirements.deleted_at IS NULL" in stmt
        assert "compliance_requirements.is_active" in stmt


@pytest.mark.asyncio
async def test_overdue_excludes_today_and_due_soon_includes_it(module_on):
    """Boundary: an obligation due today is due, not overdue — as derive_status says."""
    today = datetime.now(timezone.utc).date()
    assert derive_status(today, today) == "due_soon"
    assert derive_status(today, today - timedelta(days=1)) == "overdue"

    overdue_db = _reader_session(count=0)
    await CopilotGroundingService(db=overdue_db).gather_facts(  # type: ignore[arg-type]
        "compliance_overdue", tenant_id=TENANT_ID
    )
    assert any("next_due_date <" in s and "next_due_date <=" not in s for s in overdue_db.register_statements)

    soon_db = _RecordingSession(results=[_Result(scalar=0), _Result(rows=[])])
    await CopilotGroundingService(db=soon_db).gather_facts(  # type: ignore[arg-type]
        "compliance_due_soon", tenant_id=TENANT_ID
    )
    assert any("next_due_date >=" in s and "next_due_date <=" in s for s in soon_db.register_statements)


@pytest.mark.asyncio
async def test_due_soon_horizon_is_bounded_at_thirty_days(module_on):
    """The upper bound is a real date 30 days out, not an open-ended range."""
    captured: list[date] = []

    class _Capturing(_RecordingSession):
        async def execute(self, statement):
            compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
            self.statements.append(compiled)
            for token in compiled.split("'"):
                try:
                    captured.append(date.fromisoformat(token))
                except ValueError:
                    continue
            return _Result(scalar=0, rows=[])

    db = _Capturing()
    await CopilotGroundingService(db=db).gather_facts(  # type: ignore[arg-type]
        "compliance_due_soon", tenant_id=TENANT_ID
    )

    today = datetime.now(timezone.utc).date()
    assert min(captured) == today
    assert max(captured) == today + timedelta(days=30)
