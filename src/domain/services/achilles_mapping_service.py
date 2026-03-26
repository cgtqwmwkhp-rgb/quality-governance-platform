"""Map imported audit content to Achilles / UVDB style frameworks."""

from __future__ import annotations


class AchillesMappingService:
    """Simple framework detector for imported third-party audit reports."""

    def map_text(self, text: str, assurance_scheme: str | None = None) -> list[dict[str, object]]:
        lowered = text.lower()
        scheme = (assurance_scheme or "").lower()
        mappings: list[dict[str, object]] = []
        if "achilles" in lowered or "uvdb" in lowered or "achilles" in scheme or "uvdb" in scheme:
            mappings.append(
                {
                    "framework": "Achilles UVDB",
                    "confidence": 0.85,
                    "basis": "scheme_or_content_match",
                }
            )
        return mappings
