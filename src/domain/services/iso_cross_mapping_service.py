"""Cross-map extracted audit content to ISO standards."""

from __future__ import annotations

import re


class ISOCrossMappingService:
    """Lightweight ISO reference detector with provenance-friendly outputs."""

    _STANDARD_PATTERNS: tuple[tuple[str, str], ...] = (
        ("ISO 9001", r"\biso\s*9001\b"),
        ("ISO 14001", r"\biso\s*14001\b"),
        ("ISO 27001", r"\biso\s*27001\b"),
        ("ISO 45001", r"\biso\s*45001\b"),
    )

    def map_text(self, text: str) -> list[dict[str, object]]:
        lowered = text.lower()
        mappings: list[dict[str, object]] = []
        for label, pattern in self._STANDARD_PATTERNS:
            if re.search(pattern, lowered, flags=re.IGNORECASE):
                mappings.append(
                    {
                        "standard": label,
                        "confidence": 0.8,
                        "basis": "explicit_reference",
                    }
                )
        return mappings
