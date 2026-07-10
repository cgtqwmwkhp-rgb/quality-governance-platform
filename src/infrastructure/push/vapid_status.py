"""VAPID / Web Push readiness helpers (WCS-B06).

Push is optional: missing VAPID must not fail liveness or readiness probes.
These helpers only surface configuration honesty for ops and the admin UI.
"""

from __future__ import annotations

import os
from typing import Any


def get_vapid_readiness() -> dict[str, Any]:
    """Return push/VAPID configuration status without secrets.

    Status values:
    - ``configured``: public + private keys present
    - ``partial``: only one of the keys present
    - ``not_configured``: neither key present
    """
    private = (os.getenv("VAPID_PRIVATE_KEY") or "").strip()
    public = (os.getenv("VAPID_PUBLIC_KEY") or "").strip()
    email = (os.getenv("VAPID_EMAIL") or "").strip()

    has_private = bool(private)
    has_public = bool(public)

    if has_private and has_public:
        status = "configured"
    elif has_private or has_public:
        status = "partial"
    else:
        status = "not_configured"

    library = "ok"
    try:
        import pywebpush  # noqa: F401
    except ImportError:
        library = "missing"

    payload: dict[str, Any] = {
        "status": status,
        "public_key_present": has_public,
        "private_key_present": has_private,
        "contact_email_configured": bool(email),
        "library": library,
        # Public key is safe to expose; required by browsers to subscribe.
        "public_key": public or None,
    }
    if status != "configured":
        payload["note"] = (
            "Web Push is optional. Set VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY "
            "(and optionally VAPID_EMAIL) to enable outbound push; until then "
            "sends are skipped."
        )
    elif library == "missing":
        payload["note"] = "VAPID keys are set but pywebpush is not installed; push sends will fail."
    return payload
