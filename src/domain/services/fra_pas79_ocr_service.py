"""PAS 79-style Fire Risk Assessment OCR field extraction.

Propose-only parser: never mutates schedule data. Human confirm is required
before ``next_due_date`` moves (see compliance_schedule_fra_ocr_service).
"""

from __future__ import annotations

import calendar
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from dateutil.relativedelta import relativedelta

from src.domain.services.document_intelligence_service import DocumentIntelligenceService
from src.domain.services.ocr_field_extraction import (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_NONE,
    ExtractedField,
)

logger = logging.getLogger(__name__)

FRA_OCR_PURPOSE = "fra_pas79"
FRA_TAXONOMY_ID = "03.01"
EVIDENCE_SNIPPET_MAX = 200
ACTION_TEXT_MAX = 2000
ACTION_ROW_LIMIT = 100

_D_ISO = r"\d{4}-\d{2}-\d{2}"
_D_DMY = r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
_D_TEXT = r"\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\.?\s+\d{4}"
_D_MTEXT = r"[A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}"
_ANY_DATE = rf"(?:{_D_ISO}|{_D_DMY}|{_D_TEXT}|{_D_MTEXT})"

_ASSESSMENT_DATE_RE = re.compile(
    r"(?:date\s+of\s+(?:this\s+)?(?:fire\s+risk\s+)?assessment|assessment\s+date|"
    r"date\s+assessed|date\s+of\s+(?:site\s+)?visit|date\s+carried\s+out|"
    r"date\s+of\s+(?:current\s+)?review)\s*[:\-–]?\s*(" + _ANY_DATE + r")",
    re.IGNORECASE,
)

_NEXT_REVIEW_RE = re.compile(
    r"(?:date\s+of\s+next\s+(?:formal\s+)?review|next\s+review(?:\s+date)?|"
    r"review\s+(?:due|date)|recommended\s+(?:date\s+of\s+)?review|"
    r"next\s+assessment\s+due)\s*[:\-–]?\s*(" + _ANY_DATE + r")",
    re.IGNORECASE,
)

_REVIEW_INTERVAL_RE = re.compile(
    r"review(?:ed)?\s+(?:at\s+least\s+)?(?:every\s+(\d{1,2})\s+months?|"
    r"(annually|every\s+year)|every\s+(\d{1,2})\s+years?)",
    re.IGNORECASE,
)

_ASSESSOR_NAME_RE = re.compile(
    r"(?:fire[ \t]+risk[ \t]+)?(?:assessor|assessment[ \t]+(?:carried[ \t]+out|undertaken)[ \t]+by|"
    r"assessed[ \t]+by|carried[ \t]+out[ \t]+by|prepared[ \t]+by|author)[ \t]*[:\-–][ \t]*"
    r"([A-Z][A-Za-z'’\-]{1,20}(?:[ \t]+[A-Z][A-Za-z'’\-]{1,20}){0,3})",
    re.IGNORECASE,
)

_ASSESSOR_ORG_RE = re.compile(
    r"(?:assessing\s+(?:company|organisation)|company|organisation|"
    r"on\s+behalf\s+of|consultancy)\s*[:\-–]\s*([^\n]{2,80})",
    re.IGNORECASE,
)

_PREMISES_RE = re.compile(
    r"(?:premises|site|building|property)(?:\s+name)?(?:\s+assessed)?\s*[:\-–]\s*([^\n]{2,120})",
    re.IGNORECASE,
)

_PAS79_REF_RE = re.compile(
    r"(?:report\s*(?:no\.?|number|ref(?:erence)?)|fra\s*(?:no\.?|ref(?:erence)?)|"
    r"assessment\s*ref(?:erence)?|document\s*ref(?:erence)?)\s*[:#\-–]?\s*"
    r"([A-Z0-9][A-Z0-9\-/_.]{2,30})",
    re.IGNORECASE,
)

_RISK_PAS79_RE = re.compile(
    r"(?:overall|premises|resultant)?\s*(?:fire\s+)?risk\s+(?:rating|level|category|"
    r"classification)\s*[:\-–]?\s*(trivial|tolerable|moderate|substantial|intolerable)",
    re.IGNORECASE,
)

_RISK_LMH_RE = re.compile(
    r"(?:overall|premises|resultant)?\s*(?:fire\s+)?risk\s+(?:rating|level|category|"
    r"classification)\s*[:\-–]?\s*(very\s+low|low|medium|moderate|high|very\s+high)",
    re.IGNORECASE,
)

_ACTION_PLAN_START_RE = re.compile(
    r"^[ \t]*(?:\d+(?:\.\d+)*[ \t.)]*)?"
    r"(?:(?:priority[ \t]+)?action[ \t]+plan|significant[ \t]+findings[ \t]+and[ \t]+"
    r"action[ \t]+plan|recommendations?[ \t]+and[ \t]+priorit\w+|"
    r"schedule[ \t]+of[ \t]+(?:remedial[ \t]+)?actions?)\b[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)

_ACTION_PLAN_END_RE = re.compile(
    r"^[ \t]*(?:\d+(?:\.\d+)*[ \t.)]*)?"
    r"(?:appendix|annex|conclusion|declaration|signature|sign[- ]off|glossary|"
    r"photograph|limitations|disclaimer|distribution)\b[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)

_PRIORITY_TOKEN = r"(?:immediate(?:ly)?|urgent|high|medium|med|low|p[123]\b|priority[ \t]*[123]\b|[123]\b)"

_ACTION_ROW_PRIORITY_FIRST_RE = re.compile(
    r"^[ \t]*(?P<ref>\d{1,3}(?:\.\d{1,2})?)[.)|\t ]+"
    r"(?P<priority>" + _PRIORITY_TOKEN + r")[\t |\-:]+"
    r"(?P<text>.+?)"
    r"(?:[\t |]+(?P<target>" + _ANY_DATE + r"|immediate(?:ly)?|asap|ongoing|on[- ]going))?"
    r"[ \t]*$",
    re.IGNORECASE,
)

_ACTION_ROW_PRIORITY_LAST_RE = re.compile(
    r"^[ \t]*(?P<ref>\d{1,3}(?:\.\d{1,2})?)[.)|\t ]+"
    r"(?P<text>.+?)[\t |]+"
    r"(?P<priority>" + _PRIORITY_TOKEN + r")"
    r"(?:[\t |]+(?P<target>" + _ANY_DATE + r"|immediate(?:ly)?|asap|ongoing))?"
    r"[ \t]*$",
    re.IGNORECASE,
)

_ACTION_ROW_BARE_RE = re.compile(
    r"^[ \t]*(?P<ref>\d{1,3}(?:\.\d{1,2})?)[.)|\t ]+(?P<text>.{15,})[ \t]*$"
)

_PRIORITY_MAP = {
    "immediate": "high",
    "immediately": "high",
    "urgent": "high",
    "high": "high",
    "p1": "high",
    "priority 1": "high",
    "1": "high",
    "medium": "medium",
    "med": "medium",
    "p2": "medium",
    "priority 2": "medium",
    "2": "medium",
    "low": "low",
    "p3": "low",
    "priority 3": "low",
    "3": "low",
}

_POSTNOMINAL_RE = re.compile(
    r"\b(?:GIFireE|MIFireE|CFIFireE|BEng|MSc|CEng|FRICS|IFSM|CFPA)\b\.?",
    re.IGNORECASE,
)

_MONTHS = {
    name.lower(): index
    for index, name in enumerate(calendar.month_name)
    if name
} | {
    name.lower(): index
    for index, name in enumerate(calendar.month_abbr)
    if name
}

_BARE_NUMERIC_RE = re.compile(r"^\d[\d\s.,]*$")
_NON_DATE_TARGET_RE = re.compile(r"^(?:immediate(?:ly)?|asap|ongoing|on[- ]going)$", re.IGNORECASE)


def _clip_evidence(snippet: str | None) -> str | None:
    if snippet is None:
        return None
    cleaned = " ".join(snippet.split())
    if not cleaned:
        return None
    return cleaned[:EVIDENCE_SNIPPET_MAX]


def _field_to_proposed(extracted: ExtractedField) -> dict[str, Any]:
    return {
        "value": extracted.value,
        "confidence": extracted.confidence,
        "evidence_snippet": _clip_evidence(extracted.raw_snippet),
    }


def _parse_uk_date(raw: str) -> date | None:
    """Parse a UK-leaning date string. Day-first for numeric DMY forms."""
    text = (raw or "").strip().rstrip(".,;")
    if not text:
        return None

    # ISO first
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None

    dmy = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", text)
    if dmy:
        day_s, month_s, year_s = dmy.group(1), dmy.group(2), dmy.group(3)
        day, month = int(day_s), int(month_s)
        year = int(year_s)
        if len(year_s) == 2:
            if year > 79:
                return None
            year = 2000 + year
        try:
            return date(year, month, day)
        except ValueError:
            return None

    text_form = re.fullmatch(
        r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?\s+(\d{4})",
        text,
        re.IGNORECASE,
    )
    if text_form:
        day = int(text_form.group(1))
        month = _MONTHS.get(text_form.group(2).lower().rstrip("."))
        year = int(text_form.group(3))
        if month is None:
            return None
        try:
            return date(year, month, day)
        except ValueError:
            return None

    mtext = re.fullmatch(
        r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})",
        text,
        re.IGNORECASE,
    )
    if mtext:
        month = _MONTHS.get(mtext.group(1).lower().rstrip("."))
        day = int(mtext.group(2))
        year = int(mtext.group(3))
        if month is None:
            return None
        try:
            return date(year, month, day)
        except ValueError:
            return None

    return None


def _normalise_priority(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = " ".join(raw.strip().lower().split())
    return _PRIORITY_MAP.get(key)


def _clean_assessor_name(name: str) -> str:
    cleaned = _POSTNOMINAL_RE.sub("", name).strip()
    return " ".join(cleaned.split())


def _extract_labelled_date(pattern: re.Pattern[str], text: str) -> ExtractedField:
    match = pattern.search(text)
    if not match:
        return ExtractedField()
    raw = match.group(1).strip()
    parsed = _parse_uk_date(raw)
    if parsed is None:
        return ExtractedField(None, CONFIDENCE_NONE, _clip_evidence(match.group(0)))
    return ExtractedField(parsed.isoformat(), CONFIDENCE_HIGH, _clip_evidence(match.group(0)))


def _extract_review_interval(text: str) -> ExtractedField:
    match = _REVIEW_INTERVAL_RE.search(text)
    if not match:
        return ExtractedField()
    months_group, annually_group, years_group = match.group(1), match.group(2), match.group(3)
    if months_group:
        months = int(months_group)
    elif annual_group:
        months = 12
    elif years_group:
        months = int(years_group) * 12
    else:
        return ExtractedField()
    return ExtractedField(str(months), CONFIDENCE_HIGH, _clip_evidence(match.group(0)))


def _extract_simple(pattern: re.Pattern[str], text: str, *, transform=None) -> ExtractedField:
    match = pattern.search(text)
    if not match:
        return ExtractedField()
    value = match.group(1).strip().rstrip(".,;")
    if transform is not None:
        value = transform(value)
    if not value:
        return ExtractedField()
    return ExtractedField(value, CONFIDENCE_HIGH, _clip_evidence(match.group(0)))


def _extract_risk(text: str) -> tuple[ExtractedField, str | None]:
    pas79 = _RISK_PAS79_RE.search(text)
    if pas79:
        value = pas79.group(1).strip().lower()
        return (
            ExtractedField(value, CONFIDENCE_HIGH, _clip_evidence(pas79.group(0))),
            "pas79",
        )
    lmh = _RISK_LMH_RE.search(text)
    if lmh:
        value = " ".join(lmh.group(1).strip().lower().split())
        return (
            ExtractedField(value, CONFIDENCE_HIGH, _clip_evidence(lmh.group(0))),
            "lmh",
        )
    return ExtractedField(), None


@dataclass
class FraProposedAction:
    index: int
    source_ref: Optional[str] = None
    text: str = ""
    priority_raw: Optional[str] = None
    priority_normalised: Optional[str] = None
    target_date: Optional[date] = None
    target_date_raw: Optional[str] = None
    confidence: str = CONFIDENCE_NONE
    needs_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "source_ref": self.source_ref,
            "text": self.text,
            "priority_raw": self.priority_raw,
            "priority_normalised": self.priority_normalised,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "target_date_raw": self.target_date_raw,
            "confidence": self.confidence,
            "needs_review": self.needs_review,
        }


def _action_confidence(priority: str | None, target: date | None, target_raw: str | None) -> str:
    if priority and target is not None:
        return CONFIDENCE_HIGH
    if priority and target_raw and _NON_DATE_TARGET_RE.match(target_raw):
        return CONFIDENCE_MEDIUM
    if priority:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_NONE


def _parse_target(raw: str | None) -> tuple[date | None, str | None]:
    if raw is None:
        return None, None
    cleaned = raw.strip()
    if not cleaned:
        return None, None
    if _NON_DATE_TARGET_RE.match(cleaned):
        return None, cleaned
    parsed = _parse_uk_date(cleaned)
    return parsed, cleaned


def _match_action_row(line: str) -> re.Match[str] | None:
    for pattern in (_ACTION_ROW_PRIORITY_FIRST_RE, _ACTION_ROW_PRIORITY_LAST_RE, _ACTION_ROW_BARE_RE):
        match = pattern.match(line)
        if match:
            return match
    return None


def _extract_action_plan(text: str) -> tuple[list[FraProposedAction], list[str]]:
    warnings: list[str] = []
    start = _ACTION_PLAN_START_RE.search(text)
    if not start:
        warnings.append("No Priority Action Plan section was found in this document.")
        return [], warnings

    section = text[start.end() :]
    end = _ACTION_PLAN_END_RE.search(section)
    if end:
        section = section[: end.start()]

    actions: list[FraProposedAction] = []
    seen: set[tuple[str, str]] = set()
    last_matched = False
    true_count = 0

    for raw_line in section.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            last_matched = False
            continue
        # Skip column-header lines
        if re.match(r"^[ \t]*ref\b", line, re.IGNORECASE) and re.search(r"priority|action", line, re.IGNORECASE):
            last_matched = False
            continue

        # Continuation of previous action text
        if (
            last_matched
            and actions
            and re.match(r"^[ \t]+", raw_line)
            and not re.match(r"^[ \t]*\d{1,3}(?:\.\d{1,2})?[.)|\t ]", raw_line)
        ):
            cont = line.strip()
            if cont and not _BARE_NUMERIC_RE.match(cont):
                combined = f"{actions[-1].text} {cont}".strip()
                if len(combined) > ACTION_TEXT_MAX:
                    actions[-1].text = combined[:ACTION_TEXT_MAX]
                    warnings.append(
                        f"Action {actions[-1].source_ref or actions[-1].index} was longer than "
                        "2000 characters and has been truncated — check it against the report."
                    )
                else:
                    actions[-1].text = combined
            continue

        match = _match_action_row(line)
        if not match:
            last_matched = False
            continue

        groups = match.groupdict()
        ref = groups.get("ref")
        priority_raw = groups.get("priority")
        text_body = (groups.get("text") or "").strip()
        target_raw_in = groups.get("target")

        if len(text_body) < 15:
            last_matched = False
            continue
        if _BARE_NUMERIC_RE.match(text_body):
            last_matched = False
            continue

        true_count += 1
        truncated = False
        if len(text_body) > ACTION_TEXT_MAX:
            text_body = text_body[:ACTION_TEXT_MAX]
            truncated = True

        dedupe_key = (ref or "", text_body[:60])
        if dedupe_key in seen:
            warnings.append(
                f"Duplicate action {ref or '?'} was skipped (same reference and opening text)."
            )
            last_matched = False
            continue
        seen.add(dedupe_key)

        if truncated:
            warnings.append(
                f"Action {ref or true_count} was longer than 2000 characters and has been "
                "truncated — check it against the report."
            )

        if len(actions) >= ACTION_ROW_LIMIT:
            continue

        priority_norm = _normalise_priority(priority_raw)
        target_date, target_raw = _parse_target(target_raw_in)
        needs_review = priority_raw is None
        confidence = _action_confidence(priority_norm, target_date, target_raw)
        if needs_review:
            confidence = CONFIDENCE_NONE

        actions.append(
            FraProposedAction(
                index=len(actions),
                source_ref=ref,
                text=text_body,
                priority_raw=priority_raw.strip() if priority_raw else None,
                priority_normalised=priority_norm,
                target_date=target_date,
                target_date_raw=target_raw,
                confidence=confidence,
                needs_review=needs_review,
            )
        )
        last_matched = True

    if true_count > ACTION_ROW_LIMIT:
        warnings.append(
            f"Action plan had {true_count} rows; only the first {ACTION_ROW_LIMIT} were kept."
        )
    if start and not actions:
        warnings.append("An action plan section was found but no rows could be read from it.")

    return actions, warnings


def parse_fields_from_text(text: str) -> tuple[dict[str, Any], list[FraProposedAction], list[str]]:
    """Parse PAS 79-style fields and Priority Action Plan rows from OCR text."""
    warnings: list[str] = []
    if not (text or "").strip():
        empty = {
            "assessment_date": _field_to_proposed(ExtractedField()),
            "next_review_date": _field_to_proposed(ExtractedField()),
            "review_interval_months": _field_to_proposed(ExtractedField()),
            "assessor_name": _field_to_proposed(ExtractedField()),
            "assessor_organisation": _field_to_proposed(ExtractedField()),
            "premises_name": _field_to_proposed(ExtractedField()),
            "pas79_reference": _field_to_proposed(ExtractedField()),
            "overall_risk_rating": _field_to_proposed(ExtractedField()),
            "risk_vocabulary": None,
        }
        return empty, [], ["Could not extract any text from this document."]

    assessment_date = _extract_labelled_date(_ASSESSMENT_DATE_RE, text)
    next_review_date = _extract_labelled_date(_NEXT_REVIEW_RE, text)
    review_interval = _extract_review_interval(text)
    assessor_name = _extract_simple(_ASSESSOR_NAME_RE, text, transform=_clean_assessor_name)
    assessor_org = _extract_simple(_ASSESSOR_ORG_RE, text)
    premises = _extract_simple(_PREMISES_RE, text)
    pas79_ref = _extract_simple(_PAS79_REF_RE, text)
    overall_risk, risk_vocab = _extract_risk(text)

    # Cross-check / derive next_review_date
    if assessment_date.is_extracted and review_interval.is_extracted:
        try:
            assessed = date.fromisoformat(assessment_date.value or "")
            months = int(review_interval.value or "0")
            derived = assessed + relativedelta(months=months)
        except (TypeError, ValueError):
            derived = None
        if derived is not None:
            if next_review_date.is_extracted:
                try:
                    stated = date.fromisoformat(next_review_date.value or "")
                except ValueError:
                    stated = None
                if stated is not None and abs((stated - derived).days) > 45:
                    warnings.append(
                        f"Stated next review date ({stated.isoformat()}) differs from "
                        f"assessment date plus review interval ({derived.isoformat()}) "
                        "by more than 45 days — neither was corrected."
                    )
            else:
                next_review_date = ExtractedField(
                    derived.isoformat(),
                    CONFIDENCE_MEDIUM,
                    "Derived from assessment date + review interval (not read from document).",
                )
                warnings.append(
                    "Next review date was derived from assessment date and review interval; "
                    "it was not read from the document."
                )

    actions, action_warnings = _extract_action_plan(text)
    warnings.extend(action_warnings)

    fields = {
        "assessment_date": _field_to_proposed(assessment_date),
        "next_review_date": _field_to_proposed(next_review_date),
        "review_interval_months": _field_to_proposed(review_interval),
        "assessor_name": _field_to_proposed(assessor_name),
        "assessor_organisation": _field_to_proposed(assessor_org),
        "premises_name": _field_to_proposed(premises),
        "pas79_reference": _field_to_proposed(pas79_ref),
        "overall_risk_rating": _field_to_proposed(overall_risk),
        "risk_vocabulary": risk_vocab,
    }
    return fields, actions, warnings


@dataclass
class FraPas79Extraction:
    source_filename: str
    extraction_method: str
    fields: dict[str, Any] = field(default_factory=dict)
    actions: list[FraProposedAction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    page_count: Optional[int] = None
    ocr_provider_status: Optional[str] = None

    def to_proposed_json(self) -> dict[str, Any]:
        return {
            **self.fields,
            "actions": [action.to_dict() for action in self.actions],
        }


class FraPas79OcrService:
    """Extract PAS 79 FRA fields via the shared document intelligence spine."""

    def __init__(
        self,
        intelligence_service: DocumentIntelligenceService | None = None,
        ocr_pipeline: Any | None = None,
    ) -> None:
        self._intelligence = intelligence_service or DocumentIntelligenceService()
        self._ocr_pipeline = ocr_pipeline  # reserved for tests; unused in production path

    async def extract(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> FraPas79Extraction:
        warnings: list[str] = []
        spine = await self._intelligence.extract_bytes(
            raw=content,
            filename=filename,
            content_type=content_type,
            purpose=FRA_OCR_PURPOSE,
        )
        text = spine.text or ""
        extraction_method = spine.extraction_method or "none"

        if spine.note:
            warnings.append(spine.note)
        if spine.hard_ocr_failure:
            warnings.append("OCR provider failed and no native text was available.")
        if spine.ocr_provider_status == "not_configured" and not text.strip():
            warnings.append("OCR provider is not configured; native PDF text was empty.")

        char_count = len(text)
        logger.info(
            "fra_pas79 extract complete filename_len=%s method=%s provider_status=%s "
            "page_count=%s char_count=%s",
            len(filename or ""),
            extraction_method,
            spine.ocr_provider_status,
            spine.page_count,
            char_count,
        )

        if not text.strip():
            empty_fields, _, empty_warnings = parse_fields_from_text("")
            warnings.extend(empty_warnings)
            return FraPas79Extraction(
                source_filename=filename,
                extraction_method=extraction_method,
                fields=empty_fields,
                actions=[],
                warnings=warnings or ["Could not extract any text from this document."],
                page_count=spine.page_count,
                ocr_provider_status=spine.ocr_provider_status,
            )

        fields, actions, field_warnings = parse_fields_from_text(text)
        warnings.extend(field_warnings)
        return FraPas79Extraction(
            source_filename=filename,
            extraction_method=extraction_method,
            fields=fields,
            actions=actions,
            warnings=warnings,
            page_count=spine.page_count,
            ocr_provider_status=spine.ocr_provider_status,
        )


__all__ = [
    "FRA_OCR_PURPOSE",
    "FRA_TAXONOMY_ID",
    "FraProposedAction",
    "FraPas79Extraction",
    "FraPas79OcrService",
    "parse_fields_from_text",
    "_parse_uk_date",
]
