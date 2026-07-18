"""Unit tests for MAP-01..04 builder standard-link suggest + confirm persist."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.builder_standard_link_service import (
    BuilderStandardLinkService,
    compute_coverage_from_questions,
    normalize_scheme,
    read_standard_links,
    write_standard_links,
)
from src.domain.services.governed_knowledge_service import SchemeMapping


def test_normalize_scheme_aliases() -> None:
    assert normalize_scheme("iso9001") == "ISO"
    assert normalize_scheme("planet_mark") == "Planet Mark"
    assert normalize_scheme("UVDB") == "UVDB"


def test_write_and_read_standard_links_roundtrip() -> None:
    question = SimpleNamespace(
        assessor_guidance_json=None,
        regulatory_reference=None,
        guidance_notes=None,
    )
    write_standard_links(
        question,  # type: ignore[arg-type]
        [
            {
                "id": "l1",
                "scheme": "ISO",
                "refId": "45001-8.2",
                "label": "Emergency preparedness",
                "status": "accepted",
            }
        ],
    )
    links = read_standard_links(question)  # type: ignore[arg-type]
    assert len(links) == 1
    assert links[0]["refId"] == "45001-8.2"
    assert question.regulatory_reference == "45001-8.2"
    assert "map_standard_links" in question.assessor_guidance_json


def test_compute_coverage_from_questions() -> None:
    q1 = SimpleNamespace(
        assessor_guidance_json={
            "map_standard_links": [
                {"status": "accepted", "scheme": "ISO"},
                {"status": "accepted", "scheme": "UVDB"},
            ]
        }
    )
    q2 = SimpleNamespace(assessor_guidance_json={"map_standard_links": [{"status": "suggested"}]})
    q3 = SimpleNamespace(assessor_guidance_json=None)
    coverage = compute_coverage_from_questions([q1, q2, q3])  # type: ignore[list-item]
    assert coverage["total_questions"] == 3
    assert coverage["questions_with_accepted_links"] == 1
    assert coverage["accepted_multi_scheme_links"] == 2
    assert coverage["coverage_percent"] == 33
    assert coverage["assist_map_live"] is True
    assert coverage["by_scheme"]["ISO"] == 1
    assert coverage["by_scheme"]["UVDB"] == 1


@pytest.mark.asyncio
async def test_suggest_for_questions_ranks_and_caps() -> None:
    knowledge = MagicMock()
    knowledge._map_iso_schemes = AsyncMock(
        return_value=[
            SchemeMapping(
                clause_id="9001-7.2",
                scheme="iso9001",
                confidence=88.0,
                rationale="competence",
                title="Competence",
            )
        ]
    )
    knowledge._map_uvdb_schemes = AsyncMock(return_value=[])
    knowledge._map_planet_mark_schemes = MagicMock(
        return_value=[
            SchemeMapping(
                clause_id="pm:scope1",
                scheme="planet_mark",
                confidence=70.0,
                rationale="fleet fuel",
                title="Planet Mark Scope 1",
            )
        ]
    )
    svc = BuilderStandardLinkService(knowledge=knowledge)
    suggestions = await svc.suggest_for_questions(
        MagicMock(),
        questions=[
            {
                "question_id": "q-1",
                "question_text": "Are competence records retained for fleet fuel handlers?",
            }
        ],
        schemes=["ISO", "Planet Mark"],
        tenant_id=1,
    )
    assert len(suggestions) == 2
    assert {s["scheme"] for s in suggestions} == {"ISO", "Planet Mark"}
    assert all(s["status"] == "suggested" for s in suggestions)
    assert suggestions[0]["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_decide_link_accept_persists_and_mirrors_evidence() -> None:
    question = SimpleNamespace(
        id=42,
        template_id=7,
        assessor_guidance_json=None,
        regulatory_reference=None,
        guidance_notes=None,
    )
    template = SimpleNamespace(id=7, tenant_id=1)
    db = AsyncMock()
    db.scalar = AsyncMock(side_effect=[question, template, None])
    db.add = MagicMock()
    db.flush = AsyncMock()

    svc = BuilderStandardLinkService()
    result = await svc.decide_link(
        db,
        question_id=42,
        tenant_id=1,
        user=SimpleNamespace(id=9, email="a@example.com"),
        decision="accept",
        link={
            "id": "sug_1",
            "scheme": "ISO",
            "refId": "45001-8.2",
            "label": "Emergency",
            "confidence": 0.91,
        },
    )
    assert result["link"]["status"] == "accepted"
    assert result["link"]["refId"] == "45001-8.2"
    assert len(result["links"]) == 1
    assert question.regulatory_reference == "45001-8.2"
    assert db.add.call_count >= 2  # evidence + decision log
