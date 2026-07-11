"""Path-to-10 S10: Redis/Celery upstream readiness honesty."""

from unittest.mock import AsyncMock

import pytest

from src.infrastructure.upstream import celery_status
from src.infrastructure.upstream.celery_status import get_upstream_celery_readiness


@pytest.mark.asyncio
async def test_celery_not_configured_when_broker_and_redis_missing(monkeypatch):
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)

    result = await get_upstream_celery_readiness()

    assert result["status"] == "not_configured"
    assert result["broker_url_present"] is False
    assert result["redis_url_present"] is False
    assert result["depth_status"] == "not_configured"
    assert result["workers_ping"] == "skipped"
    assert "note" in result
    assert "CELERY_BROKER_URL" in result["note"]


@pytest.mark.asyncio
async def test_celery_partial_when_only_redis_url(monkeypatch):
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid:6379/0")
    monkeypatch.setattr(
        celery_status,
        "_probe_queue_depths",
        AsyncMock(
            return_value={
                "depth_status": "ok",
                "queues": {"default": 2, "email": 0, "notifications": 1, "reports": 0, "cleanup": 0},
                "total_depth": 3,
            }
        ),
    )

    result = await get_upstream_celery_readiness()

    assert result["status"] == "partial"
    assert result["redis_url_present"] is True
    assert result["broker_url_present"] is False
    assert result["depth_status"] == "ok"
    assert result["total_depth"] == 3
    assert result["queues"]["default"] == 2
    assert "CELERY_BROKER_URL" in result.get("note", "")


@pytest.mark.asyncio
async def test_celery_configured_broker_depth_error_is_honest(monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://example.invalid:6379/1")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setattr(
        celery_status,
        "_probe_queue_depths",
        AsyncMock(
            return_value={
                "depth_status": "error",
                "queues": {},
                "total_depth": None,
                "depth_error": "TimeoutError",
            }
        ),
    )

    result = await get_upstream_celery_readiness()

    assert result["status"] == "configured"
    assert result["broker_url_present"] is True
    assert result["broker_scheme"] == "redis"
    assert result["workers_ping"] == "skipped"
    assert result["depth_status"] == "error"
    assert result["total_depth"] is None
    assert "password" not in str(result).lower()


@pytest.mark.asyncio
async def test_celery_unsupported_broker_scheme(monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "amqp://guest@localhost//")
    monkeypatch.delenv("REDIS_URL", raising=False)

    result = await get_upstream_celery_readiness()

    assert result["status"] == "configured"
    assert result["depth_status"] == "unsupported_scheme"
    assert result["total_depth"] is None
    assert "depth_note" in result
