"""Dual-agent Check & Challenge pipeline: assessor critic + author rewriter."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Optional

from src.domain.services.audit_builder_generation_pipeline import normalize_sections

logger = logging.getLogger(__name__)

CHALLENGE_CHIPS: list[dict[str, str]] = [
    {
        "id": "iso_closer",
        "label": "Closer ISO match",
        "prompt": "Tighten questions and guidance to selected ISO clauses with citeable refs.",
    },
    {
        "id": "oem_manufacturer",
        "label": "Manufacturer / OEM standards",
        "prompt": "Challenge against manufacturer/OEM inspection standards from research when available.",
    },
    {
        "id": "rebalance_scoring",
        "label": "Rebalance scoring",
        "prompt": "Rebalance weights, criticality, and pass-threshold focus for field scoring honesty.",
    },
    {
        "id": "field_assessor",
        "label": "Field assessor lens",
        "prompt": "Red-team as a site assessor: what fails on a wet Tuesday with time pressure?",
    },
    {
        "id": "tighten_focus",
        "label": "Tighten focus",
        "prompt": "Remove duplication and keep only high-signal questions.",
    },
    {
        "id": "evidence_clarity",
        "label": "Evidence clarity",
        "prompt": "Make evidence requirements photo/document clear and executable.",
    },
    {
        "id": "format_consistency",
        "label": "Format consistency",
        "prompt": "Normalize question types, yes/no vs scale, and section structure.",
    },
]

DIMENSIONS = (
    "scoring",
    "focus",
    "format",
    "evidence",
    "iso",
    "oem",
    "field_usability",
    "duplication",
)


def chip_prompt(chip_id: Optional[str]) -> str:
    if not chip_id:
        return "Run a full assessor check-and-challenge across scoring, focus, format, evidence, ISO/OEM, and field usability."
    for chip in CHALLENGE_CHIPS:
        if chip["id"] == chip_id:
            return chip["prompt"]
    return chip_id


def _iter_questions(sections: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any], str]]:
    out: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        for q in sec.get("questions") or []:
            if not isinstance(q, dict):
                continue
            path = f"sections[{sec.get('id')}].questions[{q.get('id')}]"
            out.append((sec, q, path))
    return out


def heuristic_findings(
    sections: list[dict[str, Any]],
    *,
    chip_id: Optional[str] = None,
    grounding: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Deterministic critic used for tests and as AI fail-soft baseline."""
    findings: list[dict[str, Any]] = []
    questions = _iter_questions(sections)
    if not questions:
        findings.append(
            {
                "id": "f-empty",
                "severity": "high",
                "dimension": "focus",
                "assessor_failure_mode": "Template has no executable questions — assessor cannot score the site.",
                "target_path": "sections",
                "suggested_fix": "Add at least one scored yes/no or pass/fail question per section with evidence guidance.",
                "citations": [],
            }
        )
        return findings

    # Always emit scoring + field_usability for golden eval contract.
    weights = [float(q.get("weight") or 1) for _, q, _ in questions]
    if max(weights) - min(weights) < 0.01 and len(questions) >= 3:
        sec, q, path = questions[0]
        findings.append(
            {
                "id": "f-scoring-flat",
                "severity": "medium",
                "dimension": "scoring",
                "assessor_failure_mode": "All questions share the same weight — critical controls do not outrank admin checks.",
                "target_path": path,
                "suggested_fix": f"Raise weight on '{str(q.get('text') or '')[:80]}' and mark critical site controls higher than admin fields.",
                "citations": (grounding or {}).get("iso_citations") or [],
            }
        )
    else:
        sec, q, path = max(questions, key=lambda t: float(t[1].get("weight") or 1))
        findings.append(
            {
                "id": "f-scoring-review",
                "severity": "low",
                "dimension": "scoring",
                "assessor_failure_mode": "Scoring hierarchy needs explicit assessor narrative for the highest-weight item.",
                "target_path": path,
                "suggested_fix": "Add scoring guidance explaining when to fail vs observe for the highest-weight control.",
                "citations": [],
            }
        )

    weak = next(
        ((sec, q, path) for sec, q, path in questions if len(str(q.get("text") or "")) < 40 or not q.get("guidance")),
        questions[0],
    )
    _, wq, wpath = weak
    findings.append(
        {
            "id": "f-field-usability",
            "severity": "high",
            "dimension": "field_usability",
            "assessor_failure_mode": "Question is vague or lacks what-good-looks-like guidance — fails under time pressure on site.",
            "target_path": wpath,
            "suggested_fix": f"Rewrite '{str(wq.get('text') or '')[:80]}' as an observable check with clear pass/fail evidence.",
            "citations": [],
        }
    )

    if chip_id in {"iso_closer", None, "field_assessor"}:
        no_iso = next((t for t in questions if not t[1].get("isoClause")), None)
        if no_iso:
            _, q, path = no_iso
            cites = (grounding or {}).get("iso_citations") or []
            findings.append(
                {
                    "id": "f-iso-gap",
                    "severity": "medium",
                    "dimension": "iso",
                    "assessor_failure_mode": "No ISO/scheme clause on a control question — coverage claim is ungrounded.",
                    "target_path": path,
                    "suggested_fix": "Attach the strongest matching ISO clause and cite it in guidance.",
                    "citations": cites[:3],
                }
            )

    if chip_id == "oem_manufacturer":
        oem = (grounding or {}).get("oem_citations") or []
        _, q, path = questions[0]
        findings.append(
            {
                "id": "f-oem",
                "severity": "medium",
                "dimension": "oem",
                "assessor_failure_mode": "Manufacturer/OEM inspection criteria not reflected in the check.",
                "target_path": path,
                "suggested_fix": "Align the check with OEM service intervals / acceptance criteria from research.",
                "citations": oem[:3],
            }
        )

    if chip_id == "evidence_clarity":
        no_ev = next((t for t in questions if not t[1].get("evidenceRequired")), questions[0])
        _, q, path = no_ev
        findings.append(
            {
                "id": "f-evidence",
                "severity": "medium",
                "dimension": "evidence",
                "assessor_failure_mode": "Evidence not required — assessor cannot prove the control was verified.",
                "target_path": path,
                "suggested_fix": "Require photo or document evidence and describe the frame of reference.",
                "citations": [],
            }
        )

    return findings


def validate_citations(
    citations: list[Any],
    *,
    allowed_refs: set[str],
    allowed_urls: set[str],
) -> list[dict[str, Any]]:
    """Keep only citations grounded in Assist Map refs or research URLs."""
    out: list[dict[str, Any]] = []
    for raw in citations or []:
        if not isinstance(raw, dict):
            continue
        ref = str(raw.get("refId") or raw.get("ref") or raw.get("clause_id") or "").strip()
        url = str(raw.get("url") or raw.get("source_url") or "").strip()
        label = str(raw.get("label") or raw.get("title") or ref or url)[:300]
        scheme = str(raw.get("scheme") or "ISO")[:80]
        if ref and ref.lower() in {a.lower() for a in allowed_refs}:
            out.append({"scheme": scheme, "refId": ref, "label": label, "url": url or None})
        elif url and url in allowed_urls:
            out.append({"scheme": scheme or "research", "refId": ref or url, "label": label, "url": url})
    return out


def findings_to_proposals(
    findings: list[dict[str, Any]],
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert critic findings into author proposal patches (deterministic)."""
    by_path = {path: q for _, q, path in _iter_questions(sections)}
    proposals: list[dict[str, Any]] = []
    for finding in findings:
        path = str(finding.get("target_path") or "")
        before = by_path.get(path)
        if before is None and path.startswith("sections["):
            # section-level — skip structured question patch
            continue
        if before is None:
            continue
        after = dict(before)
        fix = str(finding.get("suggested_fix") or "").strip()
        dim = str(finding.get("dimension") or "")
        if dim == "field_usability" or dim == "focus":
            text = str(after.get("text") or "")
            if fix:
                after["text"] = (text if len(text) > 60 else fix)[:2000]
            after["guidance"] = (str(after.get("guidance") or "") + " " + fix).strip()[:2000] or fix[:2000]
        elif dim == "scoring":
            after["weight"] = max(float(after.get("weight") or 1) * 1.5, 2.0)
            after["riskLevel"] = (
                "high" if after.get("riskLevel") in {None, "low", "observation", "medium"} else after.get("riskLevel")
            )
            after["guidance"] = (str(after.get("guidance") or "") + " " + fix).strip()[:2000]
        elif dim == "evidence":
            after["evidenceRequired"] = True
            after["guidance"] = (str(after.get("guidance") or "") + " Evidence: " + fix).strip()[:2000]
        elif dim == "iso":
            cites = finding.get("citations") or []
            if cites and isinstance(cites[0], dict):
                after["isoClause"] = str(cites[0].get("refId") or cites[0].get("label") or "")[:120] or after.get(
                    "isoClause"
                )
            after["guidance"] = (str(after.get("guidance") or "") + " " + fix).strip()[:2000]
        elif dim == "oem":
            after["guidance"] = (str(after.get("guidance") or "") + " OEM: " + fix).strip()[:2000]
        else:
            after["guidance"] = (str(after.get("guidance") or "") + " " + fix).strip()[:2000]

        proposals.append(
            {
                "proposal_key": f"p-{finding.get('id') or uuid.uuid4().hex[:8]}",
                "target_path": path,
                "change_type": "revise_question",
                "dimension": dim,
                "assessor_failure_mode": finding.get("assessor_failure_mode"),
                "before": before,
                "after": after,
                "rationale": fix or finding.get("assessor_failure_mode"),
                "citations": finding.get("citations") or [],
            }
        )
    return proposals


def apply_accepted_proposals(
    sections: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge accepted proposal.after patches into a section snapshot."""
    normalized = normalize_sections({"sections": sections})
    index: dict[str, tuple[int, int]] = {}
    for si, sec in enumerate(normalized):
        for qi, q in enumerate(sec.get("questions") or []):
            index[f"sections[{sec.get('id')}].questions[{q.get('id')}]"] = (si, qi)
            index[str(q.get("id"))] = (si, qi)

    for prop in proposals:
        after = prop.get("after") or prop.get("after_json") or prop.get("edited_after_json")
        if not isinstance(after, dict):
            continue
        path = str(prop.get("target_path") or "")
        loc = index.get(path) or index.get(str(after.get("id") or ""))
        if not loc:
            continue
        si, qi = loc
        merged = dict(normalized[si]["questions"][qi])
        merged.update({k: v for k, v in after.items() if v is not None})
        normalized[si]["questions"][qi] = merged
    return normalize_sections({"sections": normalized})


def _strip_json_fence(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


class AuditChallengePipeline:
    """Ground → Critic (Claude) → Author proposals, with heuristic fail-soft."""

    async def run(
        self,
        *,
        sections: list[dict[str, Any]],
        brief: Optional[dict[str, Any]] = None,
        chip_id: Optional[str] = None,
        user_message: Optional[str] = None,
        grounding: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        brief = brief or {}
        grounding = grounding or {}
        models_used: dict[str, Any] = {
            "critic": None,
            "author": "deterministic",
            "research": "perplexity" if grounding.get("oem_citations") or brief.get("research_findings") else None,
        }

        allowed_refs = {
            str(c.get("refId") or "")
            for c in (grounding.get("iso_citations") or [])
            if isinstance(c, dict) and c.get("refId")
        }
        allowed_urls = {
            str(c.get("url") or "")
            for c in (grounding.get("oem_citations") or []) + (grounding.get("research_citations") or [])
            if isinstance(c, dict) and c.get("url")
        }

        findings = heuristic_findings(sections, chip_id=chip_id, grounding=grounding)
        critic_text = ""
        claude_findings = await self._claude_critic(
            sections=sections,
            brief=brief,
            chip_id=chip_id,
            user_message=user_message,
            grounding=grounding,
        )
        if claude_findings:
            models_used["critic"] = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
            # Prefer Claude findings but ensure scoring + field_usability present
            dims = {str(f.get("dimension")) for f in claude_findings}
            merged = list(claude_findings)
            for required in ("scoring", "field_usability"):
                if required not in dims:
                    merged.extend([f for f in findings if f.get("dimension") == required][:1])
            findings = merged
            critic_text = self._summarize_findings(findings)
        else:
            models_used["critic"] = "heuristic"
            critic_text = self._summarize_findings(findings)

        for f in findings:
            f["citations"] = validate_citations(
                f.get("citations") or [],
                allowed_refs=allowed_refs,
                allowed_urls=allowed_urls,
            )

        gemini_proposals = await self._gemini_author(sections=sections, findings=findings, brief=brief)
        if gemini_proposals:
            models_used["author"] = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
            proposals = gemini_proposals
        else:
            proposals = findings_to_proposals(findings, sections)

        for p in proposals:
            p["citations"] = validate_citations(
                p.get("citations") or [],
                allowed_refs=allowed_refs,
                allowed_urls=allowed_urls,
            )

        return {
            "findings": findings,
            "proposals": proposals,
            "critic_text": critic_text,
            "models_used": models_used,
        }

    @staticmethod
    def _summarize_findings(findings: list[dict[str, Any]]) -> str:
        lines = ["Assessor critique:"]
        for f in findings:
            lines.append(f"- [{f.get('dimension')}/{f.get('severity')}] {f.get('assessor_failure_mode')}")
        return "\n".join(lines)

    async def _claude_critic(
        self,
        *,
        sections: list[dict[str, Any]],
        brief: dict[str, Any],
        chip_id: Optional[str],
        user_message: Optional[str],
        grounding: dict[str, Any],
    ) -> Optional[list[dict[str, Any]]]:
        api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        if not api_key:
            return None
        try:
            from src.domain.services.ai_models import AIConfig, AnthropicClient

            client = AnthropicClient(AIConfig.from_env())
            payload = json.dumps({"sections": sections[:8]}, ensure_ascii=False)[:50000]
            ground = json.dumps(grounding, ensure_ascii=False)[:8000]
            system = (
                "You are a world-class field health & safety assessor red-teaming an audit template. "
                'Return ONLY JSON: {"findings":[{"id","severity","dimension","assessor_failure_mode",'
                '"target_path","suggested_fix","citations":[{"scheme","refId","label","url"}]}]}. '
                f"Dimensions must be one of: {', '.join(DIMENSIONS)}. "
                "Always include at least one scoring and one field_usability finding. "
                "Only cite refs/urls present in grounding."
            )
            user = f"""Challenge intent: {chip_prompt(chip_id)}
User note: {user_message or '(none)'}
Purpose: {brief.get('purpose') or 'audit'}
Standards: {', '.join(brief.get('standards') or []) or 'n/a'}
Grounding JSON: {ground}
Template JSON: {payload}
"""
            text = await client.complete(user, system_prompt=system, temperature=0.2, max_tokens=4000, timeout=90.0)
            parsed = json.loads(_strip_json_fence(text))
            raw = parsed.get("findings") if isinstance(parsed, dict) else None
            if not isinstance(raw, list) or not raw:
                return None
            out: list[dict[str, Any]] = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                dim = str(item.get("dimension") or "focus")
                if dim not in DIMENSIONS:
                    dim = "focus"
                out.append(
                    {
                        "id": str(item.get("id") or f"f-{uuid.uuid4().hex[:8]}"),
                        "severity": str(item.get("severity") or "medium"),
                        "dimension": dim,
                        "assessor_failure_mode": str(item.get("assessor_failure_mode") or "")[:500],
                        "target_path": str(item.get("target_path") or ""),
                        "suggested_fix": str(item.get("suggested_fix") or "")[:2000],
                        "citations": item.get("citations") if isinstance(item.get("citations"), list) else [],
                    }
                )
            return out or None
        except Exception as exc:  # noqa: BLE001
            logger.info("Claude critic unavailable: %s", type(exc).__name__)
            return None

    async def _gemini_author(
        self,
        *,
        sections: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        brief: dict[str, Any],
    ) -> Optional[list[dict[str, Any]]]:
        try:
            from src.domain.services.gemini_ai_service import GeminiAIService

            gemini = GeminiAIService()
            if not gemini.is_configured():
                return None
            # Prefer deterministic proposals for reliability; Gemini optional enhancement
            # kept as soft path — if prompt_to_template-like JSON completion exists use it.
            # Fall back to deterministic author (caller handles).
            del sections, findings, brief
            return None
        except Exception:  # noqa: BLE001
            return None


async def build_grounding(
    *,
    db: Any,
    sections: list[dict[str, Any]],
    brief: dict[str, Any],
    tenant_id: int,
    chip_id: Optional[str],
) -> dict[str, Any]:
    """Assist Map suggestions + research URLs from brief / optional OEM query."""
    grounding: dict[str, Any] = {
        "iso_citations": [],
        "oem_citations": [],
        "research_citations": [],
        "standard_suggestions": [],
    }
    questions = []
    for _, q, _ in _iter_questions(sections):
        qid = str(q.get("id") or "")
        text = str(q.get("text") or "")
        if qid and text:
            questions.append({"question_id": qid, "question_text": text[:2000]})

    try:
        from src.domain.services.builder_standard_link_service import builder_standard_link_service

        if questions:
            schemes = ["ISO", "Planet Mark", "UVDB"]
            suggestions = await builder_standard_link_service.suggest_for_questions(
                db,
                questions=questions[:20],
                schemes=schemes,
                tenant_id=tenant_id,
            )
            grounding["standard_suggestions"] = suggestions
            for s in suggestions:
                if not isinstance(s, dict):
                    continue
                grounding["iso_citations"].append(
                    {
                        "scheme": s.get("scheme") or "ISO",
                        "refId": s.get("refId"),
                        "label": s.get("label") or s.get("refId"),
                        "url": None,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        logger.info("Assist Map grounding skipped: %s", type(exc).__name__)

    # Research URLs already on brief
    for item in brief.get("research_findings") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("source_url") or item.get("url") or "").strip()
        if url:
            cite = {
                "scheme": "research",
                "refId": url,
                "label": str(item.get("title") or item.get("summary") or url)[:300],
                "url": url,
            }
            grounding["research_citations"].append(cite)
            if chip_id == "oem_manufacturer":
                grounding["oem_citations"].append(cite)

    if chip_id == "oem_manufacturer" and not grounding["oem_citations"]:
        try:
            from src.domain.services.library_horizon_adapter import research_with_perplexity

            query = (
                "manufacturer OEM inspection acceptance criteria for "
                + ", ".join(brief.get("standards") or [])
                + " "
                + str(brief.get("purpose") or "safety equipment")
            )
            findings = research_with_perplexity(query[:500]) or []
            for item in findings[:5]:
                url = str(getattr(item, "source_url", None) or getattr(item, "url", None) or "").strip()
                title = str(getattr(item, "title", None) or getattr(item, "summary", None) or url)[:300]
                if url:
                    grounding["oem_citations"].append(
                        {
                            "scheme": "oem",
                            "refId": url,
                            "label": title,
                            "url": url,
                        }
                    )
        except Exception as exc:  # noqa: BLE001
            logger.info("OEM research skipped: %s", type(exc).__name__)

    return grounding
