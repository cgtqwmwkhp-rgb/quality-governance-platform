"""AI Consensus Service — reconciles results from multiple AI providers.

Uses Bayesian combination of independent confidence signals and flags
disagreements for human review.  Designed so that two independent models
catching the same data point produces mathematically justified high
confidence, while disagreements are surfaced as warnings.
"""

from __future__ import annotations

import copy
import logging
import math
from difflib import SequenceMatcher

from src.domain.services.mistral_analysis_service import AIAnalysisResult

logger = logging.getLogger(__name__)

SCORE_TOLERANCE_PCT = 5.0
SCORE_RELATIVE_TOLERANCE = 0.10
TITLE_SIMILARITY_THRESHOLD = 0.85
SECTION_LABEL_SIMILARITY_THRESHOLD = 0.7
CORRELATION_DISCOUNT = 0.9


class AIConsensusService:
    """Reconcile two independent AI analysis results into a single consensus."""

    def reconcile(
        self,
        result_a: AIAnalysisResult,
        result_b: AIAnalysisResult,
    ) -> AIAnalysisResult:
        result_a = copy.deepcopy(result_a)
        result_b = copy.deepcopy(result_b)

        a_ok = result_a.provider_status == "completed"
        b_ok = result_b.provider_status == "completed"

        if a_ok and not b_ok:
            result_a.warnings.append(self._degradation_message(result_a, result_b))
            return result_a
        if b_ok and not a_ok:
            result_b.warnings.append(self._degradation_message(result_b, result_a))
            return result_b
        if not a_ok and not b_ok:
            return AIAnalysisResult(
                raw={},
                provider_status="failed",
                provider_name="consensus",
                warnings=["Both AI providers failed"],
            )

        warnings: list[str] = []
        warnings.extend(result_a.warnings)
        warnings.extend(result_b.warnings)

        # Deduplicate similar warnings (>85% match)
        warnings = self._deduplicate_warnings(warnings)

        scores = self._reconcile_scores(result_a, result_b, warnings)
        findings = self._reconcile_findings(result_a, result_b, warnings)
        metadata = self._reconcile_metadata(result_a, result_b, warnings)
        outcome = self._reconcile_outcome(result_a, result_b, scores["score_percentage"], warnings)

        merged_vis = list(result_a.visual_indicators) + list(result_b.visual_indicators)

        return AIAnalysisResult(
            raw={"consensus_from": [result_a.provider_name, result_b.provider_name]},
            score_breakdown=scores["breakdown"],
            overall_score=scores["overall"],
            max_score=scores["max_score"],
            score_percentage=scores["score_percentage"],
            outcome=outcome,
            findings=findings,
            report_date=metadata["report_date"],
            scheme=metadata["scheme"],
            scheme_label=metadata["scheme_label"],
            issuer_name=metadata["issuer_name"],
            warnings=warnings,
            provider_status="completed",
            provider_name="consensus",
            organization_name=metadata.get("organization_name"),
            auditor_name=metadata.get("auditor_name"),
            audit_type=metadata.get("audit_type"),
            certificate_number=metadata.get("certificate_number"),
            audit_scope=metadata.get("audit_scope"),
            next_audit_date=metadata.get("next_audit_date"),
            site_name=metadata.get("site_name"),
            site_address=metadata.get("site_address"),
            items_total=metadata.get("items_total"),
            items_applicable=metadata.get("items_applicable"),
            items_na=metadata.get("items_na"),
            visual_indicators=merged_vis,
        )

    def _reconcile_scores(
        self,
        a: AIAnalysisResult,
        b: AIAnalysisResult,
        warnings: list[str],
    ) -> dict:
        breakdown = a.score_breakdown or b.score_breakdown or []
        if a.score_breakdown and b.score_breakdown:
            breakdown = self._merge_score_breakdowns(a.score_breakdown, b.score_breakdown, warnings)

        overall = self._pick_agreed_float(a.overall_score, b.overall_score, "overall_score", warnings)
        max_s = self._pick_agreed_float(a.max_score, b.max_score, "max_score", warnings)
        pct = self._pick_agreed_float(a.score_percentage, b.score_percentage, "score_percentage", warnings)

        if pct is not None:
            pct = max(0.0, min(pct, 100.0))

        return {"breakdown": breakdown, "overall": overall, "max_score": max_s, "score_percentage": pct}

    def _merge_score_breakdowns(
        self,
        sections_a: list[dict],
        sections_b: list[dict],
        warnings: list[str],
    ) -> list[dict]:
        """Merge score breakdowns using fuzzy label matching."""
        merged: list[dict] = []
        used_b: set[int] = set()
        agreed = 0

        for sa in sections_a:
            label_a = str(sa.get("label", "")).lower()
            best_idx: int | None = None
            best_ratio = 0.0
            for idx, sb in enumerate(sections_b):
                if idx in used_b:
                    continue
                label_b = str(sb.get("label", "")).lower()
                ratio = SequenceMatcher(None, label_a, label_b).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_idx = idx

            if best_idx is not None and best_ratio >= SECTION_LABEL_SIMILARITY_THRESHOLD:
                sb = sections_b[best_idx]
                used_b.add(best_idx)
                agreed += 1
                try:
                    avg_score: float = round((float(str(sa.get("score", 0))) + float(str(sb.get("score", 0)))) / 2, 1)
                    avg_max: float = round(
                        (float(str(sa.get("max_score", 0))) + float(str(sb.get("max_score", 0)))) / 2, 1
                    )
                except (TypeError, ValueError):
                    avg_score = float(str(sa.get("score", 0)))
                    avg_max = float(str(sa.get("max_score", 0)))
                merged.append(
                    {
                        "label": sa.get("label"),
                        "score": avg_score,
                        "max_score": avg_max,
                        "percentage": round((avg_score / avg_max) * 100, 1) if avg_max else 0,
                        "_consensus": "agreed",
                    }
                )
            else:
                entry = dict(sa)
                entry["_consensus"] = "single_source"
                merged.append(entry)

        for idx, sb in enumerate(sections_b):
            if idx not in used_b:
                entry = dict(sb)
                entry["_consensus"] = "single_source"
                merged.append(entry)

        if agreed:
            warnings.append(f"Score breakdown consensus: {agreed} sections agreed by both providers")
        return merged

    def _reconcile_findings(
        self,
        a: AIAnalysisResult,
        b: AIAnalysisResult,
        warnings: list[str],
    ) -> list[dict[str, object]]:
        merged: list[dict[str, object]] = []
        used_b: set[int] = set()

        for af in a.findings:
            matched_idx = self._find_similar_finding(af, b.findings, used_b)
            if matched_idx is not None:
                bf = b.findings[matched_idx]
                used_b.add(matched_idx)
                conf_a = float(str(af.get("confidence", 0.5)))
                conf_b = float(str(bf.get("confidence", 0.5)))
                combined = self._bayesian_combine(conf_a, conf_b)
                finding = dict(af)
                finding["confidence"] = round(combined, 3)
                finding["_consensus"] = "agreed"
                finding["_provider"] = "consensus"
                finding["_providers"] = [a.provider_name, b.provider_name]
                merged.append(finding)
            else:
                finding = dict(af)
                finding["_consensus"] = "single_source"
                finding["_providers"] = [a.provider_name]
                finding["_provider"] = a.provider_name
                merged.append(finding)

        for idx, bf in enumerate(b.findings):
            if idx in used_b:
                continue
            finding = dict(bf)
            finding["_consensus"] = "single_source"
            finding["_providers"] = [b.provider_name]
            finding["_provider"] = b.provider_name
            merged.append(finding)

        agreed = sum(1 for f in merged if f.get("_consensus") == "agreed")
        single = sum(1 for f in merged if f.get("_consensus") == "single_source")
        if agreed:
            warnings.append(f"Finding consensus: {agreed} findings confirmed by both providers")

        count_diff = abs(len(a.findings) - len(b.findings))
        if count_diff > 2:
            warnings.append(
                f"Finding count divergence: {a.provider_name} found {len(a.findings)}, "
                f"{b.provider_name} found {len(b.findings)} — {single} unmatched"
            )

        return merged

    def _reconcile_metadata(
        self,
        a: AIAnalysisResult,
        b: AIAnalysisResult,
        warnings: list[str],
    ) -> dict:
        result: dict = {}

        _FREE_TEXT_FIELDS = {
            "organization_name",
            "auditor_name",
            "audit_scope",
            "scheme_label",
            "certificate_number",
            "site_name",
            "site_address",
        }

        for field_name in (
            "report_date",
            "scheme",
            "scheme_label",
            "issuer_name",
            "organization_name",
            "auditor_name",
            "audit_type",
            "certificate_number",
            "audit_scope",
            "next_audit_date",
            "site_name",
            "site_address",
        ):
            val_a = getattr(a, field_name, None)
            val_b = getattr(b, field_name, None)

            if val_a and val_b and val_a != val_b:
                warnings.append(
                    f"Metadata disagreement on {field_name}: "
                    f"{a.provider_name}='{val_a}' vs {b.provider_name}='{val_b}'"
                )
                if field_name in _FREE_TEXT_FIELDS:
                    result[field_name] = val_a if len(str(val_a)) >= len(str(val_b)) else val_b
                else:
                    result[field_name] = val_a
            else:
                result[field_name] = val_a or val_b

        for int_field in ("items_total", "items_applicable", "items_na"):
            va = getattr(a, int_field, None)
            vb = getattr(b, int_field, None)
            if va is not None and vb is not None and va != vb:
                result[int_field] = max(va, vb)
            else:
                result[int_field] = va if va is not None else vb

        return result

    def _reconcile_outcome(
        self,
        a: AIAnalysisResult,
        b: AIAnalysisResult,
        score_pct: float | None,
        warnings: list[str],
    ) -> str | None:
        if a.outcome and b.outcome:
            if a.outcome == b.outcome:
                return a.outcome
            warnings.append(
                f"Outcome disagreement: {a.provider_name}='{a.outcome}' vs "
                f"{b.provider_name}='{b.outcome}' — flagged for review"
            )
            severity_order = {"fail": 0, "review_required": 1, "conditional_pass": 2, "pass": 3}
            return a.outcome if severity_order.get(a.outcome, 1) <= severity_order.get(b.outcome, 1) else b.outcome
        return a.outcome or b.outcome

    @staticmethod
    def _deduplicate_warnings(warnings: list[str]) -> list[str]:
        """Remove warnings that are >85% similar to an earlier warning."""
        deduped: list[str] = []
        for w in warnings:
            is_dup = False
            for existing in deduped:
                if SequenceMatcher(None, w.lower(), existing.lower()).ratio() > 0.85:
                    is_dup = True
                    break
            if not is_dup:
                deduped.append(w)
        return deduped

    @staticmethod
    def _degradation_message(ok_result: AIAnalysisResult, failed_result: AIAnalysisResult) -> str:
        """Provide an actionable message based on the failure mode."""
        status = failed_result.provider_status
        name = failed_result.provider_name
        detail = ""
        if failed_result.warnings:
            last_warn = failed_result.warnings[-1]
            if "CircuitBreakerOpenError" in last_warn:
                detail = f" — {name} circuit breaker is open (will auto-recover)"
            elif "NotFound" in last_warn or "404" in last_warn:
                detail = f" — {name} AI model may need updating"
            elif "TimeoutError" in last_warn or "timed out" in last_warn.lower():
                detail = f" — {name} timed out on this document"

        if status == "not_configured":
            return f"Single-provider result ({ok_result.provider_name}); {name} is not configured — add API key in settings"
        if status == "skipped":
            return f"Single-provider result ({ok_result.provider_name}); {name} was skipped (document too large or too short)"
        return f"Single-provider result ({ok_result.provider_name}); {name} {status}{detail}"

    def _find_similar_finding(
        self,
        target: dict,
        candidates: list[dict],
        used: set[int],
    ) -> int | None:
        target_title = str(target.get("title", "")).lower()
        target_desc = str(target.get("description", "")).lower()[:500]
        target_ft = str(target.get("finding_type", ""))
        best_idx: int | None = None
        best_score = 0.0

        for idx, candidate in enumerate(candidates):
            if idx in used:
                continue
            cand_title = str(candidate.get("title", "")).lower()
            cand_desc = str(candidate.get("description", "")).lower()[:500]
            cand_ft = str(candidate.get("finding_type", ""))

            target_clause = str(target.get("clause_reference", "") or "").strip().lower()
            cand_clause = str(candidate.get("clause_reference", "") or "").strip().lower()
            if target_clause and cand_clause and target_clause != cand_clause:
                continue

            title_sim = SequenceMatcher(None, target_title, cand_title).ratio()
            desc_sim = SequenceMatcher(None, target_desc, cand_desc).ratio() if target_desc and cand_desc else 0.0
            ft_match = 1.0 if target_ft == cand_ft else 0.0

            composite = (title_sim * 0.60) + (desc_sim * 0.25) + (ft_match * 0.15)

            if composite > best_score and title_sim >= TITLE_SIMILARITY_THRESHOLD:
                best_score = composite
                best_idx = idx

        return best_idx

    @staticmethod
    def _bayesian_combine(conf_a: float, conf_b: float) -> float:
        """Bayesian combination with correlation discount.

        Both providers read the same document, so their signals are correlated,
        not independent.  A discount factor prevents over-confidence.
        """
        conf_a = max(0.01, min(0.99, conf_a))
        conf_b = max(0.01, min(0.99, conf_b))
        numerator = conf_a * conf_b
        denominator = numerator + (1 - conf_a) * (1 - conf_b)
        raw = numerator / denominator if denominator > 0 else 0.5
        return raw * CORRELATION_DISCOUNT

    def _pick_agreed_float(
        self,
        val_a: float | None,
        val_b: float | None,
        field_name: str,
        warnings: list[str],
    ) -> float | None:
        if val_a is not None and not math.isfinite(val_a):
            val_a = None
        if val_b is not None and not math.isfinite(val_b):
            val_b = None
        if val_a is not None and val_b is not None:
            abs_diff = abs(val_a - val_b)
            denom = max(abs(val_a), abs(val_b), 1.0)
            rel_diff = abs_diff / denom
            if abs_diff <= SCORE_TOLERANCE_PCT and rel_diff <= SCORE_RELATIVE_TOLERANCE:
                return round((val_a + val_b) / 2, 2)
            warnings.append(f"Score disagreement on {field_name}: {val_a} vs {val_b}")
            return val_a
        return val_a if val_a is not None else val_b
