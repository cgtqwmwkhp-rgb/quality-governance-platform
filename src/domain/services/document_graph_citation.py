"""Doc Graph citation helpers: quote_hash + deterministic staleness (ADR-0021).

Never rewrites published PDF/DOCX bytes. Staleness is evaluated against live
``DocumentChunk`` text using the locator snapshotted on the edge.
"""

from __future__ import annotations

import enum
import hashlib
import re
from dataclasses import dataclass
from typing import Optional


class CitationStaleness(str, enum.Enum):
    UNCHANGED = "unchanged"
    MOVED = "moved"
    TEXT_CHANGED = "text_changed"
    NOT_FOUND = "not_found"


# Exact deterministic references operators already type into controlled docs.
# Matches: DOC-2026-0042, PEL-IMS-POL-0001, /documents/123 (optional query).
DOC_REF_RE = re.compile(r"\bDOC-\d{4}-\d{4,}\b", re.IGNORECASE)
PEL_REF_RE = re.compile(r"\bPEL-[A-Z0-9]+(?:-[A-Z0-9]+){1,4}\b", re.IGNORECASE)
DOC_PATH_RE = re.compile(r"/documents/(\d+)(?:\?[^\s)]*)?", re.IGNORECASE)


@dataclass(frozen=True)
class CitationMatch:
    """A regex citation hit inside a chunk, with span offsets relative to chunk text."""

    kind: str  # doc_ref | pel_ref | document_path
    raw: str
    char_start: int
    char_end: int
    resolved_document_id: Optional[int] = None
    resolved_reference: Optional[str] = None


def compute_quote_hash(text: str) -> str:
    """SHA-256 hex digest of the citation span (UTF-8)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_citation_matches(chunk_text: str) -> list[CitationMatch]:
    """Find DOC / PEL / /documents/{id} citations in chunk text."""
    hits: list[CitationMatch] = []
    if not chunk_text:
        return hits

    for match in DOC_REF_RE.finditer(chunk_text):
        hits.append(
            CitationMatch(
                kind="doc_ref",
                raw=match.group(0),
                char_start=match.start(),
                char_end=match.end(),
                resolved_reference=match.group(0).upper(),
            )
        )

    for match in PEL_REF_RE.finditer(chunk_text):
        hits.append(
            CitationMatch(
                kind="pel_ref",
                raw=match.group(0),
                char_start=match.start(),
                char_end=match.end(),
                resolved_reference=match.group(0).upper(),
            )
        )

    for match in DOC_PATH_RE.finditer(chunk_text):
        hits.append(
            CitationMatch(
                kind="document_path",
                raw=match.group(0),
                char_start=match.start(),
                char_end=match.end(),
                resolved_document_id=int(match.group(1)),
            )
        )

    return hits


def evaluate_citation_staleness(
    *,
    quote_hash: Optional[str],
    citation_text: Optional[str],
    char_start: Optional[int],
    char_end: Optional[int],
    chunk_content: Optional[str],
) -> CitationStaleness:
    """Classify citation freshness against the live chunk body.

    Rules (deterministic):
    - No chunk / empty content → ``not_found``
    - Locator span still hashes to ``quote_hash`` → ``unchanged``
    - ``citation_text`` (or original span text) found elsewhere → ``moved``
    - Hash mismatch at locator and text not found → ``text_changed`` when a
      locator was present; otherwise ``not_found``
    """
    if not chunk_content:
        return CitationStaleness.NOT_FOUND

    content = chunk_content
    expected_hash = (quote_hash or "").strip().lower() or None
    quoted = citation_text

    if char_start is not None and char_end is not None and 0 <= char_start < char_end <= len(content):
        span = content[char_start:char_end]
        if expected_hash and compute_quote_hash(span) == expected_hash:
            return CitationStaleness.UNCHANGED
        if quoted is None:
            quoted = span
        # Span moved or changed — search for original quote elsewhere.
        if quoted and quoted in content:
            new_start = content.find(quoted)
            if new_start != char_start:
                return CitationStaleness.MOVED
            # Same place but hash mismatch (e.g. quote_hash stale vs citation_text)
            if expected_hash and compute_quote_hash(quoted) != expected_hash:
                return CitationStaleness.TEXT_CHANGED
            return CitationStaleness.UNCHANGED
        return CitationStaleness.TEXT_CHANGED

    if quoted:
        if quoted in content:
            if expected_hash and compute_quote_hash(quoted) == expected_hash:
                return CitationStaleness.MOVED if char_start is not None else CitationStaleness.UNCHANGED
            return CitationStaleness.MOVED
        return CitationStaleness.NOT_FOUND

    if expected_hash:
        # Brute scan windows is too expensive; without locator/text we cannot
        # prove presence — report not_found.
        return CitationStaleness.NOT_FOUND

    return CitationStaleness.NOT_FOUND


__all__ = [
    "CitationMatch",
    "CitationStaleness",
    "DOC_PATH_RE",
    "DOC_REF_RE",
    "PEL_REF_RE",
    "compute_quote_hash",
    "evaluate_citation_staleness",
    "extract_citation_matches",
]
