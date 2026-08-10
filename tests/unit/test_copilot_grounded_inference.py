"""PR3b: grounded inference — closed intents, tenant isolation, citation fail-closed."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.config import settings
from src.domain.services.copilot_grounding import (
    CopilotGroundingService,
    GroundedFacts,
    GroundedRef,
    detect_grounded_intent,
)
from src.domain.services.copilot_service import CopilotService, copilot_inference_is_enabled


@pytest.fixture
def grounding():
    return CopilotGroundingService(db=SimpleNamespace())


def _facts(*, tenant_id: int = 1, count: int = 2, refs: list[GroundedRef] | None = None) -> GroundedFacts:
    return GroundedFacts(
        intent="incident_count",
        tenant_id=tenant_id,
        label="Open register incident count",
        count=count,
        refs=refs
        or [
            GroundedRef(module="incident", id=10, reference_number="INC-2026-0001"),
            GroundedRef(module="incident", id=11, reference_number="INC-2026-0002"),
        ],
    )


# --------------------------------------------------------------------------- intents


@pytest.mark.parametrize(
    "message,expected",
    [
        ("How many incidents do we have?", "incident_count"),
        ("what's the number of incidents", "incident_count"),
        ("How many near misses this month?", "near_miss_count"),
        ("total near-miss count", "near_miss_count"),
        ("How many complaints are there?", "complaint_count"),
        ("Show overdue actions", "overdue_actions"),
        ("Which actions are past due?", "overdue_actions"),
        ("What's our ISO 9001 status?", None),
        ("Create an incident for a slip", None),
        ("What is CAPA?", None),
        ("top risks", None),
    ],
)
def test_detect_grounded_intent_closed_set(message, expected):
    assert detect_grounded_intent(message) == expected


# --------------------------------------------------------------------------- citations


def test_validate_citations_accepts_reply_using_only_facts(grounding: CopilotGroundingService):
    facts = _facts()
    reply = "There are 2 incidents on the register, including INC-2026-0001 and INC-2026-0002."
    assert grounding.validate_citations(reply, facts) is True


def test_validate_citations_drops_invented_reference(grounding: CopilotGroundingService):
    facts = _facts()
    reply = "There are 2 incidents; see also RSK-2026-9999."
    assert grounding.validate_citations(reply, facts) is False


def test_validate_citations_drops_invented_percentage(grounding: CopilotGroundingService):
    facts = _facts()
    reply = "Incidents are at 92% of last year with INC-2026-0001."
    assert grounding.validate_citations(reply, facts) is False


def test_validate_citations_drops_invented_count(grounding: CopilotGroundingService):
    facts = _facts(count=2)
    reply = "There are 47 incidents including INC-2026-0001."
    assert grounding.validate_citations(reply, facts) is False


def test_format_facts_plain_passes_its_own_validator(grounding: CopilotGroundingService):
    facts = _facts(count=2)
    plain = grounding.format_facts_plain(facts)
    assert "INC-2026-0001" in plain
    assert grounding.validate_citations(plain, facts) is True


# --------------------------------------------------------------------------- flag gate


def test_inference_flag_defaults_off():
    assert settings.ai_copilot_inference_enabled is False


def test_inference_requires_both_flags(monkeypatch):
    monkeypatch.setattr(settings, "ai_copilot_enabled", False)
    monkeypatch.setattr(settings, "ai_copilot_inference_enabled", True)
    assert copilot_inference_is_enabled() is False

    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "ai_copilot_inference_enabled", False)
    assert copilot_inference_is_enabled() is False

    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "ai_copilot_inference_enabled", True)
    assert copilot_inference_is_enabled() is True


@pytest.mark.asyncio
async def test_flag_off_skips_inference_path(monkeypatch):
    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "ai_copilot_inference_enabled", False)

    called = {"try_answer": False}

    class _Boom:
        def __init__(self, db):
            pass

        async def try_answer(self, *args, **kwargs):
            called["try_answer"] = True
            raise AssertionError("grounding must not run when inference flag is off")

    monkeypatch.setattr(
        "src.domain.services.copilot_grounding.CopilotGroundingService",
        _Boom,
    )

    service = CopilotService(db=SimpleNamespace())
    content, action, model = await service._generate_response(
        "How many incidents do we have?",
        history=[],
        context={},
        tenant_id=1,
    )
    assert called["try_answer"] is False
    assert model == "simulated-keyword-match"
    assert "cannot answer from live organisation data" in content.lower() or "not invent" in content.lower()
    assert action is None


@pytest.mark.asyncio
async def test_ungrounded_question_keeps_simulated_refusal(monkeypatch):
    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "ai_copilot_inference_enabled", True)

    service = CopilotService(db=SimpleNamespace())
    content, action, model = await service._generate_response(
        "What's our ISO 9001 compliance?",
        history=[],
        context={},
        tenant_id=1,
    )
    assert model == "simulated-keyword-match"
    assert action is not None
    assert action["honesty"] == "not_performed"
    assert "92%" not in content


@pytest.mark.asyncio
async def test_citation_failure_returns_honesty_refusal(monkeypatch):
    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "ai_copilot_inference_enabled", True)

    from src.domain.services.copilot_grounding import CITATION_REFUSED

    class _Failing:
        def __init__(self, db):
            pass

        # Signature mirrors CopilotGroundingService.try_answer, which now also
        # receives the caller's user_id for its permission-gated intents.
        async def try_answer(self, question, *, tenant_id, user_id=None):
            return CITATION_REFUSED

    monkeypatch.setattr(
        "src.domain.services.copilot_grounding.CopilotGroundingService",
        _Failing,
    )

    service = CopilotService(db=SimpleNamespace())
    content, action, model = await service._generate_response(
        "How many incidents do we have?",
        history=[],
        context={},
        tenant_id=1,
    )
    assert model == "grounded-citation-refused"
    assert action is None
    # Grounded refuse must not pretend the surface is a disconnected demo.
    assert "outside the fixed set" in content.lower()
    assert "plantex assist" in content.lower()
    assert "demo is not connected" not in content.lower()
    assert "92%" not in content


# --------------------------------------------------------------------------- tenant isolation


class _Result:
    def __init__(self, scalar=None, rows=None, scalars_list=None):
        self._scalar = scalar
        self._rows = rows or []
        self._scalars_list = scalars_list or []

    def scalar(self):
        return self._scalar

    def all(self):
        return self._rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._scalars_list)


class _RecordingSession:
    """Async session stand-in that records compiled SQL text for tenant checks."""

    def __init__(self, responses: list):
        self.responses = list(responses)
        self.statements: list[str] = []

    async def execute(self, statement):
        compiled = str(statement.compile(compile_kwargs={"literal_binds": False}))
        self.statements.append(compiled)
        if not self.responses:
            return _Result(scalar=0, rows=[])
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_gather_facts_scopes_incident_count_to_tenant():
    rows = [
        SimpleNamespace(id=10, reference_number="INC-2026-0001"),
        SimpleNamespace(id=11, reference_number="INC-2026-0002"),
    ]
    db = _RecordingSession(
        [
            _Result(scalar=2),
            _Result(rows=rows),
        ]
    )
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]
    facts = await service.gather_facts("incident_count", tenant_id=42)

    assert facts.tenant_id == 42
    assert facts.count == 2
    assert {r.reference_number for r in facts.refs} == {"INC-2026-0001", "INC-2026-0002"}
    assert db.statements, "expected SQL to be recorded"
    for stmt in db.statements:
        # Bound parameter form still names the column; tenant_id must appear.
        assert "tenant_id" in stmt.lower()


@pytest.mark.asyncio
async def test_gather_facts_never_returns_other_tenant_refs():
    """Cross-tenant: a query that only ever binds tenant 7 must not surface tenant 9's refs.

    Hermetic — we do not open Postgres. The service is the unit under test: it
    must pass the caller's tenant_id into every fact query, which the recording
    session asserts, and it must only package rows the session returned for that
    tenant.
    """
    foreign = SimpleNamespace(id=99, reference_number="INC-OTHER-9999")
    # If gather_facts ever stopped filtering, a careless mock could leak this.
    # Our session only returns tenant-7 rows, mirroring a correct WHERE.
    own = SimpleNamespace(id=1, reference_number="INC-2026-0007")
    db = _RecordingSession([_Result(scalar=1), _Result(rows=[own])])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]
    facts = await service.gather_facts("incident_count", tenant_id=7)

    assert foreign.reference_number not in facts.allowed_refs()
    assert "INC-2026-0007" in facts.allowed_refs()
    assert all("tenant_id" in s.lower() for s in db.statements)


@pytest.mark.asyncio
async def test_try_answer_plain_facts_when_no_provider(monkeypatch):
    monkeypatch.setattr(
        CopilotGroundingService,
        "_provider_available",
        staticmethod(lambda: False),
    )
    rows = [SimpleNamespace(id=1, reference_number="INC-2026-0001")]
    db = _RecordingSession([_Result(scalar=1), _Result(rows=rows)])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]
    outcome = await service.try_answer("How many incidents do we have?", tenant_id=1)
    assert outcome.kind == "answered"
    assert outcome.model_used == "grounded-facts"
    assert outcome.content is not None
    assert "INC-2026-0001" in outcome.content
    assert "1" in outcome.content


@pytest.mark.asyncio
async def test_try_answer_drops_invented_llm_refs(monkeypatch):
    monkeypatch.setattr(
        CopilotGroundingService,
        "_provider_available",
        staticmethod(lambda: True),
    )

    async def _fake_phrase(self, question, facts):
        return "There are 2 incidents; see RSK-2026-9999 for details."

    monkeypatch.setattr(CopilotGroundingService, "_phrase_over_facts", _fake_phrase)

    rows = [
        SimpleNamespace(id=10, reference_number="INC-2026-0001"),
        SimpleNamespace(id=11, reference_number="INC-2026-0002"),
    ]
    db = _RecordingSession([_Result(scalar=2), _Result(rows=rows)])
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]
    outcome = await service.try_answer("How many incidents?", tenant_id=1)
    assert outcome.kind == "refused"
    assert outcome.content is None
