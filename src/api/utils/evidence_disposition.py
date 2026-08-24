"""Helpers for evidence-asset signed URL Content-Disposition."""

from __future__ import annotations

from typing import Literal, Optional

Disposition = Literal["inline", "attachment"]


def resolve_evidence_signed_url_disposition(
    requested: str,
    content_type: Optional[str],
) -> Disposition:
    """Resolve effective Content-Disposition for an evidence signed URL.

    Clients may request ``inline`` for in-app preview (iframe / native media).
    The server only honours that for preview-safe media types that match the
    FE ``canPreviewInApp`` tier-1 set: ``image/*``, ``application/pdf``,
    ``video/*``, and ``audio/*``. Everything else — including empty/unknown
    types, Office docs, and ``application/octet-stream`` — stays ``attachment``.
    """
    if requested != "inline":
        return "attachment"

    mime = (content_type or "").lower().split(";", 1)[0].strip()
    if not mime:
        return "attachment"

    if mime.startswith("image/") or mime.startswith("video/") or mime.startswith("audio/") or mime == "application/pdf":
        return "inline"

    return "attachment"
