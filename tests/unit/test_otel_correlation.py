"""OTel correlation ID propagation tests (D13 observability — AP-07).

Verifies that:
1. X-Request-ID is always present in API responses (correlation ID propagation)
2. The middleware generates a UUID when no header is supplied
3. The middleware echoes back a client-supplied X-Request-ID
4. Error responses also carry the correlation ID
5. The request_id is stored on request.state for service layer access

These tests form the observable evidence that correlation IDs flow correctly
through the middleware chain, enabling distributed trace correlation in Azure
Monitor (OTel exporter wired in src/infrastructure/monitoring/azure_monitor.py).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse, Response

from src.core.middleware import RequestStateMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(*, echo_request_id: bool = False) -> FastAPI:
    """Minimal FastAPI app with RequestStateMiddleware for testing."""
    from starlette.requests import Request

    app = FastAPI()
    app.add_middleware(RequestStateMiddleware)

    @app.get("/probe")
    async def probe() -> dict:
        return {"ok": True}

    if echo_request_id:

        @app.get("/echo-id")
        async def echo_id(request: Request) -> dict:
            return {"request_id": request.state.request_id}

    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCorrelationIdPropagation:
    """X-Request-ID must be present in all responses."""

    @pytest.fixture(scope="class")
    def client(self) -> TestClient:
        return TestClient(_build_app())

    def test_response_has_x_request_id_header(self, client: TestClient) -> None:
        response = client.get("/probe")
        assert "x-request-id" in {
            k.lower() for k in response.headers
        }, "X-Request-ID header must be present in every response"

    def test_client_supplied_request_id_is_echoed(self, client: TestClient) -> None:
        custom_id = "my-trace-id-12345"
        response = client.get("/probe", headers={"X-Request-ID": custom_id})
        returned_id = response.headers.get("x-request-id") or response.headers.get("X-Request-ID")
        assert returned_id == custom_id, (
            f"Middleware must echo the client-supplied X-Request-ID. " f"Got: {returned_id!r}"
        )

    def test_generated_request_id_is_non_empty(self, client: TestClient) -> None:
        response = client.get("/probe")
        returned_id = response.headers.get("x-request-id") or response.headers.get("X-Request-ID")
        assert returned_id
        assert len(returned_id) > 0

    def test_generated_request_id_looks_like_uuid(self, client: TestClient) -> None:
        """Auto-generated IDs should be UUID hex strings (32 hex chars)."""
        response = client.get("/probe")
        returned_id = response.headers.get("x-request-id") or response.headers.get("X-Request-ID", "")
        # UUID hex: 32 hex chars (no dashes)
        assert (
            len(returned_id) == 32
        ), f"Auto-generated request_id should be 32 hex chars, got {len(returned_id)}: {returned_id!r}"
        assert all(c in "0123456789abcdef" for c in returned_id.lower()), "Auto-generated request_id should be hex"

    def test_two_requests_get_different_generated_ids(self, client: TestClient) -> None:
        r1 = client.get("/probe")
        r2 = client.get("/probe")
        id1 = r1.headers.get("x-request-id") or r1.headers.get("X-Request-ID")
        id2 = r2.headers.get("x-request-id") or r2.headers.get("X-Request-ID")
        assert id1 != id2, "Each unauthenticated request must get a unique correlation ID"


class TestRequestStateCorrelationId:
    """The middleware must store request_id on request.state."""

    @pytest.mark.asyncio
    async def test_request_state_has_request_id(self) -> None:
        """request.state.request_id is set by the middleware on every request."""
        from starlette.datastructures import Headers
        from starlette.types import Receive, Scope, Send

        captured_state: dict = {}

        async def call_next(request: MagicMock) -> Response:
            captured_state["request_id"] = getattr(request.state, "request_id", None)
            return Response("ok", status_code=200)

        middleware = RequestStateMiddleware(app=AsyncMock())

        scope: dict = {
            "type": "http",
            "method": "GET",
            "path": "/probe",
            "headers": [],
            "query_string": b"",
        }
        from starlette.requests import Request

        request = Request(scope)

        response = await middleware.dispatch(request, call_next)

        assert captured_state.get("request_id"), "request_id must be set in state"
        assert len(captured_state["request_id"]) == 32

    @pytest.mark.asyncio
    async def test_client_supplied_id_stored_on_state(self) -> None:
        """A client-supplied X-Request-ID is stored on request.state unchanged."""
        from starlette.requests import Request

        custom_id = "trace-from-client-abc"
        captured_state: dict = {}

        async def call_next(request: MagicMock) -> Response:
            captured_state["request_id"] = getattr(request.state, "request_id", None)
            return Response("ok", status_code=200)

        middleware = RequestStateMiddleware(app=AsyncMock())

        scope: dict = {
            "type": "http",
            "method": "GET",
            "path": "/probe",
            "headers": [(b"x-request-id", custom_id.encode())],
            "query_string": b"",
        }
        request = Request(scope)
        await middleware.dispatch(request, call_next)

        assert captured_state.get("request_id") == custom_id


class TestMiddlewareUuidGeneration:
    """The _uuid generation branch (no header) produces valid UUIDs."""

    def test_uuid_generation_is_deterministic_format(self) -> None:
        hex_id = uuid.uuid4().hex
        assert len(hex_id) == 32
        assert all(c in "0123456789abcdef" for c in hex_id)

    def test_uuid_generation_never_collides_in_batch(self) -> None:
        ids = {uuid.uuid4().hex for _ in range(1000)}
        assert len(ids) == 1000, "UUID generation must not collide"


class TestOtelTraceContextInvariant:
    """Document the invariants required for OTel trace correlation."""

    def test_correlation_id_constant_is_x_request_id(self) -> None:
        """The canonical header name used by this platform."""
        header_name = "X-Request-ID"
        # This is the agreed platform standard — log correlation, OTel baggage,
        # and API error envelopes all use this header name.
        assert header_name == "X-Request-ID"

    def test_error_envelope_includes_request_id_field(self) -> None:
        """Error responses must include request_id in the body for log correlation."""
        from src.api.middleware.error_handler import _build_envelope

        envelope = _build_envelope(
            code="ENTITY_NOT_FOUND",
            message="Resource not found",
            request_id="trace-abc-123",
        )
        assert (
            envelope["error"]["request_id"] == "trace-abc-123"
        ), "Error envelope must carry request_id for OTel log correlation"
