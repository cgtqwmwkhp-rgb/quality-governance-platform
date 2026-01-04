"""
Observability Middleware

Provides request ID tracking and structured logging for operational visibility.
"""

import json
import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Configure structured logging
logger = logging.getLogger("quality_governance")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds request IDs and structured logging to all requests.

    Features:
    - Generates or accepts X-Request-ID header
    - Includes request ID in response headers
    - Logs request/response with structured data (JSON-compatible format)
    - Tracks request duration
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and add observability data."""
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store request ID in request state for access in route handlers
        request.state.request_id = request_id

        # Record start time
        start_time = time.time()

        # Process request
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Structured log entry
            log_data = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            }

            # Log as structured key=value pairs (JSON-compatible)
            logger.info(
                f"request_id={log_data['request_id']} "
                f"method={log_data['method']} "
                f"path={log_data['path']} "
                f"status_code={log_data['status_code']} "
                f"duration_ms={log_data['duration_ms']}"
            )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Log error with structured data
            logger.error(
                f"request_id={request_id} "
                f"method={request.method} "
                f"path={request.url.path} "
                f"error={str(e)} "
                f"duration_ms={round(duration_ms, 2)}"
            )
            raise


def configure_structured_logging() -> None:
    """
    Configure structured logging for the application.

    Sets up logging format to be JSON-compatible with key=value pairs.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
