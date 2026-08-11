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
        label="Incident register count",
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
        ("How many of those incidents are closed?", "incident_closed_count"),
        (
            "How many of those incidents are either to do with back injuries or manual handling?",
            "incident_injury_category",
        ),
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
    # With inference off the surface really is a keyword demo, so it keeps saying so
    # — this is the branch on which the demo wording is the true one.
    assert "in this plantex assist demo" in content.lower()


@pytest.mark.asyncio
async def test_ungrounded_question_refuses_without_claiming_to_be_a_demo(monkeypatch):
    """FR-COPILOT-HONEST: with inference on, the refusal states the closed question
    set — not a demo that is "not connected to your registers".

    The registers are wired up on this path, so describing the surface as
    disconnected understates it, and a disclaimer that is visibly wrong is one users
    learn to skip past. It stops short of blaming the question, because the identical
    string is served when the caller lacks the permission or the module is off.
    """
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
    assert "demo is not connected" not in content.lower()
    assert "fixed set of questions from your registers" in content.lower()
    assert "outside the fixed set" not in content.lower()
    assert "plantex assist" in content.lower()
    # The lead clause the permission-gated path relies on too — see
    # tests/integration/test_copilot_grounded_compliance.py.
    assert "cannot answer from live organisation data" in content.lower()
    # The refusal still has to hold: no invented figures, and a pointer to the module.
    assert "will not invent" in content.lower()


@pytest.mark.asyncio
async def test_ungrounded_write_request_refuses_without_demo_wording(monkeypatch):
    """The write refusal carries the same disclosure, so it moves for the same reason."""
    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "ai_copilot_inference_enabled", True)

    service = CopilotService(db=SimpleNamespace())
    content, action, model = await service._generate_response(
        "create an incident for a slip in the yard",
        history=[],
        context={},
        tenant_id=1,
    )
    assert model == "simulated-keyword-match"
    assert action is not None
    assert action["honesty"] == "not_performed"
    assert "from this plantex assist demo" not in content.lower()
    assert "never creates, edits or deletes records" in content.lower()
    assert "nothing was written" in content.lower()


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
    # A citation failure means the intent *was* in the closed set and the figures were
    # computed — the wording quoted something absent from them. Pointing at the fixed
    # question set or at "this demo is not connected" would both misdescribe that.
    assert "could not verify" in content.lower()
    assert "plantex assist" in content.lower()
    assert "demo is not connected" not in content.lower()
    assert "fixed set" not in content.lower()
    assert "92%" not in content


def _incident_depth_responses(
    *,
    total: int,
    refs: list,
    closed: int = 0,
    injury: int = 0,
    minor: int = 0,
    lti: int = 0,
    riddor: int = 0,
    back: int = 0,
    mh: int = 0,
    back_or_mh: int = 0,
    type_rows: list | None = None,
) -> list:
    """Queued DB responses for ``_count_incidents`` (FR-ASSIST-DEPTH-01)."""
    return [
        _Result(scalar=total),
        _Result(scalar=closed),
        _Result(scalar=injury),
        _Result(scalar=minor),
        _Result(scalar=lti),
        _Result(scalar=riddor),
        _Result(scalar=back),
        _Result(scalar=mh),
        _Result(scalar=back_or_mh),
        _Result(rows=type_rows or []),
        _Result(rows=refs),
    ]


def test_format_facts_plain_includes_breakdown_and_deeplinks(grounding: CopilotGroundingService):
    facts = _facts(count=2)
    facts.breakdowns = [("Status breakdown", [("closed", 1), ("not_closed", 1), ("total", 2)])]
    plain = grounding.format_facts_plain(facts)
    assert "| closed | 1 |" in plain
    assert "[INC-2026-0001](/incidents/10)" in plain
    assert grounding.validate_citations(plain, facts) is True


def test_validate_citations_ignores_figures_inside_deeplink_paths(grounding: CopilotGroundingService):
    facts = _facts(count=2)
    reply = "There are 2 incidents including [INC-2026-0001](/incidents/10) and INC-2026-0002."
    assert grounding.validate_citations(reply, facts) is True


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
    db = _RecordingSession(_incident_depth_responses(total=2, refs=rows, closed=1))
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
    db = _RecordingSession(_incident_depth_responses(total=1, refs=[own]))
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

    async def _admin(self, user_id, *, tenant_id):
        return SimpleNamespace(is_superuser=True, id=user_id, tenant_id=tenant_id)

    monkeypatch.setattr(CopilotGroundingService, "_load_caller", _admin)
    rows = [SimpleNamespace(id=1, reference_number="INC-2026-0001")]
    db = _RecordingSession(_incident_depth_responses(total=1, refs=rows))
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]
    outcome = await service.try_answer("How many incidents do we have?", tenant_id=1, user_id=1)
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

    async def _admin(self, user_id, *, tenant_id):
        return SimpleNamespace(is_superuser=True, id=user_id, tenant_id=tenant_id)

    monkeypatch.setattr(CopilotGroundingService, "_load_caller", _admin)

    rows = [
        SimpleNamespace(id=10, reference_number="INC-2026-0001"),
        SimpleNamespace(id=11, reference_number="INC-2026-0002"),
    ]
    db = _RecordingSession(_incident_depth_responses(total=2, refs=rows))
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]
    outcome = await service.try_answer("How many incidents?", tenant_id=1, user_id=1)
    assert outcome.kind == "refused"
    assert outcome.content is None


@pytest.mark.asyncio
async def test_closed_followup_uses_closed_count(monkeypatch):
    monkeypatch.setattr(
        CopilotGroundingService,
        "_provider_available",
        staticmethod(lambda: False),
    )

    async def _admin(self, user_id, *, tenant_id):
        return SimpleNamespace(is_superuser=True, id=user_id, tenant_id=tenant_id)

    monkeypatch.setattr(CopilotGroundingService, "_load_caller", _admin)
    rows = [SimpleNamespace(id=3, reference_number="INC-2026-0003")]
    db = _RecordingSession(
        _incident_depth_responses(total=38, refs=rows, closed=12, injury=8, back=4, mh=2, back_or_mh=5)
    )
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]
    outcome = await service.try_answer("How many of those incidents are closed?", tenant_id=1, user_id=1)
    assert outcome.kind == "answered"
    assert outcome.content is not None
    assert "Closed incident count: **12**" in outcome.content
    assert "| closed | 12 |" in outcome.content
    assert "[INC-2026-0003](/incidents/3)" in outcome.content


@pytest.mark.asyncio
async def test_injury_mh_followup_resolves_from_fact_pack(monkeypatch):
    monkeypatch.setattr(
        CopilotGroundingService,
        "_provider_available",
        staticmethod(lambda: False),
    )

    async def _admin(self, user_id, *, tenant_id):
        return SimpleNamespace(is_superuser=True, id=user_id, tenant_id=tenant_id)

    monkeypatch.setattr(CopilotGroundingService, "_load_caller", _admin)
    rows = [SimpleNamespace(id=9, reference_number="INC-2026-0009")]
    db = _RecordingSession(
        _incident_depth_responses(total=38, refs=rows, closed=12, injury=8, back=4, mh=2, back_or_mh=5)
    )
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]
    outcome = await service.try_answer(
        "How many of those incidents are either to do with back injuries or manual handling?",
        tenant_id=1,
        user_id=1,
    )
    assert outcome.kind == "answered"
    assert outcome.content is not None
    assert "5" in outcome.content
    assert "manual_handling_text_match" in outcome.content or "back_or_manual_handling" in outcome.content


@pytest.mark.asyncio
async def test_try_answer_refuses_incident_without_read_permission(monkeypatch):
    """CORE-01 security: lacking incident:read must not leak register figures."""
    monkeypatch.setattr(
        CopilotGroundingService,
        "_provider_available",
        staticmethod(lambda: False),
    )

    async def _viewer(self, user_id, *, tenant_id):
        return SimpleNamespace(
            is_superuser=False,
            id=user_id,
            tenant_id=tenant_id,
            has_permission=lambda perm: False,
        )

    monkeypatch.setattr(CopilotGroundingService, "_load_caller", _viewer)
    rows = [SimpleNamespace(id=1, reference_number="INC-2026-0001")]
    db = _RecordingSession(_incident_depth_responses(total=1, refs=rows))
    service = CopilotGroundingService(db=db)  # type: ignore[arg-type]
    outcome = await service.try_answer("How many incidents do we have?", tenant_id=1, user_id=9)
    assert outcome.kind == "ungrounded"
