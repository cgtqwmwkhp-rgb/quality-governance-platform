"""Shared OCR field extraction primitives.

Used by Planet Mark PDF OCR and FRA / PAS 79 OCR. Kept neutral so neither
feature imports the other.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_NONE = "none"


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


__all__ = [
    "CONFIDENCE_HIGH",
    "CONFIDENCE_MEDIUM",
    "CONFIDENCE_NONE",
    "ExtractedField",
]
