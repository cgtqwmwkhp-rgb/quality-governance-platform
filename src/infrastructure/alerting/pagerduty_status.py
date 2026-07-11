"""PagerDuty / on-call alerting readiness helpers (Path-to-10 S12 honesty).

PagerDuty is optional. Missing routing key must not invent a working
integration; readiness only reports configuration. Never fails readiness.
"""

from __future__ import annotations

import os
from typing import Any


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def get_pagerduty_readiness() -> dict[str, Any]:
    """Return PagerDuty configuration status without secrets.

    Status values:
    - ``configured``: PAGERDUTY_ENABLED and routing key present
    - ``misconfigured``: PAGERDUTY_ENABLED but routing key missing
    - ``credentials_present``: routing key set but PAGERDUTY_ENABLED not set
    - ``not_configured``: neither enabled nor routing key
    """
    enabled = _truthy(os.getenv("PAGERDUTY_ENABLED"))
    routing_key = (os.getenv("PAGERDUTY_ROUTING_KEY") or "").strip()
    api_url = (os.getenv("PAGERDUTY_EVENTS_API_URL") or "").strip()

    configured = bool(routing_key)

    if enabled and configured:
        status = "configured"
    elif enabled and not configured:
        status = "misconfigured"
    elif configured:
        status = "credentials_present"
    else:
        status = "not_configured"

    payload: dict[str, Any] = {
        "status": status,
        "pagerduty_enabled": enabled,
        "pagerduty_configured": configured,
        "routing_key_present": bool(routing_key),
        "events_api_url_set": bool(api_url),
    }

    if status == "misconfigured":
        payload["note"] = (
            "PAGERDUTY_ENABLED is true but PAGERDUTY_ROUTING_KEY is missing. "
            "On-call Events API alerts will not send until Key Vault / App Settings "
            "provide a routing key."
        )
    elif status == "not_configured":
        payload["note"] = (
            "PagerDuty is not configured. Set PAGERDUTY_ENABLED=true and "
            "PAGERDUTY_ROUTING_KEY (Key Vault refs preferred) when Events API "
            "alerting is required."
        )
    elif status == "credentials_present":
        payload["note"] = (
            "PAGERDUTY_ROUTING_KEY is present but PAGERDUTY_ENABLED is not set. "
            "Set PAGERDUTY_ENABLED=true for explicit ops intent before enabling sends."
        )
    return payload
