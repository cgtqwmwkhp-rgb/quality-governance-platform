"""DB-backed Idempotency-Key helpers for create endpoints (PX-001).

Complements Redis ``IdempotencyMiddleware``:
- Claims the key before the create mutates data (prevents concurrent duplicates)
- Persists key → entity_id so retries after client timeout return the same 201 body
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import IdempotencyConflictError
from src.domain.models.api_idempotency import ApiIdempotencyKey

logger = logging.getLogger(__name__)

SCOPE_INCIDENT_CREATE = "incident.create"
SCOPE_NEAR_MISS_CREATE = "near_miss.create"
SCOPE_RTA_CREATE = "rta.create"

_STATUS_PROCESSING = "processing"
_STATUS_COMPLETED = "completed"

# How long a concurrent retry waits for the original create to finish.
_REPLAY_POLL_ATTEMPTS = 25
_REPLAY_POLL_INTERVAL_S = 0.2


@dataclass(frozen=True)
class IdempotencyOutcome:
    """Result of claiming an idempotency key."""

    is_replay: bool
    entity_id: Optional[int]
    record_id: Optional[int]


def normalize_tenant_id(tenant_id: int | None) -> int:
    """Map optional tenant to a non-null unique-constraint key (0 = none)."""
    return int(tenant_id) if tenant_id is not None else 0


def hash_payload(payload: Any) -> str:
    """Canonical SHA-256 of a JSON-serialisable create payload."""
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(mode="json")
    else:
        data = payload
    encoded = json.dumps(data, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def _get_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    scope: str,
    idempotency_key: str,
) -> ApiIdempotencyKey | None:
    result = await db.execute(
        select(ApiIdempotencyKey).where(
            ApiIdempotencyKey.tenant_id == tenant_id,
            ApiIdempotencyKey.scope == scope,
            ApiIdempotencyKey.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


def _assert_payload_match(record: ApiIdempotencyKey, payload_hash: str, idempotency_key: str) -> None:
    if record.payload_hash != payload_hash:
        raise IdempotencyConflictError(
            "Idempotency key conflict: request payload differs from original request",
            details={"idempotency_key": idempotency_key},
        )


async def _wait_for_completion(
    db: AsyncSession,
    *,
    tenant_id: int,
    scope: str,
    idempotency_key: str,
    payload_hash: str,
) -> IdempotencyOutcome:
    """Poll until the in-flight create completes (timeout-retry race)."""
    for _ in range(_REPLAY_POLL_ATTEMPTS):
        await asyncio.sleep(_REPLAY_POLL_INTERVAL_S)
        record = await _get_record(
            db,
            tenant_id=tenant_id,
            scope=scope,
            idempotency_key=idempotency_key,
        )
        if record is None:
            continue
        _assert_payload_match(record, payload_hash, idempotency_key)
        if record.status == _STATUS_COMPLETED and record.entity_id is not None:
            return IdempotencyOutcome(is_replay=True, entity_id=record.entity_id, record_id=record.id)

    raise IdempotencyConflictError(
        "Idempotency key is still processing; retry shortly",
        details={"idempotency_key": idempotency_key},
    )


async def begin_idempotent_create(
    db: AsyncSession,
    *,
    tenant_id: int | None,
    scope: str,
    idempotency_key: str | None,
    payload: Any,
) -> IdempotencyOutcome | None:
    """Claim an Idempotency-Key or return a completed replay.

    Returns ``None`` when the client did not send a key (opt-in).
    """
    if not idempotency_key:
        return None

    key = idempotency_key.strip()
    if not key:
        return None
    if len(key) > 255:
        key = key[:255]

    tid = normalize_tenant_id(tenant_id)
    payload_hash = hash_payload(payload)

    existing = await _get_record(db, tenant_id=tid, scope=scope, idempotency_key=key)
    if existing is not None:
        _assert_payload_match(existing, payload_hash, key)
        if existing.status == _STATUS_COMPLETED and existing.entity_id is not None:
            return IdempotencyOutcome(is_replay=True, entity_id=existing.entity_id, record_id=existing.id)
        return await _wait_for_completion(
            db,
            tenant_id=tid,
            scope=scope,
            idempotency_key=key,
            payload_hash=payload_hash,
        )

    record = ApiIdempotencyKey(
        tenant_id=tid,
        scope=scope,
        idempotency_key=key,
        payload_hash=payload_hash,
        status=_STATUS_PROCESSING,
    )
    try:
        async with db.begin_nested():
            db.add(record)
            await db.flush()
    except IntegrityError:
        logger.info(
            "api_idempotency_race scope=%s key=%s — waiting for winner",
            scope,
            key,
        )
        raced = await _get_record(db, tenant_id=tid, scope=scope, idempotency_key=key)
        if raced is None:
            raise IdempotencyConflictError(
                "Idempotency key conflict during concurrent create",
                details={"idempotency_key": key},
            )
        _assert_payload_match(raced, payload_hash, key)
        if raced.status == _STATUS_COMPLETED and raced.entity_id is not None:
            return IdempotencyOutcome(is_replay=True, entity_id=raced.entity_id, record_id=raced.id)
        return await _wait_for_completion(
            db,
            tenant_id=tid,
            scope=scope,
            idempotency_key=key,
            payload_hash=payload_hash,
        )

    return IdempotencyOutcome(is_replay=False, entity_id=None, record_id=record.id)


async def complete_idempotent_create(
    db: AsyncSession,
    *,
    record_id: int | None,
    entity_type: str,
    entity_id: int,
) -> None:
    """Mark a claimed key as completed with the created entity id."""
    if record_id is None:
        return
    result = await db.execute(select(ApiIdempotencyKey).where(ApiIdempotencyKey.id == record_id))
    record = result.scalar_one_or_none()
    if record is None:
        return
    record.status = _STATUS_COMPLETED
    record.entity_type = entity_type
    record.entity_id = entity_id
    record.completed_at = datetime.now(timezone.utc)
    await db.flush()
