"""PagerDuty Events API v2 enqueue client (Path-to-10 S12 Ops).

Env-driven. Never invents a routing key — absent key returns
``not_configured`` rather than a fake successful send. When a routing
key *is* set, send failures raise (fail-closed).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_EVENTS_API_URL = "https://events.pagerduty.com/v2/enqueue"

# In-process last enqueue outcome for /readyz fail-closed signalling.
_last_enqueue: dict[str, Any] = {
    "status": "never",
    "error": None,
    "at": None,
    "http_status": None,
}


class PagerDutySendError(Exception):
    """Raised when PAGERDUTY_ROUTING_KEY is set but the Events API enqueue fails."""


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def get_events_api_url() -> str:
    """Return configured Events API URL or the public v2 enqueue default."""
    return (os.getenv("PAGERDUTY_EVENTS_API_URL") or "").strip() or DEFAULT_EVENTS_API_URL


def get_routing_key() -> str | None:
    """Return routing key if present; never invent one."""
    key = (os.getenv("PAGERDUTY_ROUTING_KEY") or "").strip()
    return key or None


def is_enabled() -> bool:
    return _truthy(os.getenv("PAGERDUTY_ENABLED"))


def get_last_enqueue_status() -> dict[str, Any]:
    """Return last enqueue outcome without secrets (for readiness)."""
    return dict(_last_enqueue)


def reset_last_enqueue_status() -> None:
    """Test helper: clear in-process last-enqueue state."""
    _last_enqueue.update({"status": "never", "error": None, "at": None, "http_status": None})


def _record(status: str, *, error: str | None = None, http_status: int | None = None) -> None:
    _last_enqueue.update(
        {
            "status": status,
            "error": error,
            "at": datetime.now(timezone.utc).isoformat(),
            "http_status": http_status,
        }
    )


def should_fail_readiness() -> bool:
    """True when a routing key is configured and the last enqueue failed.

    Missing key stays non-fatal (honest not_configured). Fail-closed only
    applies after a real send attempt failed while a key was present.
    """
    if not get_routing_key():
        return False
    return _last_enqueue.get("status") == "failed"


def enqueue_event(
    *,
    summary: str,
    severity: str = "error",
    source: str = "quality-governance-platform",
    dedup_key: str | None = None,
    event_action: str = "trigger",
    custom_details: dict[str, Any] | None = None,
    client: str | None = None,
    client_url: str | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """POST an event to PagerDuty Events API v2.

    - No routing key → ``{"status": "not_configured"}`` (no HTTP call, no fake success).
    - Routing key set + HTTP/network/non-2xx → record failure and raise ``PagerDutySendError``.
    - Routing key set + 2xx → record success and return enqueue metadata (no secrets).
    """
    routing_key = get_routing_key()
    if not routing_key:
        _record("not_configured")
        logger.info("PagerDuty enqueue skipped: PAGERDUTY_ROUTING_KEY not configured")
        return {
            "status": "not_configured",
            "reason": "PAGERDUTY_ROUTING_KEY not set",
        }

    url = get_events_api_url()
    payload: dict[str, Any] = {
        "routing_key": routing_key,
        "event_action": event_action,
        "payload": {
            "summary": summary[:1024],
            "severity": severity,
            "source": source,
        },
    }
    if dedup_key:
        payload["dedup_key"] = dedup_key[:255]
    if custom_details:
        payload["payload"]["custom_details"] = custom_details
    if client:
        payload["client"] = client
    if client_url:
        payload["client_url"] = client_url

    try:
        with httpx.Client(timeout=timeout_seconds) as http:
            response = http.post(url, json=payload)
    except httpx.HTTPError as exc:
        msg = f"PagerDuty Events API network error: {exc}"
        _record("failed", error=msg)
        logger.error("PagerDuty enqueue failed (network)")
        raise PagerDutySendError(msg) from exc

    body_snippet = (response.text or "")[:300]
    if response.status_code < 200 or response.status_code >= 300:
        msg = f"PagerDuty Events API HTTP {response.status_code}: {body_snippet}"
        _record("failed", error=msg, http_status=response.status_code)
        logger.error("PagerDuty enqueue failed HTTP %s", response.status_code)
        raise PagerDutySendError(msg)

    dedup_out: str | None = None
    try:
        body = response.json()
        if isinstance(body, dict):
            dedup_out = body.get("dedup_key")
    except Exception:
        body = None

    _record("enqueued", http_status=response.status_code)
    logger.info(
        "PagerDuty event enqueued",
        extra={"event_action": event_action, "http_status": response.status_code},
    )
    return {
        "status": "enqueued",
        "event_action": event_action,
        "http_status": response.status_code,
        "dedup_key": dedup_out or dedup_key,
        "enabled": is_enabled(),
    }
