"""Gemini 2.5 Pro multimodal review service for audit document analysis.

Provides an independent second-opinion analysis by sending the raw PDF
to Gemini, which can visually interpret colors, checkmarks, table layouts,
stamps, and other visual elements that text-only extraction misses.
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import tempfile
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from src.domain.services.mistral_analysis_service import AIAnalysisResult
from src.infrastructure.resilience.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_gemini_review_cb = CircuitBreaker("gemini_review", failure_threshold=5, recovery_timeout=300)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
GEMINI_API_KEY_ENV = "GOOGLE_GEMINI_API_KEY"
MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB hard limit
GEMINI_TIMEOUT_SECONDS = 120
_VALID_SEVERITIES = frozenset({"low", "medium", "high", "critical"})
_VALID_FINDING_TYPES = frozenset(
    {"nonconformity", "positive_practice", "observation", "opportunity_for_improvement", "competence_gap", "finding"}
)
_VALID_OUTCOMES = frozenset({"pass", "fail", "review_required"})

_REVIEW_PROMPT = """\
You are an expert audit document analyst. Analyse the attached audit report
document and the supplementary extracted text below.  You can SEE the document
visually — use visual cues (colours, checkmarks, crosses, traffic lights,
stamps, table shading, logos) alongside the text content.

Return a JSON object with this exact structure (no markdown fences):

{
  "scheme": "achilles_uvdb | iso | planet_mark | smeta | ecovadis | customer_other",
  "scheme_label": "Human-readable scheme name",
  "scheme_version": "e.g. B2, ISO 9001:2015, or null",
  "issuer_name": "e.g. Achilles, BSI, or null",
  "report_date": "YYYY-MM-DD or null",
  "organization_name": "Name of company being audited, or null",
  "auditor_name": "Lead auditor name, or null",
  "audit_type": "initial | surveillance | recertification | transfer | null",
  "certificate_number": "Certificate/registration number, or null",
  "audit_scope": "Scope description, or null",
  "next_audit_date": "YYYY-MM-DD or null",
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
      "confidence": <0.0 to 1.0>,
      "clause_reference": "e.g. ISO 9001:2015 clause 9.1.3, or null",
      "corrective_action_deadline": "YYYY-MM-DD or null"
    }
  ],
  "visual_indicators": [
    {
      "page": <page number>,
      "element": "green_cell | red_cell | amber_cell | checkmark | cross | stamp | logo",
      "context": "What the visual element relates to",
      "interpretation": "pass | fail | observation | neutral"
    }
  ],
  "warnings": ["Any data quality concerns"]
}

Rules:
- score_breakdown entries MUST have score <= max_score.
- For ISO audits: typically NO numeric scores, only conformity status.
- GREEN cells/highlights = pass/compliant. RED = fail/nonconformity. AMBER = observation/partial.
- Checkmarks (✓/✔) = pass. Crosses (✗/✘) = fail.
- For each finding, assign a calibrated confidence score between 0.0 and 1.0:
  * 0.90-1.0: Finding is explicitly stated with clear, unambiguous evidence
  * 0.70-0.89: Finding is strongly implied with visual or textual evidence
  * 0.50-0.69: Finding is inferred from context or ambiguous indicators
  * Below 0.50: Uncertain — only include if other evidence supports it
- If ambiguous, add a warning instead of guessing.
- Return ONLY the JSON object.
"""


class GeminiReviewService:
    """Independent multimodal audit document reviewer using Gemini 2.5 Pro."""

    def __init__(self) -> None:
        from src.core.config import settings

        self.api_key = settings.google_gemini_api_key or os.environ.get(GEMINI_API_KEY_ENV)
        self._client = None

    @property
    def is_configured(self) -> bool:
        return bool((self.api_key or "").strip())

    def _get_client(self):
        if self._client is None:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(GEMINI_MODEL)
            except ImportError:
                logger.warning("google-generativeai not installed; Gemini review disabled")
                return None
            except Exception as e:
                logger.error("Failed to initialise Gemini review client: %s", e)
                return None
        return self._client

    async def review(
        self,
        *,
        raw_pdf: bytes,
        text: str,
        filename: str = "audit_report.pdf",
        content_type: str = "application/pdf",
        assurance_scheme: str | None = None,
    ) -> AIAnalysisResult:
        """Analyse an audit document using Gemini multimodal (PDF + text)."""
        if not self.is_configured:
            logger.info("Gemini review skipped: not configured")
            return AIAnalysisResult(raw={}, provider_status="not_configured", provider_name="gemini")

        if len(raw_pdf) > MAX_PDF_SIZE_BYTES:
            logger.warning("Gemini review skipped: PDF size %d exceeds limit %d", len(raw_pdf), MAX_PDF_SIZE_BYTES)
            return AIAnalysisResult(
                raw={},
                provider_status="skipped",
                provider_name="gemini",
                warnings=[
                    f"PDF too large for Gemini review ({len(raw_pdf) // (1024*1024)}MB > {MAX_PDF_SIZE_BYTES // (1024*1024)}MB limit)"
                ],
            )

        client = self._get_client()
        if not client:
            return AIAnalysisResult(
                raw={},
                provider_status="failed",
                provider_name="gemini",
                warnings=["Gemini SDK unavailable"],
            )

        scheme_hint = f"\nAssurance scheme hint: {assurance_scheme}" if assurance_scheme else ""
        text_excerpt = text[:8000] if text else ""
        user_message = (
            f"{_REVIEW_PROMPT}{scheme_hint}\n\n"
            f"--- BEGIN SUPPLEMENTARY TEXT (first 8000 chars) ---\n{text_excerpt}\n--- END SUPPLEMENTARY TEXT ---"
        )

        def _run():
            import google.generativeai as genai  # noqa: F811

            mime = mimetypes.guess_type(filename)[0] or content_type
            suffix = Path(filename).suffix or ".pdf"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(raw_pdf)
                tmp_path = tmp.name
            try:
                uploaded = genai.upload_file(path=tmp_path, display_name=filename, mime_type=mime)
                response = client.generate_content([user_message, uploaded])
                return response.text
            finally:
                os.unlink(tmp_path)

        try:
            raw_text = await self._call_with_retry(_run)
            raw_text = (raw_text or "").strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("```", 1)[0]

            parsed = json.loads(raw_text.strip())
            return self._build_result(parsed)
        except Exception as exc:
            logger.warning("Gemini review failed: %s: %s", type(exc).__name__, exc, exc_info=True)
            return AIAnalysisResult(
                raw={},
                provider_status="failed",
                provider_name="gemini",
                warnings=[f"Gemini review failed: {type(exc).__name__}: {exc}"],
            )

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _call_with_retry(self, run_fn):
        """Wrap the actual Gemini API call so tenacity can retry on transient errors."""
        return await asyncio.wait_for(
            _gemini_review_cb.call(asyncio.to_thread, run_fn),
            timeout=GEMINI_TIMEOUT_SECONDS,
        )

    def _build_result(self, parsed: object) -> AIAnalysisResult:
        if not isinstance(parsed, dict):
            return AIAnalysisResult(
                raw={},
                provider_status="failed",
                provider_name="gemini",
                warnings=["Gemini returned non-object JSON"],
            )
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
        for f in (parsed.get("findings") or [])[:50]:
            if not isinstance(f, dict):
                continue
            raw_sev = str(f.get("severity", "medium"))
            raw_ft = str(f.get("finding_type", "finding"))
            raw_conf = self._safe_float(f.get("confidence"))
            conf: float = min(max(raw_conf if raw_conf is not None else 0.6, 0.0), 1.0)
            clause_ref = str(f.get("clause_reference", ""))[:255] or None
            deadline = str(f.get("corrective_action_deadline", ""))[:20] or None
            findings.append(
                {
                    "title": str(f.get("title", ""))[:300],
                    "description": str(f.get("description", ""))[:2000],
                    "severity": raw_sev if raw_sev in _VALID_SEVERITIES else "medium",
                    "finding_type": raw_ft if raw_ft in _VALID_FINDING_TYPES else "finding",
                    "confidence": conf,
                    "clause_reference": clause_ref,
                    "corrective_action_deadline": deadline,
                    "_provider": "gemini",
                }
            )

        warnings = list(parsed.get("warnings") or [])
        for vi in parsed.get("visual_indicators") or []:
            warnings.append(
                f"Visual: page {vi.get('page', '?')} — {vi.get('element', '?')}: "
                f"{vi.get('context', '')} → {vi.get('interpretation', '?')}"
            )

        raw_outcome = parsed.get("outcome")
        validated_outcome = raw_outcome if raw_outcome in _VALID_OUTCOMES else None

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
            warnings=warnings,
            provider_status="completed",
            provider_name="gemini",
            organization_name=parsed.get("organization_name"),
            auditor_name=parsed.get("auditor_name"),
            audit_type=parsed.get("audit_type"),
            certificate_number=parsed.get("certificate_number"),
            audit_scope=parsed.get("audit_scope"),
            next_audit_date=parsed.get("next_audit_date"),
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
