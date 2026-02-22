"""Unit tests for IdempotencyMiddleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.middleware.idempotency import IdempotencyMiddleware


def _make_request(method="POST", headers=None, body=b'{"key": "value"}'):
    request = MagicMock()
    request.method = method
    request.headers = headers or {}
    request.body = AsyncMock(return_value=body)
    return request


class TestIdempotencyMiddleware:
    @pytest.mark.asyncio
    async def test_non_post_request_passes_through(self):
        middleware = IdempotencyMiddleware(app=MagicMock())

        request = _make_request(method="GET")
        expected_response = MagicMock()
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        call_next.assert_awaited_once_with(request)
        assert response is expected_response

    @pytest.mark.asyncio
    async def test_post_without_key_passes_through(self):
        middleware = IdempotencyMiddleware(app=MagicMock())

        request = _make_request(method="POST", headers={})
        expected_response = MagicMock()
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        call_next.assert_awaited_once_with(request)
        assert response is expected_response
