"""Best-in-class Audit Builder generation pipeline.

Perplexity research is already attached on the brief. This pipeline:
1. Gemini emits schema-shaped template JSON (structured output)
2. Claude quality-pass rewrites weak questions / guidance (fail-soft)
3. Returns sections + honesty metadata for UI / telemetry
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from src.domain.services.gemini_ai_service import GeminiAIService

logger = logging.getLogger(__name__)

QUESTION_TYPES = (
    "yes_no",
    "yes_no_na",
    "pass_fail",
    "text_short",
    "text_long",
    "numeric",
    "date",
    "scale_1_5",
    "scale_1_10",
    "signature",
    "multi_choice",
    "checklist",
)
RISK_LEVELS = ("critical", "high", "medium", "low", "observation")


def normalize_sections(raw: Any) -> list[dict[str, Any]]:
    """Coerce Gemini/Claude payloads into the FE section list shape."""
    if isinstance(raw, dict):
        sections = raw.get("sections")
        if sections is None and isinstance(raw.get("data"), list):
            sections = raw["data"]
        if not isinstance(sections, list):
            return []
    elif isinstance(raw, list):
        sections = raw
    else:
        return []

    out: list[dict[str, Any]] = []
    for i, sec in enumerate(sections):
        if not isinstance(sec, dict):
            continue
        questions_in = sec.get("questions") or []
        questions: list[dict[str, Any]] = []
        if isinstance(questions_in, list):
            for j, q in enumerate(questions_in):
                if not isinstance(q, dict):
                    continue
                text = str(q.get("text") or "").strip()
                if not text:
                    continue
                qtype = str(q.get("type") or "yes_no").strip()
                if qtype not in QUESTION_TYPES:
                    qtype = "yes_no"
                risk = str(q.get("riskLevel") or q.get("risk_level") or "medium").strip().lower()
                if risk not in RISK_LEVELS:
                    risk = "medium"
                questions.append(
                    {
                        "id": str(q.get("id") or f"question-{i + 1}-{j + 1}"),
                        "text": text[:2000],
                        "type": qtype,
                        "required": bool(q.get("required", True)),
                        "weight": float(q.get("weight") or 1),
                        "riskLevel": risk,
                        "evidenceRequired": bool(q.get("evidenceRequired") or q.get("evidence_required") or False),
                        "isoClause": (str(q.get("isoClause") or q.get("iso_clause") or "").strip() or None),
                        "guidance": (str(q.get("guidance") or "").strip() or None),
                    }
                )
        title = str(sec.get("title") or sec.get("name") or f"Section {i + 1}").strip()
        if not title or not questions:
            continue
        out.append(
            {
                "id": str(sec.get("id") or f"section-{i + 1}"),
                "title": title[:300],
                "description": str(sec.get("description") or "")[:1000],
                "questions": questions,
            }
        )
    return out


class AuditBuilderGenerationPipeline:
    """Gemini structured generate + Claude quality pass."""

    def __init__(self, gemini: Optional[GeminiAIService] = None) -> None:
        self.gemini = gemini or GeminiAIService()

    async def generate(self, *, prompt: str, brief: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        models_used: dict[str, Any] = {
            "research": "perplexity" if (brief or {}).get("research_findings") else None,
            "generate": None,
            "quality_pass": None,
        }
        if not self.gemini.is_configured():
            raise RuntimeError("GEMINI_UNAVAILABLE")

        sections = await self.gemini.prompt_to_template(prompt)
        sections = normalize_sections(sections)
        if not sections:
            raise RuntimeError("EMPTY_TEMPLATE")
        models_used["generate"] = os.environ.get("GEMINI_MODEL", "gemini-3.1-pro-preview")

        quality_available = False
        quality_notes: Optional[str] = None
        improved, quality_available, quality_model, quality_notes = await self._claude_quality_pass(
            sections=sections,
            brief=brief or {},
            prompt_excerpt=prompt[:2500],
        )
        if quality_available and improved:
            sections = improved
            models_used["quality_pass"] = quality_model

        return {
            "sections": sections,
            "models_used": models_used,
            "quality_pass_available": quality_available,
            "quality_pass_notes": quality_notes,
        }

    async def _claude_quality_pass(
        self,
        *,
        sections: list[dict[str, Any]],
        brief: dict[str, Any],
        prompt_excerpt: str,
    ) -> tuple[Optional[list[dict[str, Any]]], bool, Optional[str], Optional[str]]:
        api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        if not api_key:
            return None, False, None, "anthropic_key_missing"
        try:
            from src.domain.services.ai_models import AIConfig, AnthropicClient

            client = AnthropicClient(AIConfig.from_env())
            purpose = brief.get("purpose") or "freeform"
            standards = ", ".join(brief.get("standards") or []) or "good practice"
            # Keep token budget bounded for large templates — only send a prefix,
            # then merge so unsliced sections are never dropped on success.
            sections_in = sections
            truncated = False
            payload = json.dumps({"sections": sections_in}, ensure_ascii=False)
            if len(payload) > 60000:
                sections_in = sections[:6]
                truncated = True
                payload = json.dumps({"sections": sections_in}, ensure_ascii=False)

            system = (
                "You are a world-class health, safety and compliance audit designer. "
                "Improve assessment questions for field assessors: clearer wording, "
                "stronger risk focus, practical evidence guidance, accurate ISO/scheme "
                "clause hints when known. Do not invent case references. "
                'Return ONLY valid JSON with shape {"sections":[...]} matching the input schema.'
            )
            prefix_note = (
                "\nNote: This is a PREFIX of a larger template. Improve only these sections; "
                "do not invent replacements for omitted later sections.\n"
                if truncated
                else ""
            )
            user = f"""Improve this generated audit/assessment template.
{prefix_note}
Purpose: {purpose}
Standards: {standards}
Brief excerpt:
{prompt_excerpt}

Template JSON:
{payload}

Rules:
- Keep the same overall section count unless a section is empty/useless (then drop it).
- Preserve question ids where possible; add new ids only for new questions.
- Prefer executable question types: yes_no, yes_no_na, pass_fail, scale_1_5, text_short, text_long, checklist.
- Strengthen guidance with assessor 'what good looks like' notes.
- Return JSON only: {{"sections":[...]}}
"""
            text = await client.complete(
                user,
                system_prompt=system,
                temperature=0.2,
                max_tokens=8000,
                timeout=120.0,
            )
            text = (text or "").strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                if text.lower().startswith("json"):
                    text = text[4:].strip()
            parsed = json.loads(text)
            improved = normalize_sections(parsed)
            if not improved:
                return None, False, None, "quality_pass_empty"
            if truncated:
                # Cap Claude's prefix (ignore extras) then preserve unsliced Gemini tail.
                improved = improved[: len(sections_in)] + sections[len(sections_in) :]
            model = getattr(client, "model", None) or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
            return improved, True, model, None
        except Exception as exc:  # noqa: BLE001 — fail-soft
            logger.info("Claude quality pass unavailable: %s", type(exc).__name__)
            return None, False, None, type(exc).__name__
