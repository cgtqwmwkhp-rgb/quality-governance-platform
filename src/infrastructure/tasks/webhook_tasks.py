"""Async outbound webhook delivery tasks."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 30.0
_MAX_ATTEMPTS = 4  # initial try + up to 3 retries


class WebhookClientError(Exception):
    """Non-retryable webhook failure (missing URL, 4xx, invalid config)."""


class WebhookServerError(Exception):
    """Retryable webhook failure (network / timeout / 5xx)."""


def _normalize_headers(headers: Optional[dict[str, Any]]) -> dict[str, str]:
    if not headers:
        return {"Content-Type": "application/json", "Accept": "application/json"}
    normalized = {str(k): str(v) for k, v in headers.items()}
    normalized.setdefault("Content-Type", "application/json")
    normalized.setdefault("Accept", "application/json")
    return normalized


def _build_payload(
    *,
    entity_type: str,
    entity_id: int,
    body: Optional[dict[str, Any]],
    payload: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Merge entity context with optional config body/payload."""
    merged: dict[str, Any] = {
        "entity_type": entity_type,
        "entity_id": entity_id,
    }
    if isinstance(body, dict):
        merged.update(body)
    if isinstance(payload, dict):
        merged.update(payload)
    return merged


def _deliver_webhook(
    *,
    url: str,
    method: str,
    headers: dict[str, str],
    json_body: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """Perform a single HTTP webhook call. Raises typed errors for retry policy."""
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(method=method.upper(), url=url, headers=headers, json=json_body)
    except httpx.TimeoutException as exc:
        raise WebhookServerError(f"Webhook timeout calling {url}: {exc}") from exc
    except httpx.NetworkError as exc:
        raise WebhookServerError(f"Webhook network error calling {url}: {exc}") from exc
    except httpx.HTTPError as exc:
        raise WebhookServerError(f"Webhook HTTP error calling {url}: {exc}") from exc

    status = response.status_code
    snippet = (response.text or "")[:500]

    if 200 <= status < 300:
        return {
            "status": "delivered",
            "url": url,
            "method": method.upper(),
            "status_code": status,
        }

    if 400 <= status < 500:
        raise WebhookClientError(f"Webhook client error {status} for {url}: {snippet}")

    raise WebhookServerError(f"Webhook server error {status} for {url}: {snippet}")


@celery_app.task(
    name="src.infrastructure.tasks.webhook_tasks.deliver_webhook",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(WebhookServerError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    queue="default",
)
def deliver_webhook(
    self,
    url: str,
    method: str = "POST",
    headers: Optional[dict[str, Any]] = None,
    entity_type: str = "",
    entity_id: int = 0,
    body: Optional[dict[str, Any]] = None,
    payload: Optional[dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> dict[str, Any]:
    """Deliver a workflow webhook with retries on network/5xx; no retry on 4xx."""
    if not url:
        raise WebhookClientError("Webhook URL is required")

    timeout_seconds = float(timeout) if timeout is not None else _DEFAULT_TIMEOUT_SECONDS
    request_headers = _normalize_headers(headers)
    json_body = _build_payload(
        entity_type=entity_type,
        entity_id=entity_id,
        body=body,
        payload=payload,
    )

    try:
        result = _deliver_webhook(
            url=url,
            method=method or "POST",
            headers=request_headers,
            json_body=json_body,
            timeout=timeout_seconds,
        )
        logger.info(
            "Webhook delivered method=%s url=%s status_code=%s entity=%s#%s",
            result["method"],
            url,
            result["status_code"],
            entity_type,
            entity_id,
        )
        return {
            **result,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "attempt": self.request.retries + 1,
            "max_attempts": _MAX_ATTEMPTS,
        }
    except WebhookClientError as exc:
        logger.error(
            "Webhook non-retryable failure method=%s url=%s entity=%s#%s error=%s",
            (method or "POST").upper(),
            url,
            entity_type,
            entity_id,
            exc,
        )
        return {
            "status": "failed",
            "retryable": False,
            "url": url,
            "method": (method or "POST").upper(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "error": str(exc),
            "attempt": self.request.retries + 1,
            "max_attempts": _MAX_ATTEMPTS,
        }
    except WebhookServerError as exc:
        logger.warning(
            "Webhook retryable failure method=%s url=%s entity=%s#%s attempt=%s error=%s",
            (method or "POST").upper(),
            url,
            entity_type,
            entity_id,
            self.request.retries + 1,
            exc,
        )
        raise


def _finalize_partner_delivery_log(
    *,
    delivery_log_id: int,
    status: str,
    http_status: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    """Update partner webhook delivery log after HTTP attempt (sync Celery worker)."""
    from datetime import datetime, timezone

    from src.domain.models.partner_webhook import WebhookDeliveryLog, WebhookDeliveryStatus
    from src.infrastructure.database import SessionLocal

    now = datetime.now(timezone.utc)
    delivery_status = WebhookDeliveryStatus(status)

    with SessionLocal() as session:
        log = session.get(WebhookDeliveryLog, delivery_log_id)
        if log is None:
            logger.error("Partner delivery log %s not found for finalize", delivery_log_id)
            return
        log.status = delivery_status
        log.http_status = http_status
        log.error_message = error_message
        if delivery_status == WebhookDeliveryStatus.DELIVERED:
            log.delivered_at = now
        session.commit()


@celery_app.task(
    name="src.infrastructure.tasks.webhook_tasks.deliver_partner_webhook",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(WebhookServerError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    queue="default",
)
def deliver_partner_webhook(
    self,
    delivery_log_id: int,
    url: str,
    headers: Optional[dict[str, Any]] = None,
    payload: Optional[dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> dict[str, Any]:
    """Deliver a signed partner webhook with retries on network/5xx; finalize delivery log."""
    if not url:
        _finalize_partner_delivery_log(
            delivery_log_id=delivery_log_id,
            status="failed",
            error_message="Webhook URL is required",
        )
        raise WebhookClientError("Webhook URL is required")

    timeout_seconds = float(timeout) if timeout is not None else _DEFAULT_TIMEOUT_SECONDS
    request_headers = _normalize_headers(headers)
    json_body = payload if isinstance(payload, dict) else {}

    try:
        result = _deliver_webhook(
            url=url,
            method="POST",
            headers=request_headers,
            json_body=json_body,
            timeout=timeout_seconds,
        )
        _finalize_partner_delivery_log(
            delivery_log_id=delivery_log_id,
            status="delivered",
            http_status=result["status_code"],
        )
        logger.info(
            "Partner webhook delivered delivery_log_id=%s url=%s status_code=%s attempt=%s",
            delivery_log_id,
            url,
            result["status_code"],
            self.request.retries + 1,
        )
        return {
            **result,
            "delivery_log_id": delivery_log_id,
            "attempt": self.request.retries + 1,
            "max_attempts": _MAX_ATTEMPTS,
        }
    except WebhookClientError as exc:
        _finalize_partner_delivery_log(
            delivery_log_id=delivery_log_id,
            status="failed",
            error_message=str(exc),
        )
        logger.error(
            "Partner webhook non-retryable failure delivery_log_id=%s url=%s error=%s",
            delivery_log_id,
            url,
            exc,
        )
        return {
            "status": "failed",
            "retryable": False,
            "delivery_log_id": delivery_log_id,
            "url": url,
            "error": str(exc),
            "attempt": self.request.retries + 1,
            "max_attempts": _MAX_ATTEMPTS,
        }
    except WebhookServerError as exc:
        if self.request.retries >= self.max_retries:
            _finalize_partner_delivery_log(
                delivery_log_id=delivery_log_id,
                status="failed",
                error_message=str(exc),
            )
        logger.warning(
            "Partner webhook retryable failure delivery_log_id=%s url=%s attempt=%s error=%s",
            delivery_log_id,
            url,
            self.request.retries + 1,
            exc,
        )
        raise
