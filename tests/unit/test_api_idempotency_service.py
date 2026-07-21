"""Unit tests for durable API idempotency (PX-001)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from src.domain.exceptions import IdempotencyConflictError
from src.domain.services.api_idempotency_service import (
    SCOPE_INCIDENT_CREATE,
    begin_idempotent_create,
    complete_idempotent_create,
    hash_payload,
    normalize_tenant_id,
)


def test_normalize_tenant_id_maps_none_to_zero():
    assert normalize_tenant_id(None) == 0
    assert normalize_tenant_id(3) == 3


def test_hash_payload_is_stable_for_model_dump():
    class _Payload:
        def model_dump(self, mode="json"):
            return {"b": 2, "a": 1}

    assert hash_payload(_Payload()) == hash_payload({"a": 1, "b": 2})


@pytest.mark.asyncio
async def test_begin_without_key_is_noop():
    db = AsyncMock()
    assert (
        await begin_idempotent_create(db, tenant_id=1, scope=SCOPE_INCIDENT_CREATE, idempotency_key=None, payload={})
        is None
    )
    assert (
        await begin_idempotent_create(db, tenant_id=1, scope=SCOPE_INCIDENT_CREATE, idempotency_key="  ", payload={})
        is None
    )
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_begin_claims_new_key():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))

    nested = AsyncMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=None)
    db.begin_nested = MagicMock(return_value=nested)
    db.add = MagicMock()

    async def _flush():
        added = db.add.call_args.args[0]
        added.id = 42

    db.flush = AsyncMock(side_effect=_flush)

    outcome = await begin_idempotent_create(
        db,
        tenant_id=9,
        scope=SCOPE_INCIDENT_CREATE,
        idempotency_key="k-1",
        payload={"title": "t"},
    )
    assert outcome is not None
    assert outcome.is_replay is False
    assert outcome.record_id == 42
    db.add.assert_called_once()
    added = db.add.call_args.args[0]
    assert added.tenant_id == 9
    assert added.scope == SCOPE_INCIDENT_CREATE
    assert added.idempotency_key == "k-1"
    assert added.status == "processing"


@pytest.mark.asyncio
async def test_begin_replays_completed_key():
    existing = SimpleNamespace(
        id=5,
        payload_hash=hash_payload({"title": "same"}),
        status="completed",
        entity_id=77,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: existing))

    outcome = await begin_idempotent_create(
        db,
        tenant_id=1,
        scope=SCOPE_INCIDENT_CREATE,
        idempotency_key="replay-me",
        payload={"title": "same"},
    )
    assert outcome is not None
    assert outcome.is_replay is True
    assert outcome.entity_id == 77
    assert outcome.record_id == 5


@pytest.mark.asyncio
async def test_begin_conflict_on_payload_mismatch():
    existing = SimpleNamespace(
        id=5,
        payload_hash="deadbeef",
        status="completed",
        entity_id=77,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: existing))

    with pytest.raises(IdempotencyConflictError):
        await begin_idempotent_create(
            db,
            tenant_id=1,
            scope=SCOPE_INCIDENT_CREATE,
            idempotency_key="bad-payload",
            payload={"title": "different"},
        )


@pytest.mark.asyncio
async def test_begin_waits_when_processing_then_replays():
    processing = SimpleNamespace(
        id=5,
        payload_hash=hash_payload({"title": "x"}),
        status="processing",
        entity_id=None,
    )
    completed = SimpleNamespace(
        id=5,
        payload_hash=hash_payload({"title": "x"}),
        status="completed",
        entity_id=88,
    )
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalar_one_or_none=lambda: processing),
            SimpleNamespace(scalar_one_or_none=lambda: completed),
        ]
    )

    with patch("src.domain.services.api_idempotency_service._REPLAY_POLL_INTERVAL_S", 0):
        outcome = await begin_idempotent_create(
            db,
            tenant_id=1,
            scope=SCOPE_INCIDENT_CREATE,
            idempotency_key="wait-key",
            payload={"title": "x"},
        )

    assert outcome is not None
    assert outcome.is_replay is True
    assert outcome.entity_id == 88


@pytest.mark.asyncio
async def test_begin_integrity_error_races_to_completed():
    completed = SimpleNamespace(
        id=9,
        payload_hash=hash_payload({"title": "race"}),
        status="completed",
        entity_id=101,
    )
    db = AsyncMock()
    # First lookup miss, then after IntegrityError lookup hits completed
    db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalar_one_or_none=lambda: None),
            SimpleNamespace(scalar_one_or_none=lambda: completed),
        ]
    )

    class _Nested:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def _flush():
        raise IntegrityError("dup", {}, Exception("unique"))

    db.begin_nested = MagicMock(return_value=_Nested())
    db.add = MagicMock()
    db.flush = AsyncMock(side_effect=_flush)

    outcome = await begin_idempotent_create(
        db,
        tenant_id=1,
        scope=SCOPE_INCIDENT_CREATE,
        idempotency_key="race-key",
        payload={"title": "race"},
    )
    assert outcome is not None
    assert outcome.is_replay is True
    assert outcome.entity_id == 101


@pytest.mark.asyncio
async def test_complete_idempotent_create_sets_entity():
    record = SimpleNamespace(id=3, status="processing", entity_type=None, entity_id=None, completed_at=None)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: record))
    db.flush = AsyncMock()

    await complete_idempotent_create(db, record_id=3, entity_type="incident", entity_id=55)
    assert record.status == "completed"
    assert record.entity_type == "incident"
    assert record.entity_id == 55
    assert record.completed_at is not None
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_noop_without_record_id():
    db = AsyncMock()
    await complete_idempotent_create(db, record_id=None, entity_type="incident", entity_id=1)
    db.execute.assert_not_awaited()
