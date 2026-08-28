"""Helpers for evidence-asset Content-Disposition."""

from __future__ import annotations

import re
from typing import Literal, Optional
from urllib.parse import quote

Disposition = Literal["inline", "attachment"]

#: Anything that cannot appear unescaped inside a quoted-string header parameter:
#: bytes outside printable US-ASCII (control characters, CR/LF, and every
#: non-Latin-1 character), plus the two characters that end or escape the quoting.
_UNSAFE_IN_QUOTED_STRING = re.compile(r'[^\x20-\x7e]|["\\]')


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


def build_evidence_content_disposition(disposition: Disposition, filename: Optional[str]) -> str:
    """Build a ``Content-Disposition`` value that survives an arbitrary filename.

    ``original_filename`` is whatever the uploading browser sent, so it can carry
    non-Latin-1 characters, a double quote, or a CR/LF. The signed-url endpoint
    hands that string to Azure as a SAS parameter, but a byte-serving endpoint puts
    it in a response header, where Starlette encodes headers as Latin-1: an accented
    filename would raise ``UnicodeEncodeError`` — a 500 on an otherwise valid read —
    and a quote would let the caller close the parameter and append its own.

    The quoted form is therefore sanitised for clients that only read it, and the
    real name is carried in RFC 5987 ``filename*`` whenever sanitising changed it.
    """
    raw = (filename or "").strip() or "download"
    fallback = _UNSAFE_IN_QUOTED_STRING.sub("_", raw)
    header = f'{disposition}; filename="{fallback}"'
    if fallback != raw:
        header += f"; filename*=UTF-8''{quote(raw, safe='')}"
    return header
