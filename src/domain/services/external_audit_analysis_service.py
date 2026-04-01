"""Turn extracted external audit text into normalized reviewable audit results."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import cast

from src.domain.services.achilles_mapping_service import AchillesMappingService
from src.domain.services.iso_compliance_service import iso_compliance_service
from src.domain.services.iso_cross_mapping_service import ISOCrossMappingService
from src.domain.services.mistral_analysis_service import AIAnalysisResult


@dataclass
class DraftFindingCandidate:
    """Candidate finding before persistence."""

    title: str
    description: str
    severity: str
    finding_type: str
    confidence_score: float
    competence_verdict: str | None
    source_pages: list[int] = field(default_factory=list)
    evidence_snippets: list[str] = field(default_factory=list)
    mapped_frameworks: list[dict[str, object]] = field(default_factory=list)
    mapped_standards: list[dict[str, object]] = field(default_factory=list)
    suggested_action_title: str | None = None
    suggested_action_description: str | None = None
    suggested_risk_title: str | None = None
    provenance: dict[str, object] = field(default_factory=dict)


@dataclass
class ExternalAuditAnalysisResult:
    """Structured analysis output for an import job."""

    summary: str
    findings: list[DraftFindingCandidate]
    mapped_frameworks: list[dict[str, object]]
    mapped_standards: list[dict[str, object]]
    detected_scheme: str
    detected_scheme_confidence: float
    scheme_version: str | None
    issuer_name: str | None
    report_date: datetime | None
    overall_score: float | None
    max_score: float | None
    score_percentage: float | None
    outcome_status: str
    classification_basis: dict[str, object]
    score_breakdown: list[dict[str, object]]
    evidence_preview: list[dict[str, object]]
    positive_summary: list[dict[str, object]]
    nonconformity_summary: list[dict[str, object]]
    improvement_summary: list[dict[str, object]]
    processing_warnings: list[str]


class ExternalAuditAnalysisService:
    """Scheme-aware first-pass analysis with normalized score and evidence previews."""

    _NONCONFORMITY_TRIGGERS: tuple[tuple[str, str, str, float], ...] = (
        ("major non-conformance", "high", "nonconformity", 0.9),
        ("major nonconformance", "high", "nonconformity", 0.9),
        ("major non-conformity", "high", "nonconformity", 0.9),
        ("minor non-conformance", "medium", "nonconformity", 0.8),
        ("minor nonconformance", "medium", "nonconformity", 0.8),
        ("minor non-conformity", "medium", "nonconformity", 0.8),
        ("corrective action required", "high", "nonconformity", 0.85),
        ("critical finding", "critical", "nonconformity", 0.92),
        ("significant deficiency", "high", "nonconformity", 0.82),
        ("does not meet", "high", "nonconformity", 0.78),
        ("failed to demonstrate", "high", "nonconformity", 0.78),
        ("inadequate", "medium", "nonconformity", 0.65),
        ("area of concern", "medium", "nonconformity", 0.70),
        ("observation", "low", "observation", 0.65),
        ("not competent", "high", "competence_gap", 0.85),
        ("non-compliant", "high", "nonconformity", 0.8),
        ("non compliant", "high", "nonconformity", 0.8),
    )
    _GENERIC_FINDING_RE = re.compile(r"\bfindings?\s*[#:\d(]", re.IGNORECASE)
    _POSITIVE_TRIGGERS: tuple[tuple[str, str, str, float], ...] = (
        ("good practice", "low", "positive_practice", 0.92),
        ("best practice", "low", "positive_practice", 0.92),
        ("exemplary", "low", "positive_practice", 0.90),
        ("exceeds requirements", "low", "positive_practice", 0.90),
        ("fully compliant", "low", "positive_practice", 0.92),
        ("strength", "low", "positive_practice", 0.88),
        ("compliant", "low", "positive_practice", 0.88),
        ("conforms", "low", "positive_practice", 0.85),
        ("competent", "low", "positive_practice", 0.87),
        ("effective", "low", "positive_practice", 0.80),
        ("satisfactory", "low", "positive_practice", 0.78),
        ("well managed", "low", "positive_practice", 0.82),
    )
    _CONFIDENCE_BOOSTERS: tuple[str, ...] = (
        "compliant",
        "conforms",
        "competent",
        "effective",
        "satisfactory",
        "meets requirements",
        "acceptable",
        "adequate",
        "verified",
    )
    _IMPROVEMENT_TRIGGERS: tuple[tuple[str, str, str, float], ...] = (
        ("opportunity for improvement", "medium", "opportunity_for_improvement", 0.88),
        ("improvement opportunity", "medium", "opportunity_for_improvement", 0.84),
        ("recommendation", "medium", "opportunity_for_improvement", 0.72),
        ("recommended improvement", "medium", "opportunity_for_improvement", 0.76),
    )
    _ISO_STANDARD_PATTERNS: tuple[tuple[str, str], ...] = (
        ("ISO 9001", r"\biso\s*9001(?::?2015)?\b"),
        ("ISO 14001", r"\biso\s*14001(?::?2015)?\b"),
        ("ISO 27001", r"\biso(?:\/iec)?\s*27001(?::?2022)?\b"),
        ("ISO 45001", r"\biso\s*45001(?::?2018)?\b"),
    )
    _OUTCOME_PATTERNS: tuple[tuple[str, str], ...] = (
        ("fail", r"\b(failed|not competent|major non[- ]conformance|non[- ]compliant)\b"),
        ("pass", r"\b(certif(?:ied|ication)\s+recommended|recommended\s+for\s+certification|passed|pass)\b"),
        ("review_required", r"\b(observation|opportunity for improvement|improvement opportunity)\b"),
    )
    _CONTEXTUAL_DATE_LABELS = re.compile(
        r"(?:audit\s+date|date\s+of\s+(?:audit|assessment|inspection|visit)|report\s+date|assessment\s+date)"
        r"[:\s\-–]+",
        re.IGNORECASE,
    )
    _DATE_PATTERNS: tuple[str, ...] = (
        r"\b(\d{4}-\d{2}-\d{2})\b",
        r"\b(\d{2}/\d{2}/\d{4})\b",
        r"\b(\d{2}-\d{2}-\d{4})\b",
    )
    _LONG_DATE_RE = re.compile(
        r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{4})\b",
        re.IGNORECASE,
    )
    _LONG_DATE_ALT_RE = re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2}),?\s+(\d{4})\b",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self.achilles_mapping_service = AchillesMappingService()
        self.iso_mapping_service = ISOCrossMappingService()

    def analyze(
        self,
        *,
        extracted_text: str,
        page_texts: list[str],
        assurance_scheme: str | None,
        ai_result: AIAnalysisResult | None = None,
    ) -> ExternalAuditAnalysisResult:
        normalized_text = extracted_text.strip()
        scheme_match = self._detect_scheme(normalized_text, assurance_scheme)
        scheme = self._as_str(scheme_match["scheme"])
        scheme_label = self._as_str(scheme_match["label"])
        scheme_confidence = self._as_float(scheme_match["confidence"])
        scheme_signals = cast(list[str], scheme_match["signals"])
        frameworks = self._detect_frameworks(normalized_text, assurance_scheme, scheme)
        standards = self._build_standard_mappings(normalized_text)
        scorecard = self._extract_scorecard(normalized_text, page_texts, scheme)
        overall_score = self._as_optional_float(scorecard["overall_score"])
        max_score = self._as_optional_float(scorecard["max_score"])
        score_percentage = self._as_optional_float(scorecard["score_percentage"])
        score_breakdown = cast(list[dict[str, object]], scorecard["score_breakdown"])
        evidence_preview = cast(list[dict[str, object]], scorecard["evidence_preview"])
        warnings = cast(list[str], scorecard["warnings"])
        report_date = self._extract_report_date(normalized_text)

        if score_percentage is not None:
            score_percentage = max(0.0, min(score_percentage, 100.0))

        if ai_result and ai_result.provider_status == "completed":
            score_breakdown, overall_score, max_score, score_percentage = self._merge_ai_scores(
                rule_breakdown=score_breakdown,
                rule_overall=overall_score,
                rule_max=max_score,
                rule_pct=score_percentage,
                ai=ai_result,
            )
            if score_percentage is not None:
                score_percentage = max(0.0, min(score_percentage, 100.0))
            if ai_result.report_date and report_date is None:
                try:
                    report_date = datetime.strptime(ai_result.report_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
            if ai_result.issuer_name:
                pass  # rule-based issuer takes precedence if present
            if ai_result.outcome:
                pass  # merged below via _determine_outcome_status
            warnings.extend(ai_result.warnings)

        findings = self._extract_findings(
            page_texts=page_texts or ([normalized_text] if normalized_text else []),
            assurance_scheme=assurance_scheme,
            scheme_label=scheme_label,
            frameworks=frameworks,
            standards=standards,
            ai_result=ai_result,
        )
        positive_summary = self._build_category_summary(findings, {"positive_practice"})
        nonconformity_summary = self._build_category_summary(findings, {"nonconformity", "competence_gap", "finding"})
        improvement_summary = self._build_category_summary(findings, {"opportunity_for_improvement", "observation"})
        summary = self._build_summary(normalized_text, findings, frameworks, standards, scorecard, scheme_label)

        issuer = self._detect_issuer_name(normalized_text, scheme, assurance_scheme)
        if not issuer and ai_result and ai_result.issuer_name:
            issuer = ai_result.issuer_name

        outcome = self._determine_outcome_status(normalized_text, findings, score_percentage)
        if ai_result and ai_result.outcome and outcome == "review_required":
            outcome = ai_result.outcome
        if ai_result and ai_result.outcome and outcome != ai_result.outcome:
            warnings.append(f"Outcome divergence: rule-based='{outcome}' vs AI='{ai_result.outcome}'")

        # Section-sum cross-check
        if score_breakdown and overall_score is not None:
            section_sum = sum(float(str(s.get("score", 0))) for s in score_breakdown)
            if abs(section_sum - overall_score) > max(overall_score * 0.05, 1):
                warnings.append(
                    f"Section scores sum to {section_sum} but overall score is {overall_score} "
                    f"(delta {abs(section_sum - overall_score):.1f})"
                )

        # Scheme-specific validation (was previously dead code — now wired in)
        from src.domain.services.scheme_profiles import validate_against_scheme

        scheme_warnings = validate_against_scheme(
            scheme,
            overall_score,
            max_score,
            score_percentage,
            score_breakdown,
        )
        warnings.extend(scheme_warnings)

        return ExternalAuditAnalysisResult(
            summary=summary,
            findings=findings,
            mapped_frameworks=frameworks,
            mapped_standards=standards,
            detected_scheme=scheme,
            detected_scheme_confidence=scheme_confidence,
            scheme_version=self._detect_scheme_version(normalized_text, scheme),
            issuer_name=issuer,
            report_date=report_date,
            overall_score=overall_score,
            max_score=max_score,
            score_percentage=score_percentage,
            outcome_status=outcome,
            classification_basis={
                "assurance_scheme": assurance_scheme,
                "signals": scheme_signals,
                "mapped_frameworks": frameworks,
                "mapped_standards": standards,
            },
            score_breakdown=score_breakdown,
            evidence_preview=evidence_preview or self._build_evidence_preview_from_standards(standards),
            positive_summary=positive_summary,
            nonconformity_summary=nonconformity_summary,
            improvement_summary=improvement_summary,
            processing_warnings=warnings,
        )

    def _merge_ai_scores(
        self,
        *,
        rule_breakdown: list[dict[str, object]],
        rule_overall: float | None,
        rule_max: float | None,
        rule_pct: float | None,
        ai: AIAnalysisResult,
    ) -> tuple[list[dict[str, object]], float | None, float | None, float | None]:
        """Prefer AI-extracted scores when rule-based extraction is empty or suspect."""
        breakdown = rule_breakdown
        overall = rule_overall
        max_s = rule_max
        pct = rule_pct

        if ai.score_breakdown and (not rule_breakdown or len(ai.score_breakdown) > len(rule_breakdown)):
            breakdown = ai.score_breakdown

        if ai.overall_score is not None and ai.max_score is not None:
            if overall is None or (overall is not None and max_s is not None and overall > max_s):
                overall = ai.overall_score
                max_s = ai.max_score
            if pct is None or (pct is not None and pct > 100):
                pct = ai.score_percentage

        if pct is None and ai.score_percentage is not None:
            pct = ai.score_percentage

        if pct is not None:
            pct = max(0.0, min(pct, 100.0))

        return breakdown, overall, max_s, pct

    _NEGATION_WINDOW = re.compile(
        r"\b(?:no|not|without|absence of|zero|free from|did not find)\s+",
        re.IGNORECASE,
    )

    def _is_negated(self, text_lower: str, trigger: str) -> bool:
        """Check if a trigger phrase is preceded by a negation within ~40 chars."""
        idx = text_lower.find(trigger)
        if idx < 0:
            return False
        window = text_lower[max(0, idx - 40) : idx]
        return bool(self._NEGATION_WINDOW.search(window))

    def _extract_findings(
        self,
        *,
        page_texts: list[str],
        assurance_scheme: str | None,
        scheme_label: str,
        frameworks: list[dict[str, object]],
        standards: list[dict[str, object]],
        ai_result: AIAnalysisResult | None = None,
    ) -> list[DraftFindingCandidate]:
        findings: list[DraftFindingCandidate] = []
        for page_number, page_text in enumerate(page_texts, start=1):
            self._scan_page_for_findings(
                page_number=page_number,
                page_text=page_text,
                scheme_label=scheme_label,
                frameworks=frameworks,
                standards=standards,
                findings=findings,
            )

        if ai_result and ai_result.provider_status == "completed" and ai_result.findings:
            self._merge_ai_findings(
                findings=findings,
                ai_result=ai_result,
                scheme_label=scheme_label,
                frameworks=frameworks,
                standards=standards,
            )

        deduped = self._dedupe_findings(findings)
        return self._calibrate_confidence(deduped)

    def _scan_page_for_findings(
        self,
        *,
        page_number: int,
        page_text: str,
        scheme_label: str,
        frameworks: list[dict[str, object]],
        standards: list[dict[str, object]],
        findings: list[DraftFindingCandidate],
    ) -> None:
        """Extract rule-based findings from a single page."""
        compact = re.sub(r"\s+", " ", page_text).strip()
        lowered = compact.lower()
        if not compact:
            return
        negative_detected = False
        matched_triggers: set[str] = set()
        specific_trigger_matched = False
        for trigger, severity, finding_type, confidence in self._NONCONFORMITY_TRIGGERS:
            if trigger not in lowered or trigger in matched_triggers:
                continue
            if self._is_negated(lowered, trigger):
                continue
            snippet = self._snippet_around(compact, trigger)
            title = self._build_title(trigger, scheme_label)
            negative_detected = True
            specific_trigger_matched = True
            matched_triggers.add(trigger)
            findings.append(
                DraftFindingCandidate(
                    title=title,
                    description=snippet,
                    severity=severity,
                    finding_type=finding_type,
                    confidence_score=confidence,
                    competence_verdict="not_competent" if finding_type == "competence_gap" else None,
                    source_pages=[page_number],
                    evidence_snippets=[snippet],
                    mapped_frameworks=frameworks,
                    mapped_standards=standards,
                    suggested_action_title=f"Address imported audit issue: {title}",
                    suggested_action_description=snippet,
                    suggested_risk_title=f"Imported audit escalation: {title}",
                    provenance={
                        "page_number": page_number,
                        "trigger": trigger,
                        "analysis_method": "rule_based_import_review",
                    },
                )
            )
        if not specific_trigger_matched and self._GENERIC_FINDING_RE.search(compact):
            snippet = self._snippet_around(compact, "finding")
            title = self._build_title("finding", scheme_label)
            negative_detected = True
            findings.append(
                DraftFindingCandidate(
                    title=title,
                    description=snippet,
                    severity="medium",
                    finding_type="finding",
                    confidence_score=0.65,
                    competence_verdict=None,
                    source_pages=[page_number],
                    evidence_snippets=[snippet],
                    mapped_frameworks=frameworks,
                    mapped_standards=standards,
                    suggested_action_title=f"Address imported audit issue: {title}",
                    suggested_action_description=snippet,
                    suggested_risk_title=f"Imported audit escalation: {title}",
                    provenance={
                        "page_number": page_number,
                        "trigger": "finding (regex)",
                        "analysis_method": "rule_based_import_review",
                    },
                )
            )
        for trigger, severity, finding_type, confidence in self._IMPROVEMENT_TRIGGERS:
            if trigger not in lowered or trigger in matched_triggers:
                continue
            snippet = self._snippet_around(compact, trigger)
            title = self._build_title(trigger, scheme_label)
            matched_triggers.add(trigger)
            findings.append(
                DraftFindingCandidate(
                    title=title,
                    description=snippet,
                    severity=severity,
                    finding_type=finding_type,
                    confidence_score=confidence,
                    competence_verdict=None,
                    source_pages=[page_number],
                    evidence_snippets=[snippet],
                    mapped_frameworks=frameworks,
                    mapped_standards=standards,
                    suggested_action_title=f"Follow up imported audit improvement: {title}",
                    suggested_action_description=snippet,
                    suggested_risk_title=None,
                    provenance={
                        "page_number": page_number,
                        "trigger": trigger,
                        "analysis_method": "normalized_import_review",
                    },
                )
            )
        self._scan_positive_triggers(
            lowered=lowered,
            compact=compact,
            page_number=page_number,
            scheme_label=scheme_label,
            frameworks=frameworks,
            standards=standards,
            matched_triggers=matched_triggers,
            findings=findings,
        )

    def _scan_positive_triggers(
        self,
        *,
        lowered: str,
        compact: str,
        page_number: int,
        scheme_label: str,
        frameworks: list[dict[str, object]],
        standards: list[dict[str, object]],
        matched_triggers: set[str],
        findings: list[DraftFindingCandidate],
    ) -> None:
        """Extract positive-practice findings from a page with no negative triggers."""
        for trigger, severity, finding_type, confidence in self._POSITIVE_TRIGGERS:
            if trigger not in lowered or trigger in matched_triggers:
                continue
            if trigger == "competent" and "not competent" in lowered:
                continue
            if trigger == "compliant" and ("non-compliant" in lowered or "non compliant" in lowered):
                continue
            snippet = self._snippet_around(compact, trigger)
            title = self._build_title(trigger, scheme_label)
            boosted = self._boost_confidence(confidence, lowered)
            matched_triggers.add(trigger)
            findings.append(
                DraftFindingCandidate(
                    title=title,
                    description=snippet,
                    severity=severity,
                    finding_type=finding_type,
                    confidence_score=boosted,
                    competence_verdict="competent",
                    source_pages=[page_number],
                    evidence_snippets=[snippet],
                    mapped_frameworks=frameworks,
                    mapped_standards=standards,
                    suggested_action_title=None,
                    suggested_action_description=None,
                    suggested_risk_title=None,
                    provenance={
                        "page_number": page_number,
                        "trigger": trigger,
                        "analysis_method": "normalized_import_review",
                    },
                )
            )

    def _merge_ai_findings(
        self,
        *,
        findings: list[DraftFindingCandidate],
        ai_result: AIAnalysisResult,
        scheme_label: str,
        frameworks: list[dict[str, object]],
        standards: list[dict[str, object]],
    ) -> None:
        """Merge AI-detected findings with rule-based findings, upgrading corroborating matches."""
        from difflib import SequenceMatcher

        for ai_f in ai_result.findings:
            ai_title = str(ai_f.get("title", ""))
            ai_conf = float(str(ai_f.get("confidence", 0.60)))

            corroborated = self._try_corroborate(findings, ai_f, ai_title, ai_conf)
            if not corroborated:
                ai_evidence = ai_f.get("_evidence_snippets")
                if ai_evidence and isinstance(ai_evidence, list) and any(ai_evidence):
                    snippets = ai_evidence
                else:
                    desc_text = str(ai_f.get("description", ""))[:400]
                    snippets = [desc_text] if desc_text else []
                findings.append(
                    DraftFindingCandidate(
                        title=(
                            f"{scheme_label}: {ai_title}" if scheme_label and scheme_label not in ai_title else ai_title
                        ),
                        description=str(ai_f.get("description", "")),
                        severity=str(ai_f.get("severity", "medium")),
                        finding_type=str(ai_f.get("finding_type", "finding")),
                        confidence_score=ai_conf,
                        competence_verdict=("not_competent" if ai_f.get("finding_type") == "competence_gap" else None),
                        source_pages=[],
                        evidence_snippets=snippets,
                        mapped_frameworks=frameworks,
                        mapped_standards=standards,
                        provenance={
                            "analysis_method": "ai_structured",
                            "ai_provider": ai_f.get("_provider", "unknown"),
                            "ai_confidence": ai_conf,
                        },
                    )
                )

    @staticmethod
    def _try_corroborate(
        findings: list[DraftFindingCandidate],
        ai_f: dict[str, object],
        ai_title: str,
        ai_conf: float,
    ) -> bool:
        """Check if an AI finding corroborates an existing rule-based finding; upgrade if so."""
        from difflib import SequenceMatcher

        ai_lower = ai_title.lower()
        for existing in findings:
            existing_lower = existing.title.lower()
            if ai_lower in existing_lower or existing_lower in ai_lower:
                ratio = 1.0
            else:
                ratio = SequenceMatcher(None, existing_lower, ai_lower).ratio()
            if ratio >= 0.7:
                existing.confidence_score = max(existing.confidence_score, ai_conf)
                existing.provenance["analysis_method"] = "ai_confirmed"
                existing.provenance["ai_provider"] = ai_f.get("_provider", "unknown")
                existing.provenance["ai_confidence"] = ai_conf
                if ai_f.get("clause_reference"):
                    existing.provenance["clause_reference"] = ai_f["clause_reference"]
                return True
        return False

    def _calibrate_confidence(self, findings: list[DraftFindingCandidate]) -> list[DraftFindingCandidate]:
        """Post-processing calibration using multiplicative adjustments."""
        for f in findings:
            multiplier = 1.0
            method = f.provenance.get("analysis_method", "")

            if method == "ai_confirmed":
                multiplier *= 1.05
            if f.provenance.get("clause_reference"):
                multiplier *= 1.05

            consensus_status = f.provenance.get("_consensus")
            if consensus_status == "single_source" and method == "ai_structured":
                multiplier *= 0.95

            f.confidence_score = min(round(f.confidence_score * multiplier, 2), 0.99)
        return findings

    def _build_summary(
        self,
        text: str,
        findings: list[DraftFindingCandidate],
        frameworks: list[dict[str, object]],
        standards: list[dict[str, object]],
        scorecard: dict[str, object],
        scheme_label: str,
    ) -> str:
        parts = []
        parts.append(f"Detected scheme: {scheme_label}.")
        if findings:
            parts.append(f"{len(findings)} draft finding(s) extracted for reviewer confirmation.")
        else:
            parts.append("No deterministic findings were extracted; manual review is still required.")
        if frameworks:
            parts.append(f"Framework matches: {', '.join(str(item['framework']) for item in frameworks)}.")
        if standards:
            parts.append(
                f"ISO references detected: {', '.join(sorted({str(item['standard']) for item in standards}))}."
            )
        score_percentage = scorecard.get("score_percentage")
        if score_percentage is not None:
            parts.append(f"Normalized score: {self._as_float(score_percentage):.1f}%.")
        if text:
            parts.append(f"Source text length: {len(text.split())} words.")
        return " ".join(parts)

    def _boost_confidence(self, base: float, page_text_lower: str) -> float:
        """Boost confidence when corroborating keywords appear on the same page."""
        hits = sum(1 for kw in self._CONFIDENCE_BOOSTERS if kw in page_text_lower)
        boost = min(hits * 0.02, 0.10)
        return min(round(base + boost, 2), 0.99)

    def _snippet_around(self, text: str, trigger: str) -> str:
        lowered = text.lower()
        idx = lowered.find(trigger.lower())
        if idx < 0:
            return text[:400]
        start = max(0, idx - 140)
        end = min(len(text), idx + 260)
        # Extend to nearest sentence boundary to avoid mid-word cuts
        while start > 0 and text[start - 1] not in ".\n|":
            start -= 1
            if idx - start > 200:
                break
        while end < len(text) and text[end - 1] not in ".\n|":
            end += 1
            if end - idx > 350:
                break
        return text[start:end].strip()

    def _build_title(self, trigger: str, scheme_label: str) -> str:
        human_trigger = trigger.replace("-", " ").title()
        return f"{scheme_label}: {human_trigger}"

    def _dedupe_findings(self, findings: list[DraftFindingCandidate]) -> list[DraftFindingCandidate]:
        seen: set[tuple[str, str]] = set()
        deduped: list[DraftFindingCandidate] = []
        for finding in findings:
            key = (finding.title.lower(), finding.description[:140].lower())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(finding)
        return deduped

    def _detect_scheme(self, text: str, assurance_scheme: str | None) -> dict[str, object]:
        lowered = text.lower()
        scheme = (assurance_scheme or "").lower()
        signals: list[str] = []

        if "planet mark" in lowered or "planet mark" in scheme:
            signals.append("planet_mark_keyword")
            return {
                "scheme": "planet_mark",
                "label": "Planet Mark",
                "confidence": 0.97 if "planet mark" in scheme else 0.92,
                "signals": signals,
            }

        if any(token in lowered for token in ("achilles", "uvdb", "verify b2", "verify b1")) or any(
            token in scheme for token in ("achilles", "uvdb")
        ):
            signals.append("achilles_uvdb_keyword")
            return {
                "scheme": "achilles_uvdb",
                "label": "Achilles / UVDB",
                "confidence": 0.97 if any(token in scheme for token in ("achilles", "uvdb")) else 0.9,
                "signals": signals,
            }

        iso_hits = [
            label for label, pattern in self._ISO_STANDARD_PATTERNS if re.search(pattern, lowered, re.IGNORECASE)
        ]
        if iso_hits or "iso" in scheme:
            signals.extend(iso_hits or ["assurance_scheme_iso"])
            return {
                "scheme": "iso",
                "label": "ISO Audit",
                "confidence": 0.88 if iso_hits else 0.75,
                "signals": signals,
            }

        if any(token in lowered for token in ("customer audit", "client audit", "supplier audit", "third-party audit")):
            signals.append("customer_or_third_party_keyword")
            return {
                "scheme": "customer_other",
                "label": "Customer / Third-Party Audit",
                "confidence": 0.72,
                "signals": signals,
            }

        return {
            "scheme": "customer_other",
            "label": (assurance_scheme or "External Audit").strip() or "External Audit",
            "confidence": 0.45,
            "signals": ["fallback_external_audit"],
        }

    def _detect_frameworks(
        self,
        text: str,
        assurance_scheme: str | None,
        scheme: str,
    ) -> list[dict[str, object]]:
        mappings = self.achilles_mapping_service.map_text(text, assurance_scheme)
        if scheme == "planet_mark":
            mappings.append({"framework": "Planet Mark", "confidence": 0.95, "basis": "scheme_or_content_match"})
        elif scheme == "customer_other":
            mappings.append(
                {
                    "framework": "Customer / Third-Party Audit",
                    "confidence": 0.6,
                    "basis": "generic_external_audit",
                }
            )
        return self._dedupe_dicts(mappings, key_fields=("framework", "basis"))

    def _build_standard_mappings(self, text: str) -> list[dict[str, object]]:
        standards = self.iso_mapping_service.map_text(text)
        clause_matches = iso_compliance_service.auto_tag_content(text, min_confidence=0.35)
        for match in clause_matches:
            standards.append(
                {
                    "standard": self._humanize_standard(str(match["standard"])),
                    "confidence": float(match["confidence"]) / 100.0,
                    "basis": "clause_auto_tag",
                    "clause_id": match["clause_id"],
                    "clause_number": match["clause_number"],
                    "title": match["title"],
                }
            )
        return self._dedupe_dicts(standards, key_fields=("standard", "clause_id", "basis"))

    def _extract_scorecard(self, text: str, page_texts: list[str], scheme: str) -> dict[str, object]:
        score_breakdown = self._extract_score_breakdown(text)
        overall_score: float | None = None
        max_score: float | None = None
        score_percentage: float | None = None
        warnings: list[str] = []

        ratio_match = re.search(
            r"(?i)(overall|total|final|audit)\s+(score|rating|result)[^0-9]{0,20}(\d{1,3}(?:\.\d+)?)\s*(?:/|out of)\s*(\d{1,3}(?:\.\d+)?)",
            text,
        )
        if ratio_match:
            candidate_score = float(ratio_match.group(3))
            candidate_max = float(ratio_match.group(4))
            if candidate_max and candidate_score <= candidate_max:
                overall_score = candidate_score
                max_score = candidate_max
                score_percentage = round((overall_score / max_score) * 100, 1)

        if score_percentage is None:
            pct_match = re.search(
                r"(?i)(overall|total|final|audit)\s+(score|rating|result|compliance)[^0-9]{0,20}(\d{1,3}(?:\.\d+)?)\s*%",
                text,
            )
            if pct_match:
                score_percentage = float(pct_match.group(3))

        if score_percentage is None:
            generic_pct = re.search(
                r"(?i)\b(score|rating|result|compliance)\b[^0-9]{0,10}(\d{1,3}(?:\.\d+)?)\s*%", text
            )
            if generic_pct:
                score_percentage = float(generic_pct.group(2))

        if score_percentage is None and score_breakdown:
            total_score = sum(
                self._as_float(item["score"]) for item in score_breakdown if item.get("score") is not None
            )
            total_max = sum(
                self._as_float(item["max_score"]) for item in score_breakdown if item.get("max_score") is not None
            )
            if total_max > 0:
                overall_score = total_score
                max_score = total_max
                score_percentage = round((total_score / total_max) * 100, 1)

        evidence_preview = iso_compliance_service.auto_tag_content(text, min_confidence=0.45)[:8]
        if not evidence_preview:
            warnings.append("No clause-level ISO evidence could be auto-tagged from the imported text.")
        if score_percentage is None:
            warnings.append("No explicit overall score was extracted from the imported report.")
        if scheme == "planet_mark":
            warnings.append(
                "Planet Mark imports may require reviewer confirmation of reduction and data-quality scores."
            )

        return {
            "overall_score": overall_score,
            "max_score": max_score,
            "score_percentage": score_percentage,
            "score_breakdown": score_breakdown,
            "evidence_preview": evidence_preview,
            "warnings": warnings,
        }

    def _build_evidence_preview_from_standards(self, standards: list[dict[str, object]]) -> list[dict[str, object]]:
        preview: list[dict[str, object]] = []
        for mapping in standards:
            clause_id = mapping.get("clause_id")
            clause_number = mapping.get("clause_number")
            standard = mapping.get("standard")
            if not clause_id and not clause_number and not standard:
                continue
            preview.append(
                {
                    "standard": standard,
                    "clause_id": clause_id,
                    "clause_number": clause_number,
                    "title": mapping.get("title"),
                    "confidence": mapping.get("confidence"),
                }
            )
        return self._dedupe_dicts(preview[:8], key_fields=("standard", "clause_id", "clause_number", "title"))

    @staticmethod
    def _looks_like_date(a: float, b: float, trailing: str, *, has_label_context: bool = False) -> bool:
        """Return True when a/b looks like DD/MM, MM/DD, or is followed by a year.

        When *has_label_context* is True the match came from a line with a
        recognized section-label pattern, so we only reject it if there is an
        explicit trailing year indicator — raw numeric-range heuristics are
        skipped because they produce false positives on valid small-scale scores
        like 3/5, 4/5, 1/1, 7/10.
        """
        if trailing and re.match(r"\s*/\s*\d{4}\b", trailing):
            return True
        if trailing and re.match(r"\s*/\s*\d{2}\b", trailing):
            return True
        if has_label_context:
            return False
        ia, ib = int(a), int(b)
        if a != ia or b != ib:
            return False
        if 1 <= ia <= 31 and 1 <= ib <= 12:
            return True
        if 1 <= ib <= 31 and 1 <= ia <= 12:
            return True
        return False

    def _extract_score_breakdown(self, text: str) -> list[dict[str, object]]:
        breakdown: list[dict[str, object]] = []
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if len(line) < 8 or len(line) > 160:
                continue
            if line.lower().startswith(("page ", "sheet ")):
                continue
            match = re.search(
                r"(?P<label>[A-Za-z][A-Za-z0-9/&().,'\-:# ]{3,80})[:\s-]+(?P<score>\d{1,3}(?:\.\d+)?)\s*/\s*(?P<max>\d{1,3}(?:\.\d+)?)",
                line,
            )
            if not match:
                continue
            label = match.group("label").strip(" :-")
            if label.lower() in {"overall", "total", "final score", "audit score"}:
                continue
            score = float(match.group("score"))
            max_score = float(match.group("max"))
            if max_score <= 0:
                continue

            trailing = line[match.end() :]
            if self._looks_like_date(score, max_score, trailing, has_label_context=len(label) >= 4):
                continue

            if score > max_score:
                continue

            pct = round((score / max_score) * 100, 1)
            if pct > 100.0:
                continue

            breakdown.append(
                {
                    "label": label,
                    "score": score,
                    "max_score": max_score,
                    "percentage": pct,
                }
            )
        if len(breakdown) > 30:
            breakdown = breakdown[:30]
        return self._dedupe_dicts(breakdown, key_fields=("label",))

    def _extract_report_date(self, text: str) -> datetime | None:
        label_match = self._CONTEXTUAL_DATE_LABELS.search(text)
        if label_match:
            region = text[label_match.end() : label_match.end() + 80]
            parsed = self._parse_date_from_region(region)
            if parsed:
                return parsed

        for pattern in self._DATE_PATTERNS:
            match = re.search(pattern, text)
            if not match:
                continue
            raw = match.group(1)
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        return None

    def _parse_date_from_region(self, region: str) -> datetime | None:
        """Parse a date from a small text region near a label."""
        for pattern in self._DATE_PATTERNS:
            match = re.search(pattern, region)
            if match:
                raw = match.group(1)
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                    try:
                        return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
        long_match = self._LONG_DATE_RE.search(region)
        if long_match:
            try:
                return datetime.strptime(
                    f"{long_match.group(1)} {long_match.group(2)} {long_match.group(3)}",
                    "%d %B %Y",
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        alt_match = self._LONG_DATE_ALT_RE.search(region)
        if alt_match:
            try:
                return datetime.strptime(
                    f"{alt_match.group(2)} {alt_match.group(1)} {alt_match.group(3)}",
                    "%d %B %Y",
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return None

    def _detect_scheme_version(self, text: str, scheme: str) -> str | None:
        if scheme == "achilles_uvdb":
            match = re.search(r"(?i)\b(B1|B2|C2|V\d+(?:\.\d+)?)\b", text)
            if match:
                return match.group(1).upper()
        if scheme == "iso":
            standards = re.findall(r"(?i)\bISO(?:\/IEC)?\s*(9001|14001|27001|45001)\s*:?\s*(2015|2018|2022)?\b", text)
            if standards:
                return ", ".join(
                    sorted({f"ISO {standard}{f':{year}' if year else ''}" for standard, year in standards})
                )
        if scheme == "planet_mark":
            match = re.search(r"(?i)planet mark[^0-9]*(\d{4})", text)
            if match:
                return match.group(1)
        return None

    def _detect_issuer_name(self, text: str, scheme: str, assurance_scheme: str | None) -> str | None:
        if scheme == "planet_mark":
            return "Planet Mark"
        if scheme == "achilles_uvdb":
            return "Achilles"
        if scheme == "iso":
            issuer_match = re.search(r"(?i)\b(BSI|SGS|LRQA|Bureau Veritas|DNV|NQA|UKAS)\b", text)
            if issuer_match:
                return issuer_match.group(1)
        if assurance_scheme:
            return assurance_scheme.strip()
        return None

    _NEGATION_BEFORE_OUTCOME = re.compile(
        r"\b(?:no|not|without|absence of|zero|free from|did not find|no evidence of)\b",
        re.IGNORECASE,
    )

    def _outcome_is_negated(self, text_lower: str, match: re.Match) -> bool:  # type: ignore[type-arg]
        """Check whether an outcome-pattern match is preceded by a negation."""
        start = match.start()
        window = text_lower[max(0, start - 50) : start]
        return bool(self._NEGATION_BEFORE_OUTCOME.search(window))

    def _determine_outcome_status(
        self,
        text: str,
        findings: list[DraftFindingCandidate],
        score_percentage: float | None,
    ) -> str:
        lowered = text.lower()

        non_negated_severe = any(
            f.finding_type in {"nonconformity", "competence_gap"}
            and f.severity in {"high", "critical"}
            and f.provenance.get("analysis_method") != "normalized_import_review"
            for f in findings
        )
        if non_negated_severe:
            return "fail"

        if any(f.finding_type in {"opportunity_for_improvement", "observation"} for f in findings):
            if score_percentage is None or score_percentage < 85:
                return "review_required"

        for outcome, pattern in self._OUTCOME_PATTERNS:
            match = re.search(pattern, lowered, re.IGNORECASE)
            if not match:
                continue
            if outcome == "fail" and self._outcome_is_negated(lowered, match):
                continue
            return outcome

        if score_percentage is not None:
            if score_percentage >= 85:
                return "pass"
            if score_percentage >= 70:
                return "review_required"
            return "fail"
        return "review_required"

    def _build_category_summary(
        self,
        findings: list[DraftFindingCandidate],
        finding_types: set[str],
    ) -> list[dict[str, object]]:
        summary: list[dict[str, object]] = []
        for finding in findings:
            if finding.finding_type not in finding_types:
                continue
            summary.append(
                {
                    "title": finding.title,
                    "severity": finding.severity,
                    "finding_type": finding.finding_type,
                    "confidence_score": finding.confidence_score,
                    "source_pages": finding.source_pages,
                }
            )
        return summary[:10]

    def _humanize_standard(self, standard: str) -> str:
        normalized = standard.lower()
        mapping = {
            "iso9001": "ISO 9001",
            "iso14001": "ISO 14001",
            "iso45001": "ISO 45001",
            "iso27001": "ISO 27001",
        }
        return mapping.get(normalized, standard.upper())

    def _dedupe_dicts(
        self,
        values: list[dict[str, object]],
        *,
        key_fields: tuple[str, ...],
    ) -> list[dict[str, object]]:
        seen: set[tuple[object, ...]] = set()
        deduped: list[dict[str, object]] = []
        for item in values:
            key = tuple(item.get(field) for field in key_fields)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _as_str(self, value: object) -> str:
        return value if isinstance(value, str) else str(value)

    def _as_float(self, value: object) -> float:
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        return float(str(value))

    def _as_optional_float(self, value: object) -> float | None:
        if value is None:
            return None
        return self._as_float(value)
