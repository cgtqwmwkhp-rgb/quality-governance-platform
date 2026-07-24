"""Unit tests for Audit Builder best-in-class generation pipeline."""

from __future__ import annotations

import json

import pytest

from src.domain.services.audit_builder_generation_pipeline import AuditBuilderGenerationPipeline, normalize_sections


def test_normalize_sections_from_object_wrapper():
    raw = {
        "sections": [
            {
                "id": "section-1",
                "title": "PPE",
                "description": "PPE checks",
                "questions": [
                    {
                        "id": "q1",
                        "text": "Is PPE worn?",
                        "type": "yes_no",
                        "required": True,
                        "weight": 1,
                        "riskLevel": "high",
                        "guidance": "Observe on approach",
                    }
                ],
            }
        ]
    }
    sections = normalize_sections(raw)
    assert len(sections) == 1
    assert sections[0]["title"] == "PPE"
    assert sections[0]["questions"][0]["type"] == "yes_no"


def test_normalize_sections_coerces_bad_types_and_drops_empty():
    raw = [
        {
            "title": "Empty",
            "questions": [{"text": "", "type": "yes_no"}],
        },
        {
            "title": "Valid",
            "questions": [{"text": "Check extinguisher", "type": "not_a_type", "riskLevel": "HOT"}],
        },
    ]
    sections = normalize_sections(raw)
    assert len(sections) == 1
    q = sections[0]["questions"][0]
    assert q["type"] == "yes_no"
    assert q["riskLevel"] == "medium"


@pytest.mark.asyncio
async def test_pipeline_uses_gemini_then_claude(monkeypatch):
    monkeypatch.setenv("AUDIT_BUILDER_SYNC_QUALITY_PASS", "1")

    class FakeGemini:
        def is_configured(self):
            return True

        async def prompt_to_template(self, prompt: str):
            assert "BRIEF" in prompt or "audit" in prompt.lower() or len(prompt) > 0
            return [
                {
                    "id": "section-1",
                    "title": "Draft",
                    "description": "",
                    "questions": [
                        {
                            "id": "q1",
                            "text": "Weak question",
                            "type": "yes_no",
                            "required": True,
                            "weight": 1,
                            "riskLevel": "medium",
                        }
                    ],
                }
            ]

    async def fake_quality(self, *, sections, brief, prompt_excerpt):
        improved = normalize_sections(
            {
                "sections": [
                    {
                        "id": "section-1",
                        "title": "Improved",
                        "description": "Better",
                        "questions": [
                            {
                                "id": "q1",
                                "text": "Is the control measure effective and evidenced?",
                                "type": "yes_no",
                                "required": True,
                                "weight": 2,
                                "riskLevel": "high",
                                "guidance": "Ask for photo evidence",
                            }
                        ],
                    }
                ]
            }
        )
        return improved, True, "claude-sonnet-4-5", None

    monkeypatch.setattr(AuditBuilderGenerationPipeline, "_claude_quality_pass", fake_quality)
    pipe = AuditBuilderGenerationPipeline(gemini=FakeGemini())
    result = await pipe.generate(prompt="Build a site safety assessment", brief={"purpose": "risk_audit"})
    assert result["quality_pass_available"] is True
    assert result["sections"][0]["title"] == "Improved"
    assert result["models_used"]["quality_pass"] == "claude-sonnet-4-5"
    assert result["models_used"]["generate"]


@pytest.mark.asyncio
async def test_pipeline_skips_claude_by_default_for_sync_budget(monkeypatch):
    monkeypatch.delenv("AUDIT_BUILDER_SYNC_QUALITY_PASS", raising=False)

    class FakeGemini:
        def is_configured(self):
            return True

        async def prompt_to_template(self, prompt: str):
            return [
                {
                    "id": "section-1",
                    "title": "Draft",
                    "questions": [
                        {
                            "id": "q1",
                            "text": "Question",
                            "type": "yes_no",
                            "required": True,
                            "weight": 1,
                            "riskLevel": "low",
                        }
                    ],
                }
            ]

    async def fake_quality(self, *, sections, brief, prompt_excerpt):
        raise AssertionError("quality pass must not run when sync budget skip is default")

    monkeypatch.setattr(AuditBuilderGenerationPipeline, "_claude_quality_pass", fake_quality)
    pipe = AuditBuilderGenerationPipeline(gemini=FakeGemini())
    result = await pipe.generate(prompt="x", brief={})
    assert result["quality_pass_available"] is False
    assert result["quality_pass_notes"] == "quality_pass_skipped_sync_budget"
    assert result["sections"][0]["title"] == "Draft"


@pytest.mark.asyncio
async def test_quality_pass_truncation_preserves_unsliced_sections(monkeypatch):
    """When payload is capped to first 6 sections, success must not drop the rest."""

    def _sec(n: int) -> dict:
        return {
            "id": f"section-{n}",
            "title": f"Section {n}",
            "description": "",
            "questions": [
                {
                    "id": f"q{n}",
                    "text": f"Question {n} " + ("x" * 8000),
                    "type": "yes_no",
                    "required": True,
                    "weight": 1,
                    "riskLevel": "medium",
                }
            ],
        }

    large_sections = [_sec(i) for i in range(1, 10)]
    assert len(json.dumps({"sections": large_sections})) > 60000

    class FakeClient:
        model = "claude-sonnet-4-5"

        async def complete(self, *args, **kwargs):
            # Deliberately return more sections than were sent — merge must cap.
            return json.dumps(
                {
                    "sections": [
                        {
                            "id": f"section-{i}",
                            "title": f"Improved {i}",
                            "description": "",
                            "questions": [
                                {
                                    "id": f"q{i}",
                                    "text": f"Improved question {i}",
                                    "type": "yes_no",
                                    "required": True,
                                    "weight": 1,
                                    "riskLevel": "high",
                                    "guidance": "looks good",
                                }
                            ],
                        }
                        for i in range(1, 9)
                    ]
                }
            )

    class FakeAIConfig:
        @staticmethod
        def from_env():
            return object()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    import src.domain.services.ai_models as ai_models

    monkeypatch.setattr(ai_models, "AIConfig", FakeAIConfig)
    monkeypatch.setattr(ai_models, "AnthropicClient", lambda cfg: FakeClient())

    pipe = AuditBuilderGenerationPipeline.__new__(AuditBuilderGenerationPipeline)
    improved, ok, model, notes = await pipe._claude_quality_pass(
        sections=large_sections,
        brief={"purpose": "risk_audit", "standards": ["ISO 45001"]},
        prompt_excerpt="brief",
    )
    assert ok is True
    assert notes is None
    assert model == "claude-sonnet-4-5"
    assert len(improved) == 9
    assert improved[0]["title"] == "Improved 1"
    assert improved[5]["title"] == "Improved 6"
    assert improved[6]["title"] == "Section 7"
    assert improved[8]["id"] == "section-9"


@pytest.mark.asyncio
async def test_pipeline_fail_soft_without_claude(monkeypatch):
    monkeypatch.setenv("AUDIT_BUILDER_SYNC_QUALITY_PASS", "1")

    class FakeGemini:
        def is_configured(self):
            return True

        async def prompt_to_template(self, prompt: str):
            return [
                {
                    "id": "section-1",
                    "title": "Draft",
                    "questions": [
                        {
                            "id": "q1",
                            "text": "Question",
                            "type": "yes_no",
                            "required": True,
                            "weight": 1,
                            "riskLevel": "low",
                        }
                    ],
                }
            ]

    async def fake_quality(self, *, sections, brief, prompt_excerpt):
        return None, False, None, "anthropic_key_missing"

    monkeypatch.setattr(AuditBuilderGenerationPipeline, "_claude_quality_pass", fake_quality)
    pipe = AuditBuilderGenerationPipeline(gemini=FakeGemini())
    result = await pipe.generate(prompt="x", brief={})
    assert result["quality_pass_available"] is False
    assert result["sections"][0]["title"] == "Draft"
    assert result["models_used"]["quality_pass"] is None
