"""Turn extracted external audit text into reviewable draft findings."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.domain.services.achilles_mapping_service import AchillesMappingService
from src.domain.services.iso_cross_mapping_service import ISOCrossMappingService


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


class ExternalAuditAnalysisService:
    """Rule-based first-pass analysis with provenance and confidence."""

    _TRIGGER_KEYWORDS: tuple[tuple[str, str, str, float], ...] = (
        ("major non-conformance", "high", "nonconformity", 0.9),
        ("major nonconformance", "high", "nonconformity", 0.9),
        ("minor non-conformance", "medium", "nonconformity", 0.8),
        ("minor nonconformance", "medium", "nonconformity", 0.8),
        ("observation", "low", "observation", 0.65),
        ("not competent", "high", "competence_gap", 0.85),
        ("non-compliant", "high", "nonconformity", 0.8),
        ("non compliant", "high", "nonconformity", 0.8),
        ("finding", "medium", "finding", 0.55),
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
    ) -> ExternalAuditAnalysisResult:
        normalized_text = extracted_text.strip()
        frameworks = self.achilles_mapping_service.map_text(normalized_text, assurance_scheme)
        standards = self.iso_mapping_service.map_text(normalized_text)
        findings = self._extract_findings(
            page_texts=page_texts or ([normalized_text] if normalized_text else []),
            assurance_scheme=assurance_scheme,
            frameworks=frameworks,
            standards=standards,
        )
        summary = self._build_summary(normalized_text, findings, frameworks, standards)
        return ExternalAuditAnalysisResult(
            summary=summary,
            findings=findings,
            mapped_frameworks=frameworks,
            mapped_standards=standards,
        )

    def _extract_findings(
        self,
        *,
        page_texts: list[str],
        assurance_scheme: str | None,
        frameworks: list[dict[str, object]],
        standards: list[dict[str, object]],
    ) -> list[DraftFindingCandidate]:
        findings: list[DraftFindingCandidate] = []
        for page_number, page_text in enumerate(page_texts, start=1):
            compact = re.sub(r"\s+", " ", page_text).strip()
            lowered = compact.lower()
            if not compact:
                continue
            for trigger, severity, finding_type, confidence in self._TRIGGER_KEYWORDS:
                if trigger not in lowered:
                    continue
                snippet = self._snippet_around(compact, trigger)
                title = self._build_title(trigger, assurance_scheme)
                findings.append(
                    DraftFindingCandidate(
                        title=title,
                        description=snippet,
                        severity=severity,
                        finding_type=finding_type,
                        confidence_score=confidence,
                        competence_verdict="not_competent" if severity in {"high", "medium"} else None,
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
                break
        return self._dedupe_findings(findings)

    def _build_summary(
        self,
        text: str,
        findings: list[DraftFindingCandidate],
        frameworks: list[dict[str, object]],
        standards: list[dict[str, object]],
    ) -> str:
        parts = []
        if findings:
            parts.append(f"{len(findings)} draft finding(s) extracted for reviewer confirmation.")
        else:
            parts.append("No deterministic findings were extracted; manual review is still required.")
        if frameworks:
            parts.append(f"Framework matches: {', '.join(str(item['framework']) for item in frameworks)}.")
        if standards:
            parts.append(f"ISO references detected: {', '.join(str(item['standard']) for item in standards)}.")
        if text:
            parts.append(f"Source text length: {len(text.split())} words.")
        return " ".join(parts)

    def _snippet_around(self, text: str, trigger: str) -> str:
        lowered = text.lower()
        idx = lowered.find(trigger.lower())
        if idx < 0:
            return text[:400]
        start = max(0, idx - 140)
        end = min(len(text), idx + 260)
        return text[start:end].strip()

    def _build_title(self, trigger: str, assurance_scheme: str | None) -> str:
        scheme_label = (assurance_scheme or "External Audit").strip() or "External Audit"
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
