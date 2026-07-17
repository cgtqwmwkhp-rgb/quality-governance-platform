"""Planet Mark Measurement Report / Certificate OCR → year-reading candidates.

Wave 1 (path11/pm-ocr-year-readings). Text extraction reuses the same OCR spine
as external audits (``ExternalAuditOcrService`` → document_extraction_service +
MistralOCRService). Azure DI is consulted only when explicitly enabled; otherwise
it reports honest not_configured / stub_not_enabled without fabricating numbers.

Honesty contract:
  * Fields are populated only from keyword-anchored matches with confidence.
  * Low/no confidence → value=None + warning ("could not extract").
  * MS XLSX ingest remains SSOT for totals unless force_overwrite_totals=True.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional, Protocol

from src.domain.services.external_audit_ocr_service import ExternalAuditOcrService

logger = logging.getLogger(__name__)


class _AzureDiEnrichmentClient(Protocol):
    """Injected adapter — domain must not import infrastructure clients."""

    @property
    def is_configured(self) -> bool: ...

    async def analyze_document(self, content: bytes, filename: str, content_type: str) -> Any: ...


PROVENANCE_MEASUREMENT_REPORT = "ocr_measurement_report"
PROVENANCE_CERTIFICATE = "ocr_certificate"

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_NONE = "none"

DOCUMENT_KIND_MEASUREMENT_REPORT = "measurement_report"
DOCUMENT_KIND_CERTIFICATE = "certificate"
VALID_DOCUMENT_KINDS = {DOCUMENT_KIND_MEASUREMENT_REPORT, DOCUMENT_KIND_CERTIFICATE}

_NUM_RE = re.compile(r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)")
_CERT_NUMBER_RE = re.compile(
    r"certificate\s*(?:no\.?|number|ref(?:erence)?)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-/]{2,24})",
    re.IGNORECASE,
)
_YEAR_LABEL_RE = re.compile(r"\bYE\s?-?\s?(20\d{2})\b", re.IGNORECASE)
_DATE_RANGE_RE = re.compile(r"(\d{1,2}\s+[A-Za-z]+\s+20\d{2})\s*(?:to|-|–|until)\s*(\d{1,2}\s+[A-Za-z]+\s+20\d{2})")

_STATUS_PHRASES: list[tuple[str, list[str]]] = [
    ("certified", ["planet mark certified", "certified organisation", "has been certified", "successfully certified"]),
    ("provisional", ["provisionally certified", "provisional certification"]),
    ("in_progress", ["certification in progress", "assessment in progress", "pending certification"]),
    ("not_certified", ["not yet certified", "not certified"]),
]

APPLY_ACTION_APPLY = "apply"
APPLY_ACTION_SKIP_NOT_EXTRACTED = "skip_not_extracted"
APPLY_ACTION_SKIP_XLSX_SSOT = "skip_xlsx_ssot"
_XLSX_PROTECTED_FIELDS = {"total_co2e_tonnes", "co2e_per_fte", "average_fte"}


def _normalize_unit_text(text: str) -> str:
    normalized = text.replace("CO₂e", "CO2e").replace("co₂e", "co2e").replace("CO₂", "CO2").replace("co₂", "co2")
    return re.sub(r"t\s*CO2e", "tCO2e", normalized, flags=re.IGNORECASE)


@dataclass(frozen=True)
class ExtractedField:
    value: Optional[str] = None
    confidence: str = CONFIDENCE_NONE
    raw_snippet: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def is_extracted(self) -> bool:
        return self.value is not None and self.confidence != CONFIDENCE_NONE


@dataclass
class PlanetMarkOcrExtraction:
    source_filename: str
    document_kind: str
    extraction_method: str
    total_co2e_tonnes: ExtractedField = field(default_factory=ExtractedField)
    co2e_per_fte: ExtractedField = field(default_factory=ExtractedField)
    average_fte: ExtractedField = field(default_factory=ExtractedField)
    certificate_number: ExtractedField = field(default_factory=ExtractedField)
    reporting_period_label: ExtractedField = field(default_factory=ExtractedField)
    certification_status_cue: ExtractedField = field(default_factory=ExtractedField)
    warnings: list[str] = field(default_factory=list)
    text_excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_filename": self.source_filename,
            "document_kind": self.document_kind,
            "extraction_method": self.extraction_method,
            "total_co2e_tonnes": self.total_co2e_tonnes.to_dict(),
            "co2e_per_fte": self.co2e_per_fte.to_dict(),
            "average_fte": self.average_fte.to_dict(),
            "certificate_number": self.certificate_number.to_dict(),
            "reporting_period_label": self.reporting_period_label.to_dict(),
            "certification_status_cue": self.certification_status_cue.to_dict(),
            "warnings": self.warnings,
            "text_excerpt": self.text_excerpt,
        }

    @property
    def has_any_extraction(self) -> bool:
        return any(
            f.is_extracted
            for f in (
                self.total_co2e_tonnes,
                self.co2e_per_fte,
                self.average_fte,
                self.certificate_number,
                self.reporting_period_label,
                self.certification_status_cue,
            )
        )


def _extract_numeric_field(
    text: str,
    *,
    include_keywords: list[str],
    exclude_keywords: list[str],
    unit_keywords: list[str],
) -> tuple[Optional[float], Optional[str], bool]:
    normalized_text = _normalize_unit_text(text)
    candidates: list[tuple[float, str]] = []
    for raw_line in normalized_text.splitlines():
        lower = raw_line.lower()
        if not any(k in lower for k in include_keywords):
            continue
        if any(k in lower for k in exclude_keywords):
            continue
        if unit_keywords and not any(k in lower for k in unit_keywords):
            continue
        match = _NUM_RE.search(raw_line)
        if not match:
            continue
        try:
            value = float(match.group(1).replace(",", ""))
        except ValueError:
            continue
        candidates.append((value, raw_line.strip()))

    if not candidates:
        return None, None, False
    first_value = candidates[0][0]
    tolerance = max(0.5, abs(first_value) * 0.02)
    if any(abs(v - first_value) > tolerance for v, _ in candidates):
        return None, None, True
    return first_value, candidates[0][1], False


def _format_number(value: float) -> str:
    return f"{round(value, 3):g}"


def _extract_total_co2e(text: str) -> tuple[ExtractedField, Optional[str]]:
    value, snippet, ambiguous = _extract_numeric_field(
        text,
        include_keywords=["total"],
        exclude_keywords=["per employee", "per fte", "/fte", "per staff", "per head"],
        unit_keywords=["tco2e", "co2e"],
    )
    if ambiguous:
        return ExtractedField(), "Multiple differing total tCO2e figures were found — enter the total manually."
    if value is None:
        return ExtractedField(), "Could not extract a total tCO2e figure from this document."
    return ExtractedField(_format_number(value), CONFIDENCE_HIGH, snippet), None


def _extract_co2e_per_fte(text: str) -> tuple[ExtractedField, Optional[str]]:
    value, snippet, ambiguous = _extract_numeric_field(
        text,
        include_keywords=["per employee", "per fte", "/fte", "per staff", "per head"],
        exclude_keywords=[],
        unit_keywords=[],
    )
    if ambiguous:
        return ExtractedField(), "Multiple differing tCO2e/FTE figures were found — enter the value manually."
    if value is None:
        return ExtractedField(), "Could not extract a tCO2e per FTE figure from this document."
    return ExtractedField(_format_number(value), CONFIDENCE_HIGH, snippet), None


def _extract_average_fte(text: str) -> tuple[ExtractedField, Optional[str]]:
    value, snippet, ambiguous = _extract_numeric_field(
        text,
        include_keywords=["no. employees", "number of employees", "average fte", "employees:", "headcount"],
        exclude_keywords=["per employee", "per fte", "/fte"],
        unit_keywords=[],
    )
    if ambiguous:
        return ExtractedField(), "Multiple differing employee/FTE counts were found — enter average FTE manually."
    if value is None:
        return ExtractedField(), None
    return ExtractedField(_format_number(value), CONFIDENCE_HIGH, snippet), None


def _extract_certificate_number(text: str) -> tuple[ExtractedField, Optional[str]]:
    match = _CERT_NUMBER_RE.search(text)
    if not match:
        return ExtractedField(), None
    return ExtractedField(match.group(1).strip().rstrip(".,"), CONFIDENCE_HIGH, match.group(0).strip()), None


def _extract_reporting_period(text: str) -> tuple[ExtractedField, Optional[str]]:
    year_match = _YEAR_LABEL_RE.search(text)
    if year_match:
        return ExtractedField(f"YE{year_match.group(1)}", CONFIDENCE_HIGH, year_match.group(0).strip()), None
    date_match = _DATE_RANGE_RE.search(text)
    if date_match:
        label = f"{date_match.group(1)} to {date_match.group(2)}"
        return ExtractedField(label, CONFIDENCE_MEDIUM, date_match.group(0).strip()), None
    return ExtractedField(), "Could not identify a reporting period (YE label or date range) in this document."


def _extract_certification_status(text: str) -> tuple[ExtractedField, Optional[str]]:
    lower = text.lower()
    for normalized_status, phrases in _STATUS_PHRASES:
        for phrase in phrases:
            idx = lower.find(phrase)
            if idx != -1:
                snippet = text[max(0, idx - 20) : idx + len(phrase) + 20].strip()
                return ExtractedField(normalized_status, CONFIDENCE_HIGH, snippet), None
    return ExtractedField(), "No certification status statement was found in this document."


def parse_fields_from_text(text: str) -> tuple[dict[str, ExtractedField], list[str]]:
    """Pure field parsing from already-extracted text (unit-testable)."""
    warnings: list[str] = []
    total_field, total_warn = _extract_total_co2e(text)
    per_fte_field, per_fte_warn = _extract_co2e_per_fte(text)
    fte_field, fte_warn = _extract_average_fte(text)
    cert_field, cert_warn = _extract_certificate_number(text)
    period_field, period_warn = _extract_reporting_period(text)
    status_field, status_warn = _extract_certification_status(text)
    for warn in (total_warn, per_fte_warn, fte_warn, cert_warn, period_warn, status_warn):
        if warn:
            warnings.append(warn)
    return {
        "total_co2e_tonnes": total_field,
        "co2e_per_fte": per_fte_field,
        "average_fte": fte_field,
        "certificate_number": cert_field,
        "reporting_period_label": period_field,
        "certification_status_cue": status_field,
    }, warnings


class PlanetMarkPdfOcrService:
    """Extract Planet Mark year-reading candidates via the shared OCR spine."""

    def __init__(
        self,
        ocr_pipeline: ExternalAuditOcrService | None = None,
        azure_client: _AzureDiEnrichmentClient | None = None,
    ) -> None:
        self._ocr = ocr_pipeline or ExternalAuditOcrService()
        # Azure DI is optional enrichment; API layer injects the infra client.
        self._azure = azure_client

    async def extract(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str,
        document_kind: str,
    ) -> PlanetMarkOcrExtraction:
        if document_kind not in VALID_DOCUMENT_KINDS:
            document_kind = DOCUMENT_KIND_MEASUREMENT_REPORT

        warnings: list[str] = []
        spine = await self._ocr.extract(raw=content, filename=filename, content_type=content_type)
        text = spine.text or ""
        extraction_method = spine.extraction_method or "none"

        if spine.note:
            warnings.append(spine.note)
        if spine.hard_ocr_failure:
            warnings.append("OCR provider failed and no native text was available.")
        if spine.ocr_provider_status == "not_configured" and not text.strip():
            warnings.append("OCR provider is not configured; native PDF text was empty.")

        # Optional Azure DI enrichment — never fabricates; honest status only.
        if self._azure is not None and self._azure.is_configured:
            try:
                azure_result = await self._azure.analyze_document(content, filename, content_type)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Azure DI call failed for %s: %s", filename, type(exc).__name__)
                azure_result = None
            if azure_result and azure_result.provider_status == "completed" and azure_result.text.strip():
                text = f"{text}\n\n{azure_result.text}" if text.strip() else azure_result.text
                extraction_method = f"{extraction_method}+azure_di"
            elif azure_result and azure_result.provider_status == "stub_not_enabled":
                warnings.append(
                    azure_result.note or "Azure Document Intelligence is configured but not enabled (E4 DPO gate)."
                )
            elif azure_result and azure_result.provider_status not in ("not_configured",):
                warnings.append(azure_result.note or "Azure Document Intelligence did not return usable text.")

        if not text.strip():
            return PlanetMarkOcrExtraction(
                source_filename=filename,
                document_kind=document_kind,
                extraction_method=extraction_method,
                warnings=warnings or ["Could not extract any text from this document."],
            )

        fields, field_warnings = parse_fields_from_text(text)
        warnings.extend(field_warnings)
        return PlanetMarkOcrExtraction(
            source_filename=filename,
            document_kind=document_kind,
            extraction_method=extraction_method,
            total_co2e_tonnes=fields["total_co2e_tonnes"],
            co2e_per_fte=fields["co2e_per_fte"],
            average_fte=fields["average_fte"],
            certificate_number=fields["certificate_number"],
            reporting_period_label=fields["reporting_period_label"],
            certification_status_cue=fields["certification_status_cue"],
            warnings=warnings,
            text_excerpt=text[:600],
        )


@dataclass(frozen=True)
class ApplyFieldPlan:
    field_name: str
    action: str
    value: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field_name, "action": self.action, "value": self.value, "reason": self.reason}


def build_apply_plan(
    extraction: PlanetMarkOcrExtraction,
    *,
    xlsx_ingested: bool,
    force_overwrite_totals: bool = False,
    requested_fields: Optional[set[str]] = None,
) -> list[ApplyFieldPlan]:
    candidate_fields: dict[str, ExtractedField] = {
        "total_co2e_tonnes": extraction.total_co2e_tonnes,
        "co2e_per_fte": extraction.co2e_per_fte,
        "average_fte": extraction.average_fte,
        "certificate_number": extraction.certificate_number,
    }
    plans: list[ApplyFieldPlan] = []
    for name, extracted in candidate_fields.items():
        if requested_fields is not None and name not in requested_fields:
            continue
        if not extracted.is_extracted:
            plans.append(
                ApplyFieldPlan(
                    name,
                    APPLY_ACTION_SKIP_NOT_EXTRACTED,
                    None,
                    "Could not extract this field with confidence — enter it manually.",
                )
            )
            continue
        if name in _XLSX_PROTECTED_FIELDS and xlsx_ingested and not force_overwrite_totals:
            plans.append(
                ApplyFieldPlan(
                    name,
                    APPLY_ACTION_SKIP_XLSX_SSOT,
                    extracted.value,
                    "MS XLSX ingest is the source of truth for this reporting year's totals. "
                    "Re-apply with force_overwrite_totals=true to override.",
                )
            )
            continue
        plans.append(ApplyFieldPlan(name, APPLY_ACTION_APPLY, extracted.value, None))
    return plans


__all__ = [
    "PROVENANCE_MEASUREMENT_REPORT",
    "PROVENANCE_CERTIFICATE",
    "CONFIDENCE_HIGH",
    "CONFIDENCE_MEDIUM",
    "CONFIDENCE_NONE",
    "DOCUMENT_KIND_MEASUREMENT_REPORT",
    "DOCUMENT_KIND_CERTIFICATE",
    "VALID_DOCUMENT_KINDS",
    "ExtractedField",
    "PlanetMarkOcrExtraction",
    "PlanetMarkPdfOcrService",
    "ApplyFieldPlan",
    "APPLY_ACTION_APPLY",
    "APPLY_ACTION_SKIP_NOT_EXTRACTED",
    "APPLY_ACTION_SKIP_XLSX_SSOT",
    "build_apply_plan",
    "parse_fields_from_text",
]
