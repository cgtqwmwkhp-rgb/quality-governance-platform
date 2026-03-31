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

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert audit document analyst for a quality governance platform.
Given extracted text from an external audit report, return a JSON object with
the following structure.  Be precise — only include data that is clearly
stated in the text.  Do NOT invent values.

{
  "scheme": "achilles_uvdb | iso | planet_mark | customer_other",
  "scheme_label": "Human-readable scheme name",
  "scheme_version": "e.g. B2, ISO 9001:2015, or null",
  "issuer_name": "e.g. Achilles, BSI, or null",
  "report_date": "YYYY-MM-DD or null",
  "overall_score": <number or null>,
  "max_score": <number or null>,
  "score_percentage": <number 0-100 or null>,
  "outcome": "pass | fail | review_required",
  "score_breakdown": [
    {"label": "Section name", "score": <number>, "max_score": <number>}
  ],
  "findings": [
    {
      "title": "Short title",
      "description": "Evidence text from the document",
      "severity": "low | medium | high | critical",
      "finding_type": "nonconformity | positive_practice | observation | opportunity_for_improvement | competence_gap",
      "confidence": <0.0 to 1.0>
    }
  ],
  "warnings": ["Any data quality concerns"]
}

Rules:
- score_breakdown entries MUST have score <= max_score.  Reject date-like
  values (e.g. 23/6 meaning June 23) — those are dates, not scores.
- confidence should reflect how clearly the finding is stated in the text.
- If a score or finding is ambiguous, add a warning instead of guessing.
- Return ONLY the JSON object, no markdown fences or commentary.
"""


@dataclass
class AIAnalysisResult:
    """Structured result from Mistral AI analysis."""

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

        trimmed = text[:12000]
        user_prompt = f"Assurance scheme hint: {assurance_scheme or 'unknown'}\n\n---\n\n{trimmed}"

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
                "max_tokens": 4096,
            }
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return self._build_result(parsed)

        except Exception as exc:
            logger.warning("Mistral analysis failed: %s", type(exc).__name__, exc_info=True)
            return AIAnalysisResult(
                raw={},
                provider_status="failed",
                warnings=[f"AI analysis failed: {type(exc).__name__}"],
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
        for f in parsed.get("findings") or []:
            findings.append(
                {
                    "title": str(f.get("title", "")),
                    "description": str(f.get("description", "")),
                    "severity": str(f.get("severity", "medium")),
                    "finding_type": str(f.get("finding_type", "finding")),
                    "confidence": min(max(self._safe_float(f.get("confidence")) or 0.5, 0.0), 1.0),
                }
            )

        return AIAnalysisResult(
            raw=parsed,
            score_breakdown=breakdown,
            overall_score=overall,
            max_score=max_s,
            score_percentage=pct,
            outcome=parsed.get("outcome"),
            findings=findings,
            report_date=parsed.get("report_date"),
            scheme=parsed.get("scheme"),
            scheme_label=parsed.get("scheme_label"),
            issuer_name=parsed.get("issuer_name"),
            warnings=parsed.get("warnings") or [],
        )

    @staticmethod
    def _safe_float(value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None
