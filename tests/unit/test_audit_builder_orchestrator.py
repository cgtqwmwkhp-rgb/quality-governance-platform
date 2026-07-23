"""Unit tests for Audit Builder orchestrator + Perplexity research fail-closed."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.domain.services.audit_builder_orchestrator import AuditBuilderOrchestrator, _overlap_score
from src.domain.services.library_horizon_adapter import (
    NoopLiveHorizonProvider,
    PerplexityLiveHorizonProvider,
    get_horizon_provider,
    research_with_perplexity,
)


def test_overlap_score_prefers_shared_tokens():
    assert _overlap_score("winch trailer inspection", "trailer winch LOLER check") > 0.2
    assert _overlap_score("aaa", "zzz") < 0.2


def test_compose_generation_prompt_includes_research_and_qa():
    orch = AuditBuilderOrchestrator(MagicMock())
    brief = {
        "purpose": "risk_audit",
        "asset_hint": "Williams Trailer",
        "standards": ["ISO 45001", "HSE"],
        "themes": ["Recent near miss: winch cable"],
        "proposed_sections": [{"title": "Critical controls"}],
        "upload_summaries": ["Job sheet: annual service"],
        "research_findings": [
            {
                "title": "LOLER guidance",
                "summary": "Thorough examination intervals",
                "source_url": "https://www.hse.gov.uk/work-equipment-machinery/loler.htm",
            }
        ],
        "qa_answers": {"depth": "full audit"},
        "case_refs": [{"type": "near_miss", "id": 9}],
        "freeform_notes": "Focus on SEB winch",
    }
    prompt = orch.compose_generation_prompt(brief)
    assert "Williams Trailer" in prompt
    assert "LOLER guidance" in prompt
    assert "depth: full audit" in prompt
    assert "near_miss:9" in prompt


def test_apply_qa_answers_appends_user_themes():
    orch = AuditBuilderOrchestrator(MagicMock())
    brief = {"proposed_sections": [{"title": "Scope"}], "qa_answers": {}}
    out = orch.apply_qa_answers(brief, {"include_themes": "cable wear, guarding"})
    assert out["qa_answers"]["include_themes"] == "cable wear, guarding"
    titles = [s["title"] for s in out["proposed_sections"]]
    assert "User-requested themes" in titles


def test_get_horizon_provider_perplexity_without_key_is_noop(monkeypatch):
    monkeypatch.setattr(
        "src.domain.services.library_horizon_adapter.settings",
        MagicMock(library_horizon_provider="perplexity", perplexity_api_key=""),
    )
    provider = get_horizon_provider("perplexity")
    assert isinstance(provider, NoopLiveHorizonProvider)
    assert provider.scan(document_id=1, document_title="x", tenant_id=1) == []


def test_research_with_perplexity_fail_closed_no_key(monkeypatch):
    monkeypatch.setattr(
        "src.domain.services.library_horizon_adapter.settings",
        MagicMock(perplexity_api_key=""),
    )
    assert research_with_perplexity("winch trailer") == []


def test_perplexity_provider_parses_json_array(monkeypatch):
    payload = {
        "choices": [
            {
                "message": {
                    "content": '[{"title":"HSE LOLER","summary":"Examine lifting gear","source_url":"https://www.hse.gov.uk/loler"}]'
                }
            }
        ]
    }

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return _Resp()

    monkeypatch.setattr("src.domain.services.library_horizon_adapter.httpx.Client", _Client)
    findings = PerplexityLiveHorizonProvider("test-key").research("LOLER winch")
    assert len(findings) == 1
    assert findings[0].title == "HSE LOLER"
    assert findings[0].source_url and findings[0].source_url.startswith("https://")


@pytest.mark.asyncio
async def test_gather_brief_fail_closed_empty_db():
    db = MagicMock()

    async def _execute(_stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        return result

    db.execute = _execute
    orch = AuditBuilderOrchestrator(db)
    brief = await orch.gather_brief(
        tenant_id=1,
        purpose="risk_audit",
        scopes=["incidents", "near_misses"],
        case_refs=[],
        asset_hint="trailer",
        standards=["ISO 45001"],
        freeform_notes="test",
        upload_summaries=["upload summary"],
    )
    assert brief["brief_id"]
    assert brief["purpose"] == "risk_audit"
    assert "open_questions" in brief
    assert brief["upload_summaries"] == ["upload summary"]
