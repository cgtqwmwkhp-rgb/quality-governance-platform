from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette_context import context

from src.api.schemas.error import ErrorResponse


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Custom handler for HTTPExceptions to return a standardized error response."""
    request_id = context.get("request_id", "N/A")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=str(exc.status_code),
            message=exc.detail,
            request_id=request_id,
        ).model_dump(exclude_none=True),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Custom handler for RequestValidationErrors to return a standardized error response."""
    request_id = context.get("request_id", "N/A")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Input validation failed",
            details=exc.errors(),
            request_id=request_id,
        ).model_dump(exclude_none=True),
    )
