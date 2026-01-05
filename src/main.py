"""Main FastAPI application entry point."""

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pythonjsonlogger import jsonlogger
from starlette_context import context, middleware
from starlette_context.plugins import RequestIdPlugin

from src.api import router as api_router
from src.api.exceptions import http_exception_handler, validation_exception_handler
from src.core.config import settings
from src.infrastructure.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    if settings.is_development:
        await init_db()
    yield
    # Shutdown
    await close_db()


def configure_logging():
    """Configure structured JSON logging."""
    logger = logging.getLogger()
    logger.setLevel(settings.log_level)

    # Remove default handler
    if logger.handlers:
        logger.handlers = []

    # Add JSON handler
    json_handler = logging.StreamHandler(sys.stdout)
    # Use a format string that includes common fields. jsonlogger will handle the rest.
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s %(lineno)d %(message)s"
    )
    json_handler.setFormatter(formatter)
    logger.addHandler(json_handler)

    # Configure uvicorn logging to use the same handler
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers = []
    uvicorn_logger.addHandler(json_handler)
    uvicorn_logger.setLevel(settings.log_level)

    # Configure uvicorn.access logging to use the same handler
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.handlers = []
    uvicorn_access_logger.addHandler(json_handler)
    uvicorn_access_logger.setLevel(settings.log_level)

    # Example log to confirm configuration
    logger.info("Logging configured successfully", extra={"app_name": settings.app_name})


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    configure_logging()
    app = FastAPI(
        title=settings.app_name,
        description="Enterprise-grade Quality Governance (IMS) Platform for ISO compliance management",
        version="1.0.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # Add Request ID Middleware (must be before CORS)
    app.add_middleware(
        middleware.ContextMiddleware,
        plugins=(RequestIdPlugin(),),
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]  # TYPE-IGNORE: MYPY-002
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]  # TYPE-IGNORE: MYPY-002

    # Include API routes
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_application()


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint."""
    # Example of logging with request_id
    request_id = context.get("request_id", "N/A")
    logging.getLogger(__name__).info("Health check requested", extra={"request_id": request_id})
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "request_id": request_id,
    }
