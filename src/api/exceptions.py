"""Custom exception handlers for canonical error envelopes.

CORS headers are added here as a fallback for edge cases where
the CORSMiddleware response processing is bypassed.
"""

import re
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Production SWA origins (must match src/core/config.py)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:5173",
    # Production Azure Static Web App (custom domain style)
    "https://app-qgp-prod.azurestaticapps.net",
    # Production Azure Static Web App (auto-generated style)
    "https://purple-water-03205fa03.6.azurestaticapps.net",
]

# Regex for staging/preview SWA origins
CORS_ORIGIN_REGEX = re.compile(r"^https://[a-z0-9-]+\.[0-9]+\.azurestaticapps\.net$")


_STATUS_PHRASE: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    413: "Payload Too Large",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
}


def _get_cors_origin(request: Request) -> Optional[str]:
    """Get allowed CORS origin from request, if valid."""
    origin = request.headers.get("origin")
    if not origin:
        return None
    if origin in CORS_ALLOWED_ORIGINS:
        return origin
    if CORS_ORIGIN_REGEX.match(origin):
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

    code = exc.detail if isinstance(exc.detail, str) else str(exc.status_code)
    message = _STATUS_PHRASE.get(exc.status_code, f"HTTP {exc.status_code}")
    details = exc.detail if isinstance(exc.detail, dict) else {}

    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id,
            }
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
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": errors},
                "request_id": request_id,
            }
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
    import traceback

    logger = logging.getLogger(__name__)
    request_id = getattr(request.state, "request_id", "unknown")

    logger.error(
        "Unhandled exception [request_id=%s]: %s\n%s",
        request_id,
        type(exc).__name__,
        traceback.format_exc(),
        extra={
            "request_id": request_id,
            "exception_type": type(exc).__name__,
            "path": str(request.url.path),
        },
    )

    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": {},
                "request_id": request_id,
            }
        },
    )

    # Add CORS headers as fallback
    origin = _get_cors_origin(request)
    if origin:
        _add_cors_headers(response, origin)

    return response
