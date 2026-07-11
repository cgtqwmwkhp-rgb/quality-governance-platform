"""PagerDuty / on-call alerting readiness helpers (Path-to-10 S12 honesty).

PagerDuty is optional. Missing routing key must not invent a working
integration; readiness reports configuration. When a routing key *is*
present and the last Events API enqueue failed, readiness may fail closed
(see ``should_fail_readiness`` on the client).
"""

from __future__ import annotations

import os
from typing import Any

from src.infrastructure.alerting.pagerduty_client import (
    get_last_enqueue_status,
    should_fail_readiness,
)


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def get_pagerduty_readiness() -> dict[str, Any]:
    """Return PagerDuty configuration status without secrets.

    Status values:
    - ``configured``: PAGERDUTY_ENABLED and routing key present
    - ``misconfigured``: PAGERDUTY_ENABLED but routing key missing
    - ``credentials_present``: routing key set but PAGERDUTY_ENABLED not set
    - ``not_configured``: neither enabled nor routing key
    - ``send_failed``: routing key present and last Events API enqueue failed
      (overrides configured/credentials_present for channel honesty)
    """
    enabled = _truthy(os.getenv("PAGERDUTY_ENABLED"))
    routing_key = (os.getenv("PAGERDUTY_ROUTING_KEY") or "").strip()
    api_url = (os.getenv("PAGERDUTY_EVENTS_API_URL") or "").strip()

    configured = bool(routing_key)
    last = get_last_enqueue_status()
    send_failed = should_fail_readiness()

    if send_failed:
        status = "send_failed"
    elif enabled and configured:
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
        "last_enqueue_status": last.get("status"),
        "fail_closed": send_failed,
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
    elif status == "send_failed":
        payload["note"] = (
            "PAGERDUTY_ROUTING_KEY is set but the last Events API v2 enqueue failed. "
            "Readiness fails closed until a successful enqueue clears this state."
        )
        if last.get("error"):
            # Truncate; never include routing key (error strings are HTTP/network only).
            payload["last_enqueue_error"] = str(last["error"])[:200]
    return payload
