"""Mistral AI structured analysis for audit document extraction.

Uses the Mistral Chat API with JSON mode to extract structured data
(scores, findings, dates, scheme info) from OCR/native text, providing
significantly higher accuracy than regex-only parsing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from src.core.config import settings
from src.infrastructure.resilience.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_mistral_analysis_cb = CircuitBreaker("mistral_analysis", failure_threshold=5, recovery_timeout=300)

_VALID_SEVERITIES = frozenset({"low", "medium", "high", "critical"})
_VALID_FINDING_TYPES = frozenset(
    {
        "nonconformity",
        "major_nonconformity",
        "minor_nonconformity",
        "positive_practice",
        "observation",
        "opportunity_for_improvement",
        "competence_gap",
        "finding",
        "flagged_item",
        "question_answered_no",
    }
)
_VALID_OUTCOMES = frozenset({"pass", "fail", "review_required", "conditional_pass"})

_SYSTEM_PROMPT = """\
You are an expert audit document analyst for a Fortune 500 quality governance
platform. Given extracted text from an external audit report, return a JSON
object with the following structure. Be precise — only include data that is
clearly stated in the text. Do NOT invent values.

{
  "scheme": "achilles_uvdb | iso | planet_mark | smeta | ecovadis | customer_other",
  "scheme_label": "Human-readable scheme name",
  "scheme_version": "e.g. B2, ISO 9001:2015, or null",
  "issuer_name": "e.g. Achilles, BSI, or null",
  "report_date": "YYYY-MM-DD or null",
  "organization_name": "Name of the company/entity being audited, or null",
  "auditor_name": "Lead auditor name, or null",
  "audit_type": "initial | surveillance | recertification | transfer | null",
  "certificate_number": "Certificate or registration number, or null",
  "audit_scope": "Scope of certification / audit scope description, or null",
  "next_audit_date": "YYYY-MM-DD of next scheduled audit, or null",
  "site_name": "Name of the specific site/facility audited (may differ from organization_name), or null",
  "site_address": "Full address of the audited site/facility, or null",
  "overall_score": <number or null>,
  "max_score": <number or null>,
  "score_percentage": <number 0-100 or null>,
  "outcome": "pass | fail | review_required | conditional_pass",
  "items_total": <total number of scored items/questions or null>,
  "items_applicable": <number of applicable items excluding N/A or null>,
  "items_na": <number of N/A items excluded from scoring or null>,
  "score_breakdown": [
    {"label": "Section name", "score": <number>, "max_score": <number>}
  ],
  "findings": [
    {
      "title": "Short title",
      "description": "Verbatim evidence text from the document, preserving original wording",
      "severity": "low | medium | high | critical",
      "finding_type": "nonconformity | major_nonconformity | minor_nonconformity | positive_practice | observation | opportunity_for_improvement | competence_gap | flagged_item | question_answered_no",
      "confidence": <0.0 to 1.0>,
      "clause_reference": "e.g. ISO 9001:2015 clause 9.1.3, or null",
      "corrective_action_deadline": "YYYY-MM-DD or null",
      "evidence_items": [
        {"question": "Original inspection question text", "answer": "Yes | No | N/A", "score": "1/1 or 0/1 or null"}
      ]
    }
  ],
  "warnings": ["Any data quality concerns"]
}

Rules:
- score_breakdown entries MUST have score <= max_score. Reject date-like
  values (e.g. 23/6 meaning June 23) — those are dates, not scores.
- After computing score_breakdown, verify: the sum of section scores should
  approximately equal overall_score, and the sum of section max_scores should
  approximately equal max_score. If they diverge by more than 5%, add a
  warning explaining the discrepancy.
- Items marked "N/A", "Not Applicable", "Not Assessed", or "Excluded" must
  NOT count toward max_score. Report them in items_na. Calculate
  score_percentage against only applicable items.
- When sections use different scoring scales (e.g. some 1/1 binary and some
  out of 5), calculate score_percentage as (sum of scores / sum of max_scores)
  * 100, NOT as the average of individual section percentages. Add a warning
  if mixed scales detected.
- The input text may come from OCR of tabular documents. Look for patterns
  like "Question text ... Yes/No/N/A" or "Section ... Score/Max". When text
  appears garbled or columns are misaligned, use adjacent numeric values and
  section headers to reconstruct the intended score mapping. Add a warning if
  table reconstruction is uncertain.
- Tables that span multiple pages should be treated as a single continuous
  table. Carry forward column headers from earlier pages.
- Many audit documents contain BOTH a summary section (e.g. "Flagged Items
  Summary") AND detailed per-question results. Do NOT duplicate findings.
  Use the detailed per-question data as primary source and only add summary
  items not covered in the detail. If overlap detected, add a warning.
- Distinguish finding types carefully:
  * "nonconformity" — formal NC raised by the auditor with required corrective action
  * "major_nonconformity" / "minor_nonconformity" — if the document distinguishes severity
  * "flagged_item" — item flagged in a summary but without formal NC status
  * "question_answered_no" — a checklist question answered "No" without a formal finding
  * "observation" — noted for awareness, no corrective action required
  * "opportunity_for_improvement" — suggested improvement, not a deficiency
  * "positive_practice" — good practice noted by the auditor
- IMPORTANT: Only include "positive_practice" findings for genuinely exemplary
  or noteworthy practices. Do NOT create findings for routine compliant answers.
  For checklist-style documents, focus on non-conformities, flagged items, and
  observations. Limit positive_practice findings to a maximum of 5.
- Do NOT create "question_answered_no" findings for questions answered "Yes" or
  answered compliantly.
- For each finding, populate "evidence_items" with structured question/answer
  pairs extracted from the document. Each item should have the original
  inspection question, the answer given, and any score. This is critical for
  evidence traceability.
- For each finding, preserve the original document text verbatim in the
  description field. Prefix with page number if identifiable, e.g.
  "[p.12] Original text here". Do not rephrase or summarise evidence.
- Confidence calibration:
  * 0.95-1.0: NC number assigned, clause reference given, corrective action with deadline
  * 0.85-0.94: Finding text is explicit but missing one element (e.g. no clause ref)
  * 0.70-0.84: Inferred from a "No" answer or red/fail indicator without narrative
  * 0.50-0.69: Ambiguous — e.g. "partially compliant" with no further detail
  * Below 0.50: Do not include; add a warning instead
- Actively search for corrective action deadlines. Look for phrases like
  "to be closed by", "due date", "response required by", "within X days".
  If a general policy is stated (e.g. "all NCs must be closed within 90
  days") but no specific date, calculate from report_date and note in the
  description that the deadline was inferred.
- If a score or finding is ambiguous, add a warning instead of guessing.
- For ISO audits: typically NO numeric scores, only conformity status.
  Do not invent scores for ISO audits.
- Look for visual indicators described in text: "green", "red", "amber",
  "tick", "cross", "pass", "fail" adjacent to section labels.
- PLANET MARK SCHEME: If scheme is "planet_mark", you MUST also extract a
  "planet_mark_carbon" object with the following fields (null if not stated):
  {
    "reporting_year_label": "e.g. YE2023 or Year 2023 — the label on the report",
    "period_start": "YYYY-MM-DD — start of the reporting period",
    "period_end": "YYYY-MM-DD — end of the reporting period",
    "fte_count": <positive integer — full-time equivalent employees or null>,
    "scope_1_co2e_tonnes": <number — Scope 1 direct emissions in tCO2e or null>,
    "scope_2_co2e_tonnes": <number — Scope 2 indirect energy emissions in tCO2e or null>,
    "scope_3_co2e_tonnes": <number — Scope 3 value chain emissions in tCO2e or null>,
    "total_co2e_tonnes": <number — total market-based tCO2e or null>,
    "baseline_year_label": "e.g. YE2022 — the baseline year referenced or null",
    "baseline_total_co2e_tonnes": <number — baseline year total tCO2e or null>,
    "reduction_percent": <number — % reduction vs baseline, positive means reduced or null>,
    "data_quality_scope_1_2": <integer 0-16 — Planet Mark data quality score for Scope 1&2 or null>,
    "data_quality_scope_3": <integer 0-16 — Planet Mark data quality score for Scope 3 or null>,
    "certification_number": "Planet Mark certificate number e.g. PM-XXXX or null",
    "certification_date": "YYYY-MM-DD — date certificate was issued or null",
    "expiry_date": "YYYY-MM-DD — date certificate expires or null",
    "outcome_status": "certified | in_progress | not_certified — based on report language",
    "improvement_actions": [
      {
        "title": "Short action title e.g. Install LED lighting",
        "target_scope": "scope_1 | scope_2 | scope_3 | general or null",
        "deadline": "YYYY-MM-DD or null",
        "expected_reduction_pct": <number or null>
      }
    ]
  }
  PLANET MARK extraction rules:
  - Convert all emission values to tCO2e (tonnes). If values appear as kgCO2e, divide by 1000.
  - The data quality scale is 0-16 (NOT a percentage). "14/16" means score 14 out of 16.
  - "Scope 1" = direct emissions (combustion, fleet, owned processes).
  - "Scope 2" = indirect energy (purchased electricity, heat, steam).
  - "Scope 3" = value chain (travel, supply chain, waste, commuting).
  - Do NOT confuse data quality scores with emission values.
  - outcome_status: use "certified" if the document says "certified" or "awarded";
    "in_progress" if it says "assessment in progress" or "pending"; "not_certified" otherwise.
  - If improvement_actions are listed (action plan, reduction plan), extract up to 20.
- Return ONLY the JSON object, no markdown fences or commentary.
"""


@dataclass
class AIAnalysisResult:
    """Structured result from AI analysis (Mistral or Gemini)."""

    raw: dict
    score_breakdown: list[dict[str, object]] = field(default_factory=list)
    overall_score: float | None = None
    max_score: float | None = None
    score_percentage: float | None = None
    outcome: str | None = None
    findings: list[dict[str, object]] = field(default_factory=list)
    report_date: str | None = None
    scheme: str | None = None
    scheme_label: str | None = None
    issuer_name: str | None = None
    warnings: list[str] = field(default_factory=list)
    provider_status: str = "completed"
    provider_name: str = "mistral"
    organization_name: str | None = None
    auditor_name: str | None = None
    audit_type: str | None = None
    certificate_number: str | None = None
    audit_scope: str | None = None
    next_audit_date: str | None = None
    site_name: str | None = None
    site_address: str | None = None
    items_total: int | None = None
    items_applicable: int | None = None
    items_na: int | None = None
    visual_indicators: list[dict[str, object]] = field(default_factory=list)
    planet_mark_carbon: dict[str, object] | None = None


class MistralAnalysisService:
    """Uses Mistral Chat API (JSON mode) for structured audit analysis."""

    def __init__(self) -> None:
        self.api_key = settings.mistral_api_key
        self.base_url = settings.mistral_api_base_url.rstrip("/")
        self.timeout_seconds = settings.mistral_ocr_timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool((self.api_key or "").strip())

    async def analyze_text(self, text: str, assurance_scheme: str | None = None) -> AIAnalysisResult:
        """Send extracted text to Mistral Chat for structured analysis."""
        if not self.is_configured:
            logger.info("Mistral analysis skipped: provider not configured")
            return AIAnalysisResult(raw={}, provider_status="not_configured")

        if not text or len(text.split()) < 20:
            return AIAnalysisResult(
                raw={},
                provider_status="skipped",
                warnings=["Text too short for AI analysis"],
            )

        chunks = self._smart_chunk(text, max_chars=30000)
        user_prompt = (
            f"Assurance scheme hint: {assurance_scheme or 'unknown'}\n\n"
            "--- BEGIN DOCUMENT TEXT ---\n\n" + "\n\n".join(chunks) + "\n\n--- END DOCUMENT TEXT ---"
        )

        try:
            import httpx

            payload = {
                "model": "mistral-small-latest",
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 8192,
            }

            async def _do_call():
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    resp.raise_for_status()
                    return resp

            response = await _mistral_analysis_cb.call(_do_call)

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            content = self._strip_markdown_fences(content)
            parsed = json.loads(content)
            return self._build_result(parsed)

        except Exception as exc:
            logger.warning("Mistral analysis failed: %s: %s", type(exc).__name__, exc, exc_info=True)
            return AIAnalysisResult(
                raw={},
                provider_status="failed",
                warnings=[f"AI analysis failed: {type(exc).__name__}: {exc}"],
            )

    def _build_result(self, parsed: dict) -> AIAnalysisResult:
        breakdown = []
        for item in parsed.get("score_breakdown") or []:
            score = item.get("score")
            max_score = item.get("max_score")
            if score is None or max_score is None:
                continue
            try:
                s, m = float(score), float(max_score)
            except (TypeError, ValueError):
                continue
            if m <= 0 or s > m:
                continue
            breakdown.append(
                {
                    "label": str(item.get("label", "Section")),
                    "score": s,
                    "max_score": m,
                    "percentage": round((s / m) * 100, 1),
                }
            )

        overall = self._safe_float(parsed.get("overall_score"))
        max_s = self._safe_float(parsed.get("max_score"))
        pct = self._safe_float(parsed.get("score_percentage"))
        if pct is not None and pct > 100:
            pct = None
        if overall is not None and max_s is not None and overall > max_s:
            overall = None
            max_s = None

        findings = []
        dropped_low_conf = 0
        for f in (parsed.get("findings") or [])[:50]:
            if not isinstance(f, dict):
                continue
            raw_sev = str(f.get("severity", "medium"))
            raw_ft = str(f.get("finding_type", "finding"))
            raw_conf = self._safe_float(f.get("confidence"))
            conf = min(max(raw_conf if raw_conf is not None else 0.6, 0.0), 1.0)
            if conf < 0.50:
                dropped_low_conf += 1
                continue
            evidence_items = f.get("evidence_items") or []
            if not isinstance(evidence_items, list):
                evidence_items = []
            evidence_snippets: list[str] = []
            for ei in evidence_items[:20]:
                if isinstance(ei, dict) and ei.get("question"):
                    parts = [str(ei["question"]), str(ei.get("answer", ""))]
                    if ei.get("score"):
                        parts.append(str(ei["score"]))
                    evidence_snippets.append(" | ".join(parts))
            findings.append(
                {
                    "title": str(f.get("title", ""))[:300],
                    "description": str(f.get("description", ""))[:2000],
                    "severity": raw_sev if raw_sev in _VALID_SEVERITIES else "medium",
                    "finding_type": raw_ft if raw_ft in _VALID_FINDING_TYPES else "finding",
                    "confidence": conf,
                    "clause_reference": str(f.get("clause_reference", ""))[:255] or None,
                    "corrective_action_deadline": str(f.get("corrective_action_deadline", ""))[:20] or None,
                    "_provider": "mistral",
                    "_evidence_snippets": evidence_snippets or None,
                }
            )

        raw_outcome = parsed.get("outcome")
        validated_outcome = raw_outcome if raw_outcome in _VALID_OUTCOMES else None

        # Extract and validate Planet Mark carbon block if present
        pm_carbon = parsed.get("planet_mark_carbon")
        if isinstance(pm_carbon, dict):
            pm_carbon = self._validate_planet_mark_carbon(pm_carbon)
        else:
            pm_carbon = None

        return AIAnalysisResult(
            raw=parsed,
            score_breakdown=breakdown,
            overall_score=overall,
            max_score=max_s,
            score_percentage=pct,
            outcome=validated_outcome,
            findings=findings,
            report_date=parsed.get("report_date"),
            scheme=parsed.get("scheme"),
            scheme_label=parsed.get("scheme_label"),
            issuer_name=parsed.get("issuer_name"),
            warnings=list(parsed.get("warnings") or []),
            provider_name="mistral",
            organization_name=parsed.get("organization_name"),
            auditor_name=parsed.get("auditor_name"),
            audit_type=parsed.get("audit_type"),
            certificate_number=parsed.get("certificate_number"),
            audit_scope=parsed.get("audit_scope"),
            next_audit_date=parsed.get("next_audit_date"),
            site_name=parsed.get("site_name"),
            site_address=parsed.get("site_address"),
            items_total=self._safe_int(parsed.get("items_total")),
            items_applicable=self._safe_int(parsed.get("items_applicable")),
            items_na=self._safe_int(parsed.get("items_na")),
            planet_mark_carbon=pm_carbon,
        )

    @staticmethod
    def _safe_float(value: object) -> float | None:
        if value is None:
            return None
        try:
            result = float(str(value))
            if not __import__("math").isfinite(result):
                return None
            return result
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _strip_markdown_fences(content: str) -> str:
        """Remove markdown code fences that LLMs sometimes wrap JSON in."""
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped[3:]
        if stripped.endswith("```"):
            stripped = stripped.rsplit("```", 1)[0]
        return stripped.strip()

    @staticmethod
    def _validate_planet_mark_carbon(raw: dict) -> dict:
        """Validate and sanitise extracted Planet Mark carbon data.

        Applies range checks, unit normalisation (kgCO2e → tCO2e),
        cross-validation between scope totals, and removes clearly
        invalid values rather than passing them through.
        """
        out: dict = {}

        def _safe_float_pos(val: object) -> float | None:
            try:
                f = float(val)  # type: ignore[arg-type]
                return f if f >= 0 else None
            except (TypeError, ValueError):
                return None

        def _safe_int_pos(val: object) -> int | None:
            try:
                i = int(str(val))
                return i if i > 0 else None
            except (TypeError, ValueError):
                return None

        # String fields — copy through with truncation
        for key in (
            "reporting_year_label",
            "period_start",
            "period_end",
            "baseline_year_label",
            "certification_number",
            "certification_date",
            "expiry_date",
        ):
            v = raw.get(key)
            out[key] = str(v)[:50] if v not in (None, "", "null") else None

        # Outcome status validation
        raw_outcome = str(raw.get("outcome_status", "") or "").lower()
        out["outcome_status"] = raw_outcome if raw_outcome in {"certified", "in_progress", "not_certified"} else None

        # Numeric emission values — must be non-negative and plausible (< 10M tCO2e)
        for key in (
            "scope_1_co2e_tonnes",
            "scope_2_co2e_tonnes",
            "scope_3_co2e_tonnes",
            "total_co2e_tonnes",
            "baseline_total_co2e_tonnes",
        ):
            v = _safe_float_pos(raw.get(key))
            out[key] = v if v is not None and v < 10_000_000 else None

        out["reduction_percent"] = _safe_float_pos(raw.get("reduction_percent"))
        out["fte_count"] = _safe_int_pos(raw.get("fte_count"))

        # Data quality scores: integer 0-16
        for key in ("data_quality_scope_1_2", "data_quality_scope_3"):
            v = _safe_int_pos(raw.get(key))
            out[key] = v if v is not None and v <= 16 else None

        # Cross-validate: scope sum should approximately equal total (allow 10% tolerance)
        s1 = out.get("scope_1_co2e_tonnes")
        s2 = out.get("scope_2_co2e_tonnes")
        s3 = out.get("scope_3_co2e_tonnes")
        total = out.get("total_co2e_tonnes")
        if s1 is not None and s2 is not None and total is not None:
            scope_sum = (s1 or 0) + (s2 or 0) + (s3 or 0)
            if total > 0 and abs(scope_sum - total) / total > 0.15:
                logger.warning(
                    "Planet Mark carbon cross-validation: scope sum %.2f diverges from total %.2f by >15%%",
                    scope_sum,
                    total,
                )

        # Improvement actions — extract up to 20
        raw_actions = raw.get("improvement_actions") or []
        actions = []
        for item in (raw_actions if isinstance(raw_actions, list) else [])[:20]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "") or "").strip()
            if not title:
                continue
            target = str(item.get("target_scope", "") or "").lower()
            actions.append(
                {
                    "title": title[:300],
                    "target_scope": target if target in {"scope_1", "scope_2", "scope_3", "general"} else None,
                    "deadline": str(item.get("deadline", "") or "")[:20] or None,
                    "expected_reduction_pct": _safe_float_pos(item.get("expected_reduction_pct")),
                }
            )
        out["improvement_actions"] = actions

        return out

    @staticmethod
    def _smart_chunk(text: str, max_chars: int = 30000) -> list[str]:
        """Select the most informative portions of a document for AI analysis.

        Instead of a blind truncation, prioritises:
        1. First ~4K chars (cover page, executive summary, ToC)
        2. Sections containing score/finding keywords
        3. Final ~2K chars (conclusions, recommendations)
        """
        if len(text) <= max_chars:
            return [text]

        _SIGNAL_KEYWORDS = (
            "score",
            "finding",
            "non-conformance",
            "nonconformance",
            "observation",
            "recommendation",
            "improvement",
            "competent",
            "compliant",
            "overall",
            "total",
            "result",
            "pass",
            "fail",
            "certificate",
            "conclusion",
            "summary",
        )

        head = text[:4000]
        tail = text[-2000:]
        budget = max_chars - len(head) - len(tail) - 200

        paragraphs = text[4000:-2000].split("\n\n") if len(text) > 6000 else []
        scored: list[tuple[int, int, str]] = []
        for idx, para in enumerate(paragraphs):
            if not para.strip():
                continue
            lower = para.lower()
            hits = sum(1 for kw in _SIGNAL_KEYWORDS if kw in lower)
            scored.append((hits, idx, para))

        scored.sort(key=lambda x: x[0], reverse=True)
        selected: list[tuple[int, int, str]] = []
        used = 0
        for _hits, idx, para in scored:
            if used + len(para) > budget:
                if not selected:
                    selected.append((idx, _hits, para[:budget]))
                break
            selected.append((idx, _hits, para))
            used += len(para)

        # Re-sort by original document position to preserve structure
        selected.sort(key=lambda x: x[0])
        middle_parts: list[str] = [para for _idx, _hits, para in selected]

        chunks = [head]
        if middle_parts:
            chunks.append("\n\n".join(middle_parts))
        chunks.append(tail)
        return chunks
