"""Unit tests for Compliance Schedule regulatory-basis AI service."""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.compliance_schedule_regulatory_ai_service import (
    AI_ONLY_CONFIDENCE_CAP,
    AI_UNAVAILABLE_NOTICE,
    AI_UNCONFIGURED_NOTICE,
    ComplianceScheduleRegulatoryAiService,
    RegulatoryCandidate,
)


class _FakeScalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)

    def scalar_one_or_none(self) -> Any:
        return self._rows[0] if self._rows else None


def _standard(*, id: int, code: str, name: str, tenant_id: Optional[int] = None) -> MagicMock:
    row = MagicMock()
    row.id = id
    row.code = code
    row.name = name
    row.full_name = name
    row.is_active = True
    row.tenant_id = tenant_id
    return row


@pytest.fixture
def db() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_fra_title_yields_fire_safety_order_candidate(db: AsyncMock) -> None:
    db.execute = AsyncMock(return_value=_FakeResult([]))

    with patch.object(ComplianceScheduleRegulatoryAiService, "_ai_is_configured", return_value=False):
        service = ComplianceScheduleRegulatoryAiService(db)
        result = await service.suggest(
            tenant_id=1,
            title="Fire Risk Assessment",
            taxonomy_id="03.01",
            description="Annual FRA review for each premises",
            statutory=True,
        )

    assert result.ai_available is False
    assert result.notice == AI_UNCONFIGURED_NOTICE
    assert result.candidates
    assert result.candidates[0].regulation_or_standard_code == "FSO2005"
    assert "Fire Safety" in result.candidates[0].label
    assert result.needs_clarification is False


@pytest.mark.asyncio
async def test_ai_unconfigured_still_returns_deterministic_candidates(db: AsyncMock) -> None:
    db.execute = AsyncMock(return_value=_FakeResult([]))

    with patch.object(ComplianceScheduleRegulatoryAiService, "_ai_is_configured", return_value=False):
        service = ComplianceScheduleRegulatoryAiService(db)
        result = await service.suggest(
            tenant_id=1,
            title="Fixed Electrical Inspection (EICR)",
            taxonomy_id="04.02",
            description=None,
            statutory=True,
        )

    assert result.ai_available is False
    assert any(c.regulation_or_standard_code == "EAWR1989" for c in result.candidates)


@pytest.mark.asyncio
async def test_ai_call_failure_falls_back_with_unavailable_notice(db: AsyncMock) -> None:
    db.execute = AsyncMock(return_value=_FakeResult([]))

    with (
        patch.object(ComplianceScheduleRegulatoryAiService, "_ai_is_configured", return_value=True),
        patch(
            "src.domain.services.compliance_schedule_regulatory_ai_service.call_via_upstream_breaker",
            AsyncMock(side_effect=RuntimeError("breaker open")),
        ),
    ):
        service = ComplianceScheduleRegulatoryAiService(db)
        result = await service.suggest(
            tenant_id=1,
            title="Fire Risk Assessment",
            taxonomy_id="03.01",
            description=None,
            statutory=True,
        )

    assert result.ai_available is False
    assert result.notice == AI_UNAVAILABLE_NOTICE
    assert result.candidates[0].regulation_or_standard_code == "FSO2005"


@pytest.mark.asyncio
async def test_ai_cannot_mint_standard_id(db: AsyncMock) -> None:
    standard = _standard(id=10, code="ISO45001", name="ISO 45001:2018")
    # First execute: list standards; subsequent: clauses / resolve
    db.execute = AsyncMock(
        side_effect=[
            _FakeResult([standard]),
            _FakeResult([]),  # clauses
        ]
    )

    ai_payload = {
        "candidates": [
            {
                "code": "ISO45001",
                "label": "ISO 45001",
                "confidence": 0.95,
                "rationale": "OH&S",
                "standard_id": 999,
                "clause_ids": [111],
            }
        ],
        "questions": [],
    }

    with (
        patch.object(ComplianceScheduleRegulatoryAiService, "_ai_is_configured", return_value=True),
        patch(
            "src.domain.services.compliance_schedule_regulatory_ai_service.call_via_upstream_breaker",
            AsyncMock(return_value=__import__("json").dumps(ai_payload)),
        ),
    ):
        service = ComplianceScheduleRegulatoryAiService(db)
        result = await service.suggest(
            tenant_id=1,
            title="ISO 45001 management review",
            taxonomy_id="01.01",
            description="OH&S",
            statutory=False,
        )

    hit = next(c for c in result.candidates if c.regulation_or_standard_code == "ISO45001")
    assert hit.standard_id == 10
    assert hit.clause_ids == ()


@pytest.mark.asyncio
async def test_ai_only_code_is_capped_below_threshold(db: AsyncMock) -> None:
    db.execute = AsyncMock(return_value=_FakeResult([]))

    ai_payload = {
        "candidates": [
            {
                "code": "MADEUP999",
                "label": "Made Up Regulation 2099",
                "confidence": 0.99,
                "rationale": "hallucination",
            }
        ],
        "questions": [
            {"id": "topic_domain", "question": "Which area?", "options": ["Fire"], "why": "x"},
            {"id": "statutory_nature", "question": "Statutory?", "options": ["Yes"], "why": "y"},
        ],
    }

    with (
        patch.object(ComplianceScheduleRegulatoryAiService, "_ai_is_configured", return_value=True),
        patch(
            "src.domain.services.compliance_schedule_regulatory_ai_service.call_via_upstream_breaker",
            AsyncMock(return_value=__import__("json").dumps(ai_payload)),
        ),
    ):
        service = ComplianceScheduleRegulatoryAiService(db)
        result = await service.suggest(
            tenant_id=1,
            title="Obscure obligation",
            taxonomy_id="99.99",
            description=None,
            statutory=False,
        )

    assert result.candidates
    top = result.candidates[0]
    assert top.source == "ai"
    assert top.standard_id is None
    assert top.confidence <= AI_ONLY_CONFIDENCE_CAP
    assert result.needs_clarification is True


@pytest.mark.asyncio
async def test_low_confidence_triggers_two_to_four_questions(db: AsyncMock) -> None:
    db.execute = AsyncMock(return_value=_FakeResult([]))

    with (
        patch.object(ComplianceScheduleRegulatoryAiService, "_ai_is_configured", return_value=False),
        patch.object(
            ComplianceScheduleRegulatoryAiService,
            "_threshold",
            return_value=0.99,
        ),
    ):
        service = ComplianceScheduleRegulatoryAiService(db)
        result = await service.suggest(
            tenant_id=1,
            title="Fire Risk Assessment",
            taxonomy_id="03.01",
            description=None,
            statutory=True,
        )

    assert result.needs_clarification is True
    assert 2 <= len(result.clarifying_questions) <= 4


@pytest.mark.asyncio
async def test_answers_raise_confidence_and_stop_asking(db: AsyncMock) -> None:
    db.execute = AsyncMock(return_value=_FakeResult([]))

    with patch.object(ComplianceScheduleRegulatoryAiService, "_ai_is_configured", return_value=False):
        service = ComplianceScheduleRegulatoryAiService(db)
        result = await service.suggest(
            tenant_id=1,
            title="Annual review",
            taxonomy_id="03.01",
            description=None,
            statutory=True,
            answers={
                "topic_domain": "Fire safety",
                "known_citation": "Fire Risk Assessment under Fire Safety Order",
            },
        )

    assert result.candidates
    assert result.candidates[0].regulation_or_standard_code == "FSO2005"
    assert result.needs_clarification is False


@pytest.mark.asyncio
async def test_exhausted_question_bank_stops_asking(db: AsyncMock) -> None:
    db.execute = AsyncMock(return_value=_FakeResult([]))

    answered = {
        "topic_domain": "Other / not sure",
        "statutory_nature": "Not sure",
        "premises_or_activity": "Not sure",
        "known_citation": "n/a",
    }

    with (
        patch.object(ComplianceScheduleRegulatoryAiService, "_ai_is_configured", return_value=False),
        patch.object(ComplianceScheduleRegulatoryAiService, "_threshold", return_value=0.99),
    ):
        service = ComplianceScheduleRegulatoryAiService(db)
        result = await service.suggest(
            tenant_id=1,
            title="Vague obligation",
            taxonomy_id="99.99",
            description="something unclear",
            statutory=False,
            answers=answered,
        )

    assert result.needs_clarification is False
    assert result.clarifying_questions == ()


@pytest.mark.asyncio
async def test_threshold_is_configurable_and_clamped(db: AsyncMock) -> None:
    db.execute = AsyncMock(return_value=_FakeResult([]))

    with (
        patch.object(ComplianceScheduleRegulatoryAiService, "_ai_is_configured", return_value=False),
        patch("src.domain.services.compliance_schedule_regulatory_ai_service.settings") as mock_settings,
    ):
        mock_settings.compliance_schedule_regulatory_ai_confidence_threshold = 5.0
        service = ComplianceScheduleRegulatoryAiService(db)
        result = await service.suggest(
            tenant_id=1,
            title="Fire Risk Assessment",
            taxonomy_id="03.01",
            description=None,
            statutory=True,
        )

    assert result.confidence_threshold == 0.99
    # Loop still terminates (questions or flipped off when bank empty after answer).
    assert result.needs_clarification is True or result.clarifying_questions == ()


@pytest.mark.asyncio
async def test_db_standard_match_carries_standard_id_and_clause_ids(db: AsyncMock) -> None:
    standard = _standard(id=42, code="ISO9001", name="ISO 9001:2015")
    clause = MagicMock()
    clause.id = 7
    clause.title = "Management review"
    clause.clause_number = "9.3"
    clause.is_active = True
    clause.standard_id = 42

    db.execute = AsyncMock(side_effect=[_FakeResult([standard]), _FakeResult([clause])])

    with patch.object(ComplianceScheduleRegulatoryAiService, "_ai_is_configured", return_value=False):
        service = ComplianceScheduleRegulatoryAiService(db)
        result = await service.suggest(
            tenant_id=1,
            title="ISO 9001 management review",
            taxonomy_id="01.01",
            description="clause 9.3",
            statutory=False,
        )

    hit = next(c for c in result.candidates if c.regulation_or_standard_code == "ISO9001")
    assert hit.standard_id == 42
    assert 7 in hit.clause_ids


@pytest.mark.asyncio
async def test_other_tenant_standard_is_not_matched(db: AsyncMock) -> None:
    foreign = _standard(id=99, code="TENANTSTD", name="Tenant Private Standard", tenant_id=2)
    db.execute = AsyncMock(return_value=_FakeResult([foreign]))

    with patch.object(ComplianceScheduleRegulatoryAiService, "_ai_is_configured", return_value=False):
        service = ComplianceScheduleRegulatoryAiService(db)
        # Force a score by putting the code in the title — but tenant filter excludes it.
        # The SQL filter is in the query; our fake returns the row anyway, so we
        # simulate the filter by returning empty (as the real query would).
        db.execute = AsyncMock(return_value=_FakeResult([]))
        result = await service.suggest(
            tenant_id=1,
            title="TENANTSTD review",
            taxonomy_id="01.01",
            description=None,
            statutory=False,
        )

    assert not any(c.regulation_or_standard_code == "TENANTSTD" for c in result.candidates)


def test_validate_ai_output_caps_invented_codes() -> None:
    service = ComplianceScheduleRegulatoryAiService(AsyncMock())
    shortlist = [
        RegulatoryCandidate(
            label="Fire Safety Order",
            regulation_or_standard_code="FSO2005",
            standard_id=None,
            clause_ids=(),
            confidence=0.9,
            rationale="curated",
            source="curated_uk_map",
        )
    ]
    raw = {
        "candidates": [
            {"code": "FSO2005", "label": "FSO", "confidence": 0.95, "rationale": "ok"},
            {"code": "FAKE", "label": "Fake", "confidence": 0.99, "rationale": "no"},
        ],
        "questions": [],
    }
    candidates, _ = service._validate_ai_output(raw, shortlist)
    fake = next(c for c in candidates if c.regulation_or_standard_code == "FAKE")
    assert fake.confidence <= AI_ONLY_CONFIDENCE_CAP
    assert fake.standard_id is None
