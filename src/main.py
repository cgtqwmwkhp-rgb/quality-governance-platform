"""Main FastAPI application entry point."""

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pythonjsonlogger import jsonlogger
from starlette.middleware.base import BaseHTTPMiddleware

from src.api import router as api_router
from src.api.exceptions import http_exception_handler, validation_exception_handler
from src.core.config import settings
from src.core.middleware import RequestStateMiddleware
from src.infrastructure.database import close_db, init_db


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Cache control for security
        if "/api/" in request.url.path:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using sophisticated per-endpoint limits.

    Uses the infrastructure rate limiter which supports:
    - Per-endpoint configurable limits
    - IP-based and user-based limiting
    - Redis backend for distributed deployments
    - Fallback to in-memory when Redis unavailable
    - Different limits for authenticated vs anonymous users
    """

    async def dispatch(self, request: Request, call_next):
        from src.infrastructure.middleware.rate_limiter import rate_limit_middleware

        return await rate_limit_middleware(request, call_next)


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
        docs_url="/docs",  # Always enable API docs
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        redirect_slashes=False,  # Disabled to prevent HTTP redirects behind HTTPS proxy
        lifespan=lifespan,
    )

    # Add Request State Middleware (must be first for request_id propagation)
    app.add_middleware(RequestStateMiddleware)

    # Add Security Headers Middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Add Rate Limiting Middleware (uses per-endpoint configurable limits)
    app.add_middleware(RateLimitMiddleware)

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"https://.*\.azurestaticapps\.net",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]  # TYPE-IGNORE: MYPY-002 FastAPI exception handler type mismatch
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]  # TYPE-IGNORE: MYPY-002 FastAPI exception handler type mismatch

    # Include API routes
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_application()


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint: Provides basic API information and links."""
    from fastapi.responses import HTMLResponse

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{settings.app_name}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #2c3e50;
                margin-bottom: 10px;
            }}
            .version {{
                color: #7f8c8d;
                font-size: 14px;
                margin-bottom: 20px;
            }}
            .description {{
                color: #555;
                line-height: 1.6;
                margin-bottom: 30px;
            }}
            .endpoints {{
                margin-top: 30px;
            }}
            .endpoint {{
                background: #f8f9fa;
                padding: 15px;
                margin: 10px 0;
                border-radius: 4px;
                border-left: 4px solid #3498db;
            }}
            .endpoint a {{
                color: #3498db;
                text-decoration: none;
                font-weight: 500;
            }}
            .endpoint a:hover {{
                text-decoration: underline;
            }}
            .endpoint-desc {{
                color: #7f8c8d;
                font-size: 14px;
                margin-top: 5px;
            }}
            .status {{
                display: inline-block;
                padding: 4px 12px;
                background: #27ae60;
                color: white;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{settings.app_name}</h1>
            <div class="version">Version 1.0.0 | Environment: {settings.app_env} <span class="status">RUNNING</span></div>
            <div class="description">
                Enterprise-grade Quality Governance (IMS) Platform for ISO compliance management.
                Manage standards, audits, risks, incidents, complaints, and policies in one integrated system.
            </div>

            <div class="endpoints">
                <h2>Available Endpoints</h2>

                {'<div class="endpoint"><a href="/docs">/docs</a><div class="endpoint-desc">Interactive API Documentation (Swagger UI)</div></div>' if settings.is_development else ''}

                {'<div class="endpoint"><a href="/redoc">/redoc</a><div class="endpoint-desc">Alternative API Documentation (ReDoc)</div></div>' if settings.is_development else ''}

                <div class="endpoint">
                    <a href="/health">/health</a>
                    <div class="endpoint-desc">Legacy health check endpoint</div>
                </div>

                <div class="endpoint">
                    <a href="/healthz">/healthz</a>
                    <div class="endpoint-desc">Liveness probe - Check if application is alive</div>
                </div>

                <div class="endpoint">
                    <a href="/readyz">/readyz</a>
                    <div class="endpoint-desc">Readiness probe - Check if application is ready (includes DB check)</div>
                </div>

                <div class="endpoint">
                    <a href="/api/v1">/api/v1</a>
                    <div class="endpoint-desc">API v1 endpoints (authentication required)</div>
                </div>
            </div>

            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #7f8c8d; font-size: 14px;">
                <strong>Modules:</strong> Standards Library, Audits & Inspections, Risk Management, Incidents, Root Cause Analysis, Complaints, Policy Library
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


@app.get("/health", tags=["Health"])
async def health_check(request: Request) -> dict:
    """Health check endpoint."""
    # Get request_id from request.state (reliable under AsyncClient)
    request_id = getattr(request.state, "request_id", "N/A")
    logging.getLogger(__name__).info("Health check requested", extra={"request_id": request_id})
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "request_id": request_id,
    }


# Build version stamp - set by CI/CD or defaults
import os as _os

_BUILD_SHA = _os.environ.get("BUILD_SHA", "dev")
_BUILD_TIME = _os.environ.get("BUILD_TIME", "local")


@app.get("/api/v1/meta/version", tags=["Meta"])
async def get_version() -> dict:
    """Return build version information for deployment verification."""
    return {
        "build_sha": _BUILD_SHA,
        "build_time": _BUILD_TIME,
        "app_name": settings.app_name,
        "environment": settings.app_env,
    }


@app.get("/healthz", tags=["Health"])
async def liveness_check(request: Request) -> dict:
    """Liveness probe: Check if application process is alive.

    Returns 200 OK if the application is running.
    Used by container orchestrators to determine if the container should be restarted.
    """
    request_id = getattr(request.state, "request_id", "N/A")
    return {
        "status": "ok",
        "request_id": request_id,
    }


@app.get("/readyz", tags=["Health"])
async def readiness_check(request: Request):
    """Readiness probe: Check if application is ready to accept traffic.

    Checks database connectivity. Returns 200 OK if ready, 503 if not ready.
    Used by load balancers to determine if traffic should be routed to this instance.

    Per ADR-0003: Readiness Probe Database Check
    """
    from fastapi.responses import JSONResponse
    from sqlalchemy import text

    from src.infrastructure.database import async_session_maker

    request_id = getattr(request.state, "request_id", "N/A")
    logger = logging.getLogger(__name__)

    try:
        # Ping database with a simple query
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))

        logger.info("Readiness check passed", extra={"request_id": request_id})
        return {
            "status": "ready",
            "database": "connected",
            "request_id": request_id,
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}", extra={"request_id": request_id, "error": str(e)})
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "disconnected",
                "error": str(e),
                "request_id": request_id,
            },
        )
