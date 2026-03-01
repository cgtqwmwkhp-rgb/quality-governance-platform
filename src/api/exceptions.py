"""Custom exception handlers for canonical error envelopes.

CORS headers are added here as a fallback for edge cases where
the CORSMiddleware response processing is bypassed.
"""

import re
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core.config import settings

_CORS_ORIGIN_REGEX = re.compile(r"^https://[a-z0-9-]+\.[0-9]+\.azurestaticapps\.net$")


def _get_cors_origin(request: Request) -> Optional[str]:
    """Get allowed CORS origin from request, if valid."""
    origin = request.headers.get("origin")
    if not origin:
        return None
    if origin in settings.cors_origins:
        return origin
    if _CORS_ORIGIN_REGEX.match(origin):
        return origin
    return None


def _add_cors_headers(response: JSONResponse, origin: str) -> JSONResponse:
    """Add CORS headers to response for the given origin."""
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Vary"] = "Origin"
    return response


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTPException and return canonical error envelope.

    CORS headers are added as fallback for edge cases.

    Args:
        request: The incoming request
        exc: The HTTP exception

    Returns:
        JSONResponse with canonical error envelope
    """
    request_id = getattr(request.state, "request_id", "unknown")

    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": str(exc.status_code),
            "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "details": exc.detail if isinstance(exc.detail, dict) else {},
            "request_id": request_id,
        },
    )

    # Add CORS headers as fallback
    origin = _get_cors_origin(request)
    if origin:
        _add_cors_headers(response, origin)

    return response


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle RequestValidationError and return canonical error envelope.

    CORS headers are added as fallback for edge cases.

    Args:
        request: The incoming request
        exc: The validation error

    Returns:
        JSONResponse with canonical error envelope
    """
    request_id = getattr(request.state, "request_id", "unknown")

    # Convert validation errors to JSON-serializable format
    errors = []
    for error in exc.errors():
        # Create a clean copy with only serializable values
        clean_error = {
            "loc": list(error.get("loc", [])),
            "msg": str(error.get("msg", "")),
            "type": str(error.get("type", "")),
        }
        errors.append(clean_error)

    response = JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "422",
            "message": "Validation error",
            "details": {"errors": errors},
            "request_id": request_id,
        },
    )

    # Add CORS headers as fallback
    origin = _get_cors_origin(request)
    if origin:
        _add_cors_headers(response, origin)

    return response


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unhandled exceptions with CORS headers.

    This catches any exception not caught by other handlers and ensures
    CORS headers are present on 500 responses.

    Args:
        request: The incoming request
        exc: The exception

    Returns:
        JSONResponse with canonical error envelope and CORS headers
    """
    import logging

    logger = logging.getLogger(__name__)
    request_id = getattr(request.state, "request_id", "unknown")

    # Log the actual error for debugging (no PII)
    logger.error(
        f"Unhandled exception: {type(exc).__name__}",
        extra={
            "request_id": request_id,
            "exception_type": type(exc).__name__,
            "path": str(request.url.path),
        },
        exc_info=True,
    )

    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": "500",
            "message": "Internal server error",
            "details": {},
            "request_id": request_id,
        },
    )

    # Add CORS headers as fallback
    origin = _get_cors_origin(request)
    if origin:
        _add_cors_headers(response, origin)

    return response
