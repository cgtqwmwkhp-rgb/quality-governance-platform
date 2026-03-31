"""Regression coverage for Celery Redis URL normalization."""

from src.infrastructure.tasks.celery_app import _normalize_redis_ssl_url


def test_normalize_redis_ssl_url_adds_ssl_requirement_for_rediss() -> None:
    url = "rediss://:secret@redis-qgp-prod.redis.cache.windows.net:6380/0"

    normalized = _normalize_redis_ssl_url(url)

    assert normalized.endswith("/0?ssl_cert_reqs=CERT_REQUIRED")


def test_normalize_redis_ssl_url_preserves_existing_ssl_requirement() -> None:
    url = "rediss://:secret@redis-qgp-prod.redis.cache.windows.net:6380/1?ssl_cert_reqs=CERT_OPTIONAL"

    normalized = _normalize_redis_ssl_url(url)

    assert normalized == url


def test_normalize_redis_ssl_url_leaves_plain_redis_unchanged() -> None:
    url = "redis://localhost:6379/0"

    normalized = _normalize_redis_ssl_url(url)

    assert normalized == url
