"""Unit tests for the idempotency middleware.

Tests helper functions, payload hashing, key generation,
and dispatch logic with mocked Redis/request/response objects.
"""

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.middleware.idempotency import _IDEMPOTENT_METHODS, IdempotencyMiddleware, _compute_payload_hash, _make_key

# =========================================================================
# Pure helper functions
# =========================================================================


class TestComputePayloadHash:
    def test_empty_body(self):
        result = _compute_payload_hash(b"")
        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected

    def test_deterministic(self):
        body = b'{"key": "value"}'
        assert _compute_payload_hash(body) == _compute_payload_hash(body)

    def test_different_payloads_differ(self):
        h1 = _compute_payload_hash(b'{"a": 1}')
        h2 = _compute_payload_hash(b'{"a": 2}')
        assert h1 != h2

    def test_returns_hex_string(self):
        result = _compute_payload_hash(b"test")
        assert all(c in "0123456789abcdef" for c in result)
        assert len(result) == 64


class TestMakeKey:
    _FP = "abcd1234abcd1234"
    _METHOD = "POST"
    _PATH = "/api/v1/incidents/"

    def test_prefix(self):
        assert _make_key("abc", self._FP, self._METHOD, self._PATH).startswith("idem:")

    def test_deterministic(self):
        k1 = _make_key("my-key", self._FP, self._METHOD, self._PATH)
        k2 = _make_key("my-key", self._FP, self._METHOD, self._PATH)
        assert k1 == k2

    def test_empty_key_does_not_raise(self):
        key = _make_key("", self._FP, self._METHOD, self._PATH)
        assert key.startswith("idem:")


class TestIdempotentMethods:
    def test_includes_post(self):
        assert "POST" in _IDEMPOTENT_METHODS

    def test_includes_put(self):
        assert "PUT" in _IDEMPOTENT_METHODS

    def test_includes_patch(self):
        assert "PATCH" in _IDEMPOTENT_METHODS

    def test_excludes_get(self):
        assert "GET" not in _IDEMPOTENT_METHODS

    def test_excludes_delete(self):
        assert "DELETE" not in _IDEMPOTENT_METHODS


# =========================================================================
# Middleware dispatch
# =========================================================================


def _make_request(method="POST", headers=None, body=b"{}"):
    req = MagicMock()
    req.method = method
    req.headers = headers or {}
    req.body = AsyncMock(return_value=body)
    return req


class TestMiddlewareDispatchNonIdempotent:
    @pytest.mark.asyncio
    async def test_get_passes_through(self):
        mw = IdempotencyMiddleware(app=MagicMock())
        call_next = AsyncMock(return_value=MagicMock())
        request = _make_request(method="GET")

        result = await mw.dispatch(request, call_next)
        call_next.assert_awaited_once_with(request)

    @pytest.mark.asyncio
    async def test_delete_passes_through(self):
        mw = IdempotencyMiddleware(app=MagicMock())
        call_next = AsyncMock(return_value=MagicMock())
        request = _make_request(method="DELETE")

        result = await mw.dispatch(request, call_next)
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_options_passes_through(self):
        mw = IdempotencyMiddleware(app=MagicMock())
        call_next = AsyncMock(return_value=MagicMock())
        request = _make_request(method="OPTIONS")

        await mw.dispatch(request, call_next)
        call_next.assert_awaited_once()


class TestMiddlewareNoKey:
    @pytest.mark.asyncio
    async def test_post_without_key_passes_through(self):
        mw = IdempotencyMiddleware(app=MagicMock())
        call_next = AsyncMock(return_value=MagicMock())
        request = _make_request(method="POST", headers={})

        await mw.dispatch(request, call_next)
        call_next.assert_awaited_once()


class TestMiddlewareRedisUnavailable:
    @pytest.mark.asyncio
    @patch("src.api.middleware.idempotency._get_redis", new_callable=AsyncMock, return_value=None)
    async def test_falls_back_when_redis_unavailable(self, mock_redis):
        mw = IdempotencyMiddleware(app=MagicMock())
        call_next = AsyncMock(return_value=MagicMock())
        request = _make_request(headers={"Idempotency-Key": "test-key"})

        await mw.dispatch(request, call_next)
        call_next.assert_awaited_once()


class TestMiddlewareCacheHit:
    @pytest.mark.asyncio
    @patch("src.api.middleware.idempotency._get_redis")
    async def test_returns_cached_response_on_match(self, mock_get_redis):
        body = b'{"data": 1}'
        payload_hash = _compute_payload_hash(body)
        cached = json.dumps(
            {
                "body": '{"result": "ok"}',
                "status_code": 200,
                "headers": {"content-type": "application/json"},
                "payload_hash": payload_hash,
            }
        ).encode("utf-8")

        redis_mock = AsyncMock()
        redis_mock.get.return_value = cached
        mock_get_redis.return_value = redis_mock

        mw = IdempotencyMiddleware(app=MagicMock())
        call_next = AsyncMock()
        request = _make_request(headers={"Idempotency-Key": "key-1"}, body=body)

        response = await mw.dispatch(request, call_next)
        call_next.assert_not_awaited()
        assert response.status_code == 200

    @pytest.mark.asyncio
    @patch("src.api.middleware.idempotency._get_redis")
    async def test_returns_409_on_payload_mismatch(self, mock_get_redis):
        cached = json.dumps(
            {
                "body": "old",
                "status_code": 200,
                "headers": {},
                "payload_hash": "different-hash",
            }
        ).encode("utf-8")

        redis_mock = AsyncMock()
        redis_mock.get.return_value = cached
        mock_get_redis.return_value = redis_mock

        mw = IdempotencyMiddleware(app=MagicMock())
        call_next = AsyncMock()
        request = _make_request(headers={"Idempotency-Key": "key-2"}, body=b'{"new": true}')

        response = await mw.dispatch(request, call_next)
        assert response.status_code == 409
        content = json.loads(response.body)
        assert content["error"]["code"] == "IDEMPOTENCY_CONFLICT"


class TestMiddlewareCacheMiss:
    @pytest.mark.asyncio
    @patch("src.api.middleware.idempotency._get_redis")
    async def test_caches_new_response(self, mock_get_redis):
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None
        mock_get_redis.return_value = redis_mock

        response_body = b'{"created": true}'
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = MagicMock()
        mock_response.headers.items.return_value = [("content-type", "application/json")]

        async def body_iter():
            yield response_body

        mock_response.body_iterator = body_iter()

        mw = IdempotencyMiddleware(app=MagicMock())
        call_next = AsyncMock(return_value=mock_response)
        request = _make_request(headers={"Idempotency-Key": "key-3"})

        result = await mw.dispatch(request, call_next)
        redis_mock.setex.assert_awaited_once()
        assert result.status_code == 201


class TestMiddlewareRedisError:
    @pytest.mark.asyncio
    @patch("src.api.middleware.idempotency._get_redis")
    async def test_graceful_fallback_on_redis_read_error(self, mock_get_redis):
        redis_mock = AsyncMock()
        redis_mock.get.side_effect = Exception("Connection lost")
        mock_get_redis.return_value = redis_mock

        response_body = b'{"ok": true}'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = MagicMock()
        mock_response.headers.items.return_value = []

        async def body_iter():
            yield response_body

        mock_response.body_iterator = body_iter()

        mw = IdempotencyMiddleware(app=MagicMock())
        call_next = AsyncMock(return_value=mock_response)
        request = _make_request(headers={"Idempotency-Key": "key-err"})

        result = await mw.dispatch(request, call_next)
        call_next.assert_awaited_once()
