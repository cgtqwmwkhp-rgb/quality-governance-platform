"""Regression coverage for Celery Redis URL normalization."""

from src.infrastructure.tasks.celery_app import _normalize_redis_ssl_url, _redis_ssl_options


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


def test_redis_ssl_options_enable_cert_requirement_for_rediss() -> None:
    url = "rediss://:secret@redis-qgp-prod.redis.cache.windows.net:6380/1"

    assert _redis_ssl_options(url) == {"ssl_cert_reqs": "CERT_REQUIRED"}


def test_redis_ssl_options_ignore_plain_redis() -> None:
    assert _redis_ssl_options("redis://localhost:6379/1") is None
