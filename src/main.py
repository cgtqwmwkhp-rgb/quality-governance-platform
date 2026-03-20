"""Main FastAPI application entry point."""

import logging
import os as _os
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pythonjsonlogger import jsonlogger
from starlette.middleware.base import BaseHTTPMiddleware

from src.api import router as api_router
from src.api.middleware.error_handler import register_exception_handlers
from src.api.middleware.idempotency import IdempotencyMiddleware
from src.core.config import settings
from src.core.middleware import RequestStateMiddleware
from src.core.uat_safety import UATSafetyMiddleware
from src.infrastructure.database import close_db, init_db
from src.infrastructure.middleware.request_logger import RequestLoggerMiddleware
from src.infrastructure.monitoring.azure_monitor import setup_telemetry
from src.infrastructure.pams_database import close_pams, init_pams


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

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
    import time

    logger = logging.getLogger(__name__)

    # Startup
    if settings.is_development:
        await init_db()

    # Initialise PAMS external database connection (non-blocking)
    try:
        await init_pams()
    except Exception as e:
        logger.warning("PAMS database init failed (non-fatal): %s", e)

    # Pre-warm OpenAPI schema generation for fast first request
    # This avoids cold-start latency when /openapi.json is first accessed
    # FastAPI caches the schema internally after first generation
    openapi_start = time.perf_counter()
    try:
        _ = app.openapi()  # Triggers schema generation and caching
        openapi_duration_ms = (time.perf_counter() - openapi_start) * 1000
        logger.info(
            "OpenAPI schema pre-warmed at startup",
            extra={"openapi_warmup_ms": round(openapi_duration_ms, 2)},
        )
    except Exception as e:
        # Non-fatal: log warning but don't block startup
        logger.warning(
            f"OpenAPI pre-warm failed (non-fatal): {e}",
            extra={"error": str(e)},
        )

    yield
    # Shutdown
    await close_pams()
    await close_db()


def configure_logging():
    """Configure structured JSON logging."""
    logger = logging.getLogger()
    logger.setLevel(settings.log_level)

    if logger.handlers:
        logger.handlers = []

    json_handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s %(lineno)d %(message)s"
    )
    json_handler.setFormatter(formatter)
    logger.addHandler(json_handler)

    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers = []
    uvicorn_logger.addHandler(json_handler)
    uvicorn_logger.setLevel(settings.log_level)

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.handlers = []
    uvicorn_access_logger.addHandler(json_handler)
    uvicorn_access_logger.setLevel(settings.log_level)

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
        openapi_tags=[
            {
                "name": "Authentication",
                "description": "Authentication, authorization, and session management",
            },
            {"name": "Users", "description": "User account management and profiles"},
            {
                "name": "Incidents",
                "description": "Incident reporting, tracking, and resolution",
            },
            {
                "name": "Risk Register",
                "description": "Risk assessment, controls, and mitigation",
            },
            {
                "name": "Audits & Inspections",
                "description": "Audit templates, runs, findings, and scoring",
            },
            {
                "name": "ISO Compliance & Evidence",
                "description": "ISO clause mapping, evidence links, and gap analysis",
            },
            {
                "name": "Standards Library",
                "description": "ISO standards, clauses, and controls catalogue",
            },
            {
                "name": "Document Library",
                "description": "Document upload, AI analysis, and semantic search",
            },
            {
                "name": "Policy Library",
                "description": "Policy lifecycle management and acknowledgments",
            },
            {
                "name": "Actions",
                "description": "Corrective and preventive action tracking",
            },
            {
                "name": "CAPA",
                "description": "Corrective and Preventive Action management",
            },
            {
                "name": "Complaints",
                "description": "Customer complaint handling and resolution",
            },
            {
                "name": "Investigations",
                "description": "Root cause investigations and templates",
            },
            {
                "name": "Near Misses",
                "description": "Near-miss event reporting and tracking",
            },
            {
                "name": "Road Traffic Collisions",
                "description": "RTA incident management",
            },
            {
                "name": "Notifications",
                "description": "In-app and push notification management",
            },
            {
                "name": "Analytics & Reporting",
                "description": "Dashboards, KPIs, and trend analysis",
            },
            {
                "name": "Workflow Automation",
                "description": "Automated workflows and approval chains",
            },
            {
                "name": "AI Intelligence",
                "description": "AI-powered insights and recommendations",
            },
            {
                "name": "AI Copilot",
                "description": "Interactive AI assistant for compliance guidance",
            },
            {"name": "Health", "description": "Health, liveness, and readiness probes"},
            {"name": "Meta", "description": "Build version and deployment metadata"},
        ],
    )

    setup_telemetry(app=app)

    # GZip compression — outermost so all responses are compressed
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # Add Request State Middleware (must be first for request_id propagation)
    app.add_middleware(RequestStateMiddleware)

    # Add UAT Safety Middleware (production read-only mode)
    # Must be early in stack to block writes before they reach handlers
    app.add_middleware(UATSafetyMiddleware)

    # Add Security Headers Middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Request logging (method, path, status, latency)
    app.add_middleware(RequestLoggerMiddleware)

    # Add Rate Limiting Middleware (uses per-endpoint configurable limits)
    app.add_middleware(RateLimitMiddleware)

    # Add Idempotency Middleware (caches POST responses by Idempotency-Key header)
    app.add_middleware(IdempotencyMiddleware)

    # Configure CORS - explicit allowlist + regex for staging/preview
    # Production origins are explicit in cors_origins for security
    # Regex pattern for staging/preview Azure SWA deployments
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"^https://[a-z0-9-]+\.[0-9]+\.azurestaticapps\.net$",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Request-Id",
            "X-UAT-Write-Enable",
            "X-UAT-Issue-Id",
            "X-UAT-Owner",
            "X-UAT-Expiry",
        ],
        expose_headers=[
            "X-Request-Id",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
        ],
        max_age=86400,  # Cache preflight for 24 hours
    )

    # Register exception handlers (DomainError, HTTPException, ValidationError, catch-all)
    register_exception_handlers(app)

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

    Checks database and Redis connectivity. Returns 200 OK if ready, 503 if not.
    Used by load balancers to determine if traffic should be routed to this instance.

    Per ADR-0003: Readiness Probe Database Check
    """
    import asyncio

    from fastapi.responses import JSONResponse
    from sqlalchemy import text

    from src.infrastructure.database import async_session_maker

    request_id = getattr(request.state, "request_id", "N/A")
    logger = logging.getLogger(__name__)

    db_status = "connected"
    redis_status = "connected"
    status_code = 200

    # Database check
    try:
        async with async_session_maker() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=3.0)
    except Exception as e:
        logger.error("Readiness: DB check failed: %s", e, extra={"request_id": request_id})
        db_status = "disconnected"
        status_code = 503

    # Redis check
    try:
        import redis.asyncio as aioredis

        if settings.redis_url:
            r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
            await asyncio.wait_for(r.ping(), timeout=2.0)
            await r.aclose()
        else:
            redis_status = "not_configured"
    except Exception as e:
        logger.warning("Readiness: Redis check failed: %s", e, extra={"request_id": request_id})
        redis_status = "degraded"

    overall = "ready" if status_code == 200 else "not_ready"
    if status_code == 200:
        logger.info("Readiness check passed", extra={"request_id": request_id})

    payload = {
        "status": overall,
        "database": db_status,
        "redis": redis_status,
        "request_id": request_id,
    }
    return JSONResponse(content=payload, status_code=status_code)
