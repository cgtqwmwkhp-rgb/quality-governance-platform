"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import router as api_router
from src.api.health import router as health_router
from src.core.config import settings
from src.infrastructure.database import close_db, init_db
from src.middleware.observability import ObservabilityMiddleware, configure_structured_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    if settings.is_development:
        await init_db()
    yield
    # Shutdown
    await close_db()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description="Enterprise-grade Quality Governance (IMS) Platform for ISO compliance management",
        version="1.0.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # Configure structured logging
    configure_structured_logging()

    # Add observability middleware (request IDs, structured logging)
    app.add_middleware(ObservabilityMiddleware)

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include health endpoints at root level (for orchestrators)
    app.include_router(health_router)

    # Include API routes
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_application()


# Health endpoints are now registered via health_router at root level
