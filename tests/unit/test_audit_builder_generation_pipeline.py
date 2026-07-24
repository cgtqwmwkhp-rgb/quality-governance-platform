"""Unit tests for Audit Builder best-in-class generation pipeline."""

from __future__ import annotations

import pytest

from src.domain.services.audit_builder_generation_pipeline import (
    AuditBuilderGenerationPipeline,
    normalize_sections,
)


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
async def test_pipeline_fail_soft_without_claude(monkeypatch):
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
