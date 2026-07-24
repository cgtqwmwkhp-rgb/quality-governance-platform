"""Unit tests for the Audit Builder Check & Challenge critic/author pipeline.

Pure logic + heuristic fail-soft path (no Claude/Gemini/DB) so these run fast
and deterministically in CI regardless of AI credentials.
"""

from __future__ import annotations

import pytest

from src.domain.services.audit_challenge_pipeline import (
    CHALLENGE_CHIPS,
    AuditChallengePipeline,
    apply_accepted_proposals,
    chip_prompt,
    findings_to_proposals,
    heuristic_findings,
    validate_citations,
)


def _section(qid: str = "q1", **overrides) -> dict:
    question = {
        "id": qid,
        "text": "Check it",
        "type": "yes_no",
        "required": True,
        "weight": 1,
        "evidenceRequired": False,
        "guidance": None,
        "isoClause": None,
    }
    question.update(overrides)
    return {"id": "s1", "title": "Section 1", "questions": [question]}


class TestChipPrompt:
    def test_known_chip_returns_prompt(self):
        assert chip_prompt("field_assessor") != "field_assessor"
        assert "site" in chip_prompt("field_assessor").lower()

    def test_unknown_chip_falls_back_to_id(self):
        assert chip_prompt("not-a-real-chip") == "not-a-real-chip"

    def test_no_chip_returns_full_review_prompt(self):
        assert "full assessor check" in chip_prompt(None).lower()

    def test_all_chip_ids_are_unique(self):
        ids = [c["id"] for c in CHALLENGE_CHIPS]
        assert len(ids) == len(set(ids))


class TestHeuristicFindings:
    def test_empty_template_flags_no_executable_questions(self):
        findings = heuristic_findings([])
        assert len(findings) == 1
        assert findings[0]["dimension"] == "focus"
        assert findings[0]["severity"] == "high"

    def test_always_includes_scoring_and_field_usability(self):
        sections = [
            _section("q1", text="Is the guard fitted correctly and inspected today?", weight=1, guidance="Check visually"),
            _section("q2", text="Is oil level ok?", weight=1),
            _section("q3", text="Brakes?", weight=1),
        ]
        findings = heuristic_findings(sections)
        dims = {f["dimension"] for f in findings}
        assert "scoring" in dims
        assert "field_usability" in dims

    def test_flat_weights_trigger_rebalance_finding(self):
        sections = [_section("q1", weight=1), _section("q2", weight=1), _section("q3", weight=1)]
        findings = heuristic_findings(sections)
        scoring = next(f for f in findings if f["dimension"] == "scoring")
        assert scoring["id"] == "f-scoring-flat"

    def test_vague_question_flagged_field_usability(self):
        sections = [_section("q1", text="OK?", guidance=None)]
        findings = heuristic_findings(sections)
        usability = next(f for f in findings if f["dimension"] == "field_usability")
        assert usability["target_path"] == "sections[s1].questions[q1]"

    def test_oem_chip_only_emits_oem_finding_when_requested(self):
        sections = [_section()]
        no_chip = heuristic_findings(sections, chip_id=None)
        with_chip = heuristic_findings(sections, chip_id="oem_manufacturer")
        assert not any(f["dimension"] == "oem" for f in no_chip)
        assert any(f["dimension"] == "oem" for f in with_chip)

    def test_evidence_chip_flags_missing_evidence(self):
        sections = [_section(evidenceRequired=False)]
        findings = heuristic_findings(sections, chip_id="evidence_clarity")
        assert any(f["dimension"] == "evidence" for f in findings)


class TestValidateCitations:
    def test_drops_ungrounded_ref(self):
        out = validate_citations(
            [{"refId": "ISO-9001-4.2", "label": "Context"}],
            allowed_refs=set(),
            allowed_urls=set(),
        )
        assert out == []

    def test_keeps_grounded_ref_case_insensitive(self):
        out = validate_citations(
            [{"refId": "iso-9001-4.2", "label": "Context"}],
            allowed_refs={"ISO-9001-4.2"},
            allowed_urls=set(),
        )
        assert len(out) == 1
        assert out[0]["refId"] == "iso-9001-4.2"

    def test_keeps_allowed_research_url(self):
        out = validate_citations(
            [{"url": "https://oem.example.com/manual", "label": "OEM manual", "scheme": "oem"}],
            allowed_refs=set(),
            allowed_urls={"https://oem.example.com/manual"},
        )
        assert len(out) == 1
        assert out[0]["url"] == "https://oem.example.com/manual"

    def test_ignores_non_dict_entries(self):
        out = validate_citations(["not-a-dict", None], allowed_refs=set(), allowed_urls=set())
        assert out == []


class TestFindingsToProposals:
    def test_field_usability_finding_rewrites_text(self):
        sections = [_section("q1", text="OK?", guidance=None)]
        findings = [
            {
                "id": "f-field-usability",
                "dimension": "field_usability",
                "target_path": "sections[s1].questions[q1]",
                "suggested_fix": "Rewrite as an observable check with clear pass/fail evidence.",
                "assessor_failure_mode": "vague",
                "citations": [],
            }
        ]
        proposals = findings_to_proposals(findings, sections)
        assert len(proposals) == 1
        assert proposals[0]["after"]["guidance"]

    def test_scoring_finding_raises_weight(self):
        sections = [_section("q1", weight=1)]
        findings = [
            {
                "id": "f-scoring",
                "dimension": "scoring",
                "target_path": "sections[s1].questions[q1]",
                "suggested_fix": "Raise weight",
                "citations": [],
            }
        ]
        proposals = findings_to_proposals(findings, sections)
        assert proposals[0]["after"]["weight"] > 1

    def test_unresolvable_target_path_is_skipped(self):
        findings = [
            {
                "id": "f-1",
                "dimension": "focus",
                "target_path": "sections[missing].questions[missing]",
                "suggested_fix": "x",
                "citations": [],
            }
        ]
        assert findings_to_proposals(findings, [_section()]) == []


class TestApplyAcceptedProposals:
    def test_merges_after_into_matching_question(self):
        sections = [_section("q1", text="Old text")]
        proposals = [
            {
                "target_path": "sections[s1].questions[q1]",
                "after": {"id": "q1", "text": "New text"},
            }
        ]
        merged = apply_accepted_proposals(sections, proposals)
        assert merged[0]["questions"][0]["text"] == "New text"

    def test_unmatched_proposal_is_ignored(self):
        sections = [_section("q1", text="Old text")]
        proposals = [{"target_path": "sections[none].questions[none]", "after": {"text": "New text"}}]
        merged = apply_accepted_proposals(sections, proposals)
        assert merged[0]["questions"][0]["text"] == "Old text"


class TestAuditChallengePipelineHeuristicFallback:
    """When no ANTHROPIC/GEMINI keys are configured the pipeline must still
    return useful, cited-or-empty proposals (Wave A/B fail-soft requirement)."""

    @pytest.mark.asyncio
    async def test_run_returns_findings_and_proposals_without_ai_keys(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        sections = [
            _section("q1", text="Is the guard fitted correctly and inspected today?", weight=1, guidance="Check visually"),
            _section("q2", text="OK?", weight=1),
        ]
        pipeline = AuditChallengePipeline()
        result = await pipeline.run(sections=sections, brief={}, chip_id=None, grounding={})
        assert result["models_used"]["critic"] == "heuristic"
        assert result["models_used"]["author"] == "deterministic"
        assert len(result["findings"]) >= 2
        assert isinstance(result["proposals"], list)
        assert result["critic_text"].startswith("Assessor critique:")

    @pytest.mark.asyncio
    async def test_run_drops_ungrounded_citations(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        sections = [_section("q1", text="Guard question", weight=1)]
        pipeline = AuditChallengePipeline()
        result = await pipeline.run(
            sections=sections,
            brief={},
            chip_id="iso_closer",
            grounding={"iso_citations": []},
        )
        for finding in result["findings"]:
            for citation in finding.get("citations") or []:
                assert citation.get("refId") or citation.get("url")
