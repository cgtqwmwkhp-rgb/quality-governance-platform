"""Twilio / outbound SMS readiness helpers (Lane 1 Ops honesty).

SMS is optional until operators set TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN.
Missing credentials must not fake a successful send; readiness only reports configuration.
"""

from __future__ import annotations

import os
from typing import Any


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def get_sms_readiness() -> dict[str, Any]:
    """Return outbound SMS configuration status without secrets.

    Status values:
    - ``configured``: Twilio SID + auth token present (and SMS_ENABLED not false)
    - ``misconfigured``: SMS_ENABLED true but Twilio credentials missing
    - ``disabled``: SMS_ENABLED explicitly false
    - ``not_configured``: credentials absent and not explicitly enabled
    """
    sms_enabled_raw = os.getenv("SMS_ENABLED")
    sms_enabled = _truthy(sms_enabled_raw) if sms_enabled_raw is not None else None
    account_sid = (os.getenv("TWILIO_ACCOUNT_SID") or "").strip()
    auth_token = (os.getenv("TWILIO_AUTH_TOKEN") or "").strip()
    from_number = (os.getenv("TWILIO_FROM_NUMBER") or "").strip()

    credentials_present = bool(account_sid and auth_token)

    if sms_enabled is False:
        status = "disabled"
    elif sms_enabled is True and not credentials_present:
        status = "misconfigured"
    elif credentials_present:
        status = "configured"
    else:
        status = "not_configured"

    library = "ok"
    try:
        import twilio  # noqa: F401
    except ImportError:
        library = "missing"

    payload: dict[str, Any] = {
        "status": status,
        "sms_enabled": bool(credentials_present) if sms_enabled is None else sms_enabled,
        "sms_configured": credentials_present,
        "twilio_account_sid_present": bool(account_sid),
        "twilio_auth_token_present": bool(auth_token),
        "twilio_from_number_present": bool(from_number),
        "library": library,
    }

    if status == "misconfigured":
        payload["note"] = (
            "SMS_ENABLED is true but TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN are missing. "
            "Outbound SMS will not send until Key Vault / App Settings provide Twilio credentials."
        )
    elif status == "not_configured":
        payload["note"] = (
            "Outbound SMS is not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
            "and TWILIO_FROM_NUMBER (Key Vault refs preferred)."
        )
    elif status == "disabled":
        payload["note"] = "SMS_ENABLED=false; outbound SMS is explicitly disabled."
    elif status == "configured" and library == "missing":
        payload["note"] = "Twilio credentials are set but the twilio package is not installed; SMS sends will fail."
    elif status == "configured" and not from_number:
        payload["note"] = (
            "Twilio credentials are present but TWILIO_FROM_NUMBER is unset; "
            "sends may fail until a from-number is configured."
        )
    return payload
