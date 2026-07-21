"""Normalise and score lookup names to prevent near-duplicate Safety lookups."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Sequence

# Exact after normalise → auto-reuse. At/above this → operator must confirm.
SIMILAR_THRESHOLD = 0.86


_PUNCT_RE = re.compile(r"[^a-z0-9]+")
_SPACE_RE = re.compile(r"\s+")


def normalise_lookup_key(value: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for equality checks."""
    text = (value or "").strip().lower()
    text = _PUNCT_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def similarity_score(left: str, right: str) -> float:
    a = normalise_lookup_key(left)
    b = normalise_lookup_key(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


@dataclass(frozen=True)
class SimilarMatch:
    id: int
    name: str
    score: float


def find_similar_matches(
    name: str,
    candidates: Sequence[tuple[int, str]],
    *,
    threshold: float = SIMILAR_THRESHOLD,
    limit: int = 5,
) -> list[SimilarMatch]:
    """Return candidates at/above threshold, highest score first (excluding exact)."""
    key = normalise_lookup_key(name)
    if not key:
        return []
    scored: list[SimilarMatch] = []
    for candidate_id, candidate_name in candidates:
        score = similarity_score(name, candidate_name)
        if score >= threshold and normalise_lookup_key(candidate_name) != key:
            scored.append(SimilarMatch(id=candidate_id, name=candidate_name, score=round(score, 4)))
    scored.sort(key=lambda item: (-item.score, item.name.lower(), item.id))
    return scored[:limit]


def find_exact_match(name: str, candidates: Iterable[tuple[int, str]]) -> tuple[int, str] | None:
    key = normalise_lookup_key(name)
    if not key:
        return None
    for candidate_id, candidate_name in candidates:
        if normalise_lookup_key(candidate_name) == key:
            return candidate_id, candidate_name
    return None


def classify_lookup_name(
    name: str,
    candidates: Sequence[tuple[int, str]],
    *,
    threshold: float = SIMILAR_THRESHOLD,
) -> tuple[str, tuple[int, str] | None, list[SimilarMatch]]:
    """
    Classify a proposed lookup name.

    Returns (intent, exact_match, similar_matches) where intent is:
    - reuse: exact normalise match
    - similar: near-duplicate requires confirmation
    - new: no close match
    """
    exact = find_exact_match(name, candidates)
    if exact is not None:
        return "reuse", exact, []
    similar = find_similar_matches(name, candidates, threshold=threshold)
    if similar:
        return "similar", None, similar
    return "new", None, []
