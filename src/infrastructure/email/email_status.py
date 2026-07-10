"""SMTP / outbound email readiness helpers (Lane 1 Ops honesty).

Email is optional until operators set EMAIL_ENABLED=true *and* SMTP credentials.
Missing SMTP must not fake a successful send; readiness only reports configuration.
"""

from __future__ import annotations

import os
from typing import Any


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def get_email_readiness() -> dict[str, Any]:
    """Return outbound email configuration status without secrets.

    Status values:
    - ``configured``: EMAIL_ENABLED and SMTP_USER + SMTP_PASSWORD present
    - ``misconfigured``: EMAIL_ENABLED but SMTP credentials missing
    - ``credentials_present``: SMTP credentials set but EMAIL_ENABLED not set
    - ``not_configured``: neither enabled nor credentials
    """
    email_enabled = _truthy(os.getenv("EMAIL_ENABLED"))
    smtp_user = (os.getenv("SMTP_USER") or "").strip()
    smtp_password = (os.getenv("SMTP_PASSWORD") or "").strip()
    smtp_host = (os.getenv("SMTP_HOST") or "smtp.office365.com").strip()
    from_email = (os.getenv("FROM_EMAIL") or "").strip()

    email_configured = bool(smtp_user and smtp_password)

    if email_enabled and email_configured:
        status = "configured"
    elif email_enabled and not email_configured:
        status = "misconfigured"
    elif email_configured:
        status = "credentials_present"
    else:
        status = "not_configured"

    payload: dict[str, Any] = {
        "status": status,
        "email_enabled": email_enabled,
        "email_configured": email_configured,
        "smtp_host_set": bool(smtp_host),
        "smtp_user_present": bool(smtp_user),
        "smtp_password_present": bool(smtp_password),
        "from_email_present": bool(from_email),
    }

    if status == "misconfigured":
        payload["note"] = (
            "EMAIL_ENABLED is true but SMTP_USER/SMTP_PASSWORD are missing. "
            "Outbound email will not send until Key Vault / App Settings provide SMTP credentials."
        )
    elif status == "not_configured":
        payload["note"] = (
            "Outbound email is not configured. Set EMAIL_ENABLED=true and SMTP_HOST, "
            "SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL (Key Vault refs preferred)."
        )
    elif status == "credentials_present":
        payload["note"] = (
            "SMTP credentials are present but EMAIL_ENABLED is not set. "
            "EmailService may still send when credentials exist; set EMAIL_ENABLED=true "
            "for explicit ops intent and smoke-gate enforcement."
        )
    return payload
