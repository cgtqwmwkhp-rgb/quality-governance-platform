"""Global exception handler for consistent error responses."""

import logging
import traceback
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = str(uuid.uuid4())
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": _status_phrase(exc.status_code),
                "message": str(exc.detail),
                "request_id": request_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = str(uuid.uuid4())
        details = []
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error.get("loc", []))
            details.append(
                {
                    "field": field,
                    "message": error.get("msg", ""),
                    "code": error.get("type", ""),
                }
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation Error",
                "message": "Request validation failed",
                "details": details,
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = str(uuid.uuid4())
        logger.error(
            "Unhandled exception [%s]: %s\n%s",
            request_id,
            str(exc),
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            },
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
