"""CEL document-version freshness classifiers (Doc Graph Wave 1 PR-F).

Compares a ComplianceEvidenceLink's pinned ``document_version_id`` against the
current library tip. Pure helpers — no I/O. Never rewrites published bytes.
"""

from __future__ import annotations

from typing import Literal, Optional

CelVersionFreshness = Literal["current", "stale", "unpinned", "unknown"]


def classify_cel_version_freshness(
    *,
    pinned_document_version_id: Optional[int],
    tip_document_version_id: Optional[int],
) -> CelVersionFreshness:
    """Classify whether a CEL pin still matches the library tip.

    - ``unpinned``: no version was recorded on the link
    - ``current``: pin equals tip
    - ``stale``: pin differs from a known tip (document has moved on)
    - ``unknown``: pin exists but tip could not be resolved
    """
    if pinned_document_version_id is None:
        return "unpinned"
    if tip_document_version_id is None:
        return "unknown"
    if int(pinned_document_version_id) == int(tip_document_version_id):
        return "current"
    return "stale"
