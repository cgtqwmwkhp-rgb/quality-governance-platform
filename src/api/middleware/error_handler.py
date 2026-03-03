"""Global exception handler for consistent error responses.

Handles DomainError subclasses, HTTPException, RequestValidationError,
and uncaught exceptions — all with a unified error envelope.
"""

import logging
import traceback
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.api.schemas.error_codes import ErrorCode
from src.domain.exceptions import DomainError

logger = logging.getLogger(__name__)

_STATUS_TO_ERROR_CODE: dict[int, str] = {
    400: ErrorCode.VALIDATION_ERROR,
    401: ErrorCode.AUTHENTICATION_REQUIRED,
    403: ErrorCode.PERMISSION_DENIED,
    404: ErrorCode.ENTITY_NOT_FOUND,
    409: ErrorCode.DUPLICATE_ENTITY,
    429: ErrorCode.RATE_LIMIT_EXCEEDED,
    500: ErrorCode.INTERNAL_ERROR,
}


def _build_envelope(
    code: str,
    message: str,
    request_id: str,
    details: dict | None = None,
) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
        logger.warning(
            "Domain error [%s] %s: %s",
            exc.code,
            type(exc).__name__,
            exc.message,
            extra={"request_id": request_id, "error_code": exc.code},
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=_build_envelope(exc.code, exc.message, request_id, exc.details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
        code = _STATUS_TO_ERROR_CODE.get(exc.status_code, f"HTTP_{exc.status_code}")
        details: dict[str, object] = exc.detail if isinstance(exc.detail, dict) else {}
        message = exc.detail if isinstance(exc.detail, str) else _status_phrase(exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_envelope(code, message, request_id, details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
        field_errors = []
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error.get("loc", []))
            field_errors.append(
                {
                    "field": field,
                    "message": error.get("msg", ""),
                    "type": error.get("type", ""),
                }
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_build_envelope(
                ErrorCode.VALIDATION_ERROR,
                "Request validation failed",
                request_id,
                {"errors": field_errors},
            ),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
        logger.error(
            "Unhandled exception [request_id=%s]: %s\n%s",
            request_id,
            str(exc),
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_build_envelope(ErrorCode.INTERNAL_ERROR, "Internal server error", request_id),
        )


def _status_phrase(code: int) -> str:
    phrases = {
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
    return phrases.get(code, f"HTTP {code}")
