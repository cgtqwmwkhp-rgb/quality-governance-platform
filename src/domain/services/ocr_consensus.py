"""Provider-neutral, deterministic OCR page consensus primitives."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence

PAGE_CONSENSUS_PIPELINE_VERSION = "2026.07.r5"


class OCRPageSource(Protocol):
    """Minimal page contract accepted by OCR consensus functions."""

    provider: str
    page_number: int
    text: str


PageConsensusPersistHook = Callable[["OCRPageConsensus", Sequence[OCRPageSource]], None]


@dataclass(frozen=True)
class OCRPageCandidate:
    """OCR text emitted by one provider for one 1-indexed page."""

    provider: str
    page_number: int
    text: str


@dataclass(frozen=True)
class OCRPageConsensus:
    """Agreement metrics and selected text for a single document page."""

    page_number: int
    selected_text: str
    selected_provider: str
    agreement: float
    character_error_rate: float | None
    providers: tuple[str, ...]


def normalize_ocr_text(text: str) -> str:
    """Normalize harmless OCR whitespace differences before comparison."""
    return " ".join(text.casefold().split())


def hash_ocr_text(text: str) -> str:
    """Return SHA-256 hex digest of normalized OCR text for artifact storage."""
    normalized = normalize_ocr_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def character_error_rate(reference: str, observed: str) -> float | None:
    """Return Levenshtein character error rate, or ``None`` without a reference."""
    normalized_reference = normalize_ocr_text(reference)
    normalized_observed = normalize_ocr_text(observed)
    if not normalized_reference:
        return None

    previous = list(range(len(normalized_observed) + 1))
    for reference_index, reference_character in enumerate(normalized_reference, start=1):
        current = [reference_index]
        for observed_index, observed_character in enumerate(normalized_observed, start=1):
            substitution_cost = int(reference_character != observed_character)
            current.append(
                min(
                    current[-1] + 1,
                    previous[observed_index] + 1,
                    previous[observed_index - 1] + substitution_cost,
                )
            )
        previous = current
    return previous[-1] / len(normalized_reference)


def build_page_consensus(
    candidates: Sequence[OCRPageSource],
    *,
    reference_text: str | None = None,
    persist_hook: PageConsensusPersistHook | None = None,
) -> OCRPageConsensus:
    """Select deterministic page text and calculate provider agreement.

    The most frequent normalized text wins. Ties retain the first supplied
    candidate, allowing callers to express a provider preference explicitly.

    When ``persist_hook`` is supplied it is invoked with the consensus result
    and original candidates so callers can persist ``ocr_artifacts`` rows.
    """
    if not candidates:
        raise ValueError("At least one OCR page candidate is required.")

    page_numbers = {candidate.page_number for candidate in candidates}
    if len(page_numbers) != 1:
        raise ValueError("OCR page candidates must refer to the same page.")

    normalized_texts = [normalize_ocr_text(candidate.text) for candidate in candidates]
    winner_index = max(
        range(len(candidates)),
        key=lambda index: (normalized_texts.count(normalized_texts[index]), -index),
    )
    winner = candidates[winner_index]
    agreement = normalized_texts.count(normalized_texts[winner_index]) / len(candidates)

    consensus = OCRPageConsensus(
        page_number=winner.page_number,
        selected_text=winner.text,
        selected_provider=winner.provider,
        agreement=agreement,
        character_error_rate=(
            character_error_rate(reference_text, winner.text) if reference_text is not None else None
        ),
        providers=tuple(candidate.provider for candidate in candidates),
    )
    if persist_hook is not None:
        persist_hook(consensus, candidates)
    return consensus


__all__ = [
    "OCRPageCandidate",
    "OCRPageConsensus",
    "OCRPageSource",
    "PAGE_CONSENSUS_PIPELINE_VERSION",
    "PageConsensusPersistHook",
    "build_page_consensus",
    "character_error_rate",
    "hash_ocr_text",
    "normalize_ocr_text",
]
