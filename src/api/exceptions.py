"""Custom exception handlers for canonical error envelopes."""

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette_context import context


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTPException and return canonical error envelope.

    Args:
        request: The incoming request
        exc: The HTTP exception

    Returns:
        JSONResponse with canonical error envelope
    """
    request_id = context.get("request_id", "unknown")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": str(exc.status_code),
            "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "details": exc.detail if isinstance(exc.detail, dict) else {},
            "request_id": request_id,
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle RequestValidationError and return canonical error envelope.

    Args:
        request: The incoming request
        exc: The validation error

    Returns:
        JSONResponse with canonical error envelope
    """
    request_id = context.get("request_id", "unknown")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "422",
            "message": "Validation error",
            "details": {"errors": exc.errors()},
            "request_id": request_id,
        },
    )
