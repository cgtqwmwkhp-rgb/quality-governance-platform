"""Main FastAPI application entry point."""

import asyncio
import logging
import secrets
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.api import router as api_router
from src.api.middleware import register_exception_handlers
from src.api.middleware.idempotency import IdempotencyMiddleware
from src.api.middleware.json_depth import JsonDepthMiddleware
from src.core.config import settings
from src.core.middleware import RequestStateMiddleware
from src.core.uat_safety import UATSafetyMiddleware
from src.infrastructure.database import close_db, init_db
from src.infrastructure.monitoring.azure_monitor import setup_telemetry


class APIVersionMiddleware(BaseHTTPMiddleware):
    """Enforce API versioning and advertise current version."""

    CURRENT_VERSION = "1.0"
    SUPPORTED_VERSIONS = {"v1", "1.0"}

    async def dispatch(self, request: Request, call_next):
        accept_version = request.headers.get("Accept-Version")
        if accept_version and accept_version not in self.SUPPORTED_VERSIONS:
            return JSONResponse(
                status_code=406,
                content={
                    "detail": f"API version '{accept_version}' is not supported. "
                    f"Current version: {self.CURRENT_VERSION}. "
                    "Use Accept-Version: v1 or omit the header.",
                    "supported_versions": sorted(self.SUPPORTED_VERSIONS),
                    "deprecated": True,
                },
                headers={"X-API-Version": self.CURRENT_VERSION},
            )

        response = await call_next(request)
        response.headers["X-API-Version"] = self.CURRENT_VERSION
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        response: Response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'nonce-{nonce}'; "
            f"img-src 'self' data: https:; "
            f"font-src 'self'; "
            f"connect-src 'self' https://*.azurestaticapps.net; "
            f"frame-ancestors 'none'; "
            f"report-uri /api/v1/telemetry/csp-report; "
            f"report-to csp-endpoint"
        )
        response.headers["Report-To"] = (
            '{"group":"csp-endpoint","max_age":86400,' '"endpoints":[{"url":"/api/v1/telemetry/csp-report"}]}'
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

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

    from src.infrastructure.cache.redis_cache import warmup_cache

    await warmup_cache()

    # Seed compliance automation default data if tables are empty
    try:
        from src.domain.services.compliance_automation_service import compliance_automation_service
        from src.infrastructure.database import async_session_maker

        async with async_session_maker() as session:
            await compliance_automation_service.seed_default_data(session)
            await session.commit()
    except Exception as e:
        logger.warning(f"Compliance automation seed skipped: {e}")

    # Seed IMS module data (standards, ISO 27001 controls, UVDB, Planet Mark)
    try:
        from src.domain.services.ims_seed_service import seed_all_ims_modules
        from src.infrastructure.database import async_session_maker as _ims_sm

        async with _ims_sm() as ims_session:
            await seed_all_ims_modules(ims_session)
            await ims_session.commit()
    except Exception as e:
        logger.warning(f"IMS module seed skipped: {e}")

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

    # Track in-flight requests for graceful shutdown
    app.state.inflight = 0
    app.state.shutting_down = False

    yield

    # --- Graceful shutdown ---
    logger.info("Shutdown signal received – draining in-flight requests")
    app.state.shutting_down = True

    # Wait up to 30s for in-flight requests to complete
    shutdown_deadline = 30.0
    poll_interval = 0.25
    waited = 0.0
    while getattr(app.state, "inflight", 0) > 0 and waited < shutdown_deadline:
        await asyncio.sleep(poll_interval)
        waited += poll_interval
    if waited >= shutdown_deadline:
        logger.warning(
            "Shutdown timeout reached with %d in-flight requests still pending",
            getattr(app.state, "inflight", 0),
        )

    # Close database connections
    await close_db()

    # Close Redis connections
    try:
        from src.infrastructure.cache.redis_cache import close_redis

        await close_redis()
    except Exception:
        logger.debug("Redis close skipped (not available or already closed)")

    # Cancel background tasks
    for task in asyncio.all_tasks():
        if task is not asyncio.current_task() and not task.done():
            task.cancel()

    logger.info("Graceful shutdown complete")


def configure_logging():
    """Configure structured JSON logging with correlation context."""
    from src.infrastructure.logging import configure_structured_logging

    log_dir = getattr(settings, "log_dir", None)
    configure_structured_logging(level=settings.log_level, log_dir=log_dir)
    logging.getLogger(__name__).info("Logging configured successfully", extra={"app_name": settings.app_name})


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
        redirect_slashes=True,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "Authentication", "description": "Authentication, authorization, and session management"},
            {"name": "Users", "description": "User account management and profiles"},
            {"name": "Incidents", "description": "Incident reporting, tracking, and resolution"},
            {"name": "Risk Register", "description": "Risk assessment, controls, and mitigation"},
            {"name": "Audits & Inspections", "description": "Audit templates, runs, findings, and scoring"},
            {
                "name": "ISO Compliance & Evidence",
                "description": "ISO clause mapping, evidence links, and gap analysis",
            },
            {"name": "Standards Library", "description": "ISO standards, clauses, and controls catalogue"},
            {"name": "Document Library", "description": "Document upload, AI analysis, and semantic search"},
            {"name": "Policy Library", "description": "Policy lifecycle management and acknowledgments"},
            {"name": "Actions", "description": "Corrective and preventive action tracking"},
            {"name": "CAPA", "description": "Corrective and Preventive Action management"},
            {"name": "Complaints", "description": "Customer complaint handling and resolution"},
            {"name": "Investigations", "description": "Root cause investigations and templates"},
            {"name": "Near Misses", "description": "Near-miss event reporting and tracking"},
            {"name": "Road Traffic Collisions", "description": "RTA incident management"},
            {"name": "Notifications", "description": "In-app and push notification management"},
            {"name": "Analytics & Reporting", "description": "Dashboards, KPIs, and trend analysis"},
            {"name": "Workflow Automation", "description": "Automated workflows and approval chains"},
            {"name": "AI Intelligence", "description": "AI-powered insights and recommendations"},
            {"name": "AI Copilot", "description": "Interactive AI assistant for compliance guidance"},
            {"name": "Health", "description": "Health, liveness, and readiness probes"},
            {"name": "Meta", "description": "Build version and deployment metadata"},
        ],
    )

    # Sentry error tracking (conditional on DSN being configured)
    if settings.sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            traces_sample_rate=0.1,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        )

    # Initialize OpenTelemetry instrumentation
    setup_telemetry(app)

    # SLO metrics middleware (outermost to capture full latency)
    from src.api.routes.slo import SLOMetricsMiddleware

    app.add_middleware(SLOMetricsMiddleware)

    # Add Request State Middleware (must be first for request_id propagation)
    app.add_middleware(RequestStateMiddleware)

    # Add UAT Safety Middleware (production read-only mode)
    # Must be early in stack to block writes before they reach handlers
    app.add_middleware(UATSafetyMiddleware)

    # Add JSON Depth Limiting Middleware (reject deeply nested payloads)
    app.add_middleware(JsonDepthMiddleware)

    # Add Security Headers Middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Add API Version Middleware (tracks version header for future migration)
    app.add_middleware(APIVersionMiddleware)

    # Add Tenant Context Middleware (sets app.current_tenant_id for RLS)
    # Must be after auth sets request.state.user / request.state.tenant_id
    from src.infrastructure.middleware.tenant_context import TenantContextMiddleware

    app.add_middleware(TenantContextMiddleware)

    # Add Audit Logging Middleware (logs all mutating requests)
    # Must be before rate limit middleware to capture rate-limited requests too
    from src.api.middleware.audit_middleware import AuditLoggingMiddleware

    app.add_middleware(AuditLoggingMiddleware)

    # Add Rate Limiting Middleware (uses per-endpoint configurable limits)
    app.add_middleware(RateLimitMiddleware)

    # Add Idempotency Middleware (handles Idempotency-Key header for POST requests)
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
            "X-Request-Id",
            "X-API-Version",
            "X-UAT-Write-Enable",
            "X-UAT-Issue-Id",
            "X-UAT-Owner",
            "X-UAT-Expiry",
            "Idempotency-Key",
        ],
        expose_headers=[
            "X-Request-Id",
            "X-API-Version",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
        ],
        max_age=86400,  # Cache preflight for 24 hours
    )

    # Register all exception handlers (DomainError, HTTPException, validation, generic)
    register_exception_handlers(app)

    # Include API routes
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_application()


@app.get("/", tags=["Root"])
async def root(request: Request):
    """Root endpoint: Provides basic API information and links."""
    from fastapi.responses import HTMLResponse

    nonce = getattr(request.state, "csp_nonce", "")
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{settings.app_name}</title>
        <style nonce="{nonce}">
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
            .footer {{
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                color: #7f8c8d;
                font-size: 14px;
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

            <div class="footer">
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


_BUILD_SHA = settings.build_sha
_BUILD_TIME = settings.build_time
_STARTUP_TIME = time.time()


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


async def _check_database() -> str:
    from sqlalchemy import text

    from src.infrastructure.database import async_session_maker

    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return "healthy"
    except Exception:
        return "unhealthy"


async def _check_redis() -> str:
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        return "healthy"
    except Exception:
        return "unavailable"


def _check_celery() -> str:
    celery_url = settings.celery_broker_url or settings.redis_url
    if not celery_url:
        return "not_configured"
    try:
        from src.infrastructure.tasks.celery_app import celery_app

        inspect = celery_app.control.inspect(timeout=2.0)
        active = inspect.active()
        return "ok" if active else "no_workers"
    except Exception as e:
        return f"error: {str(e)[:100]}"


def _check_azure_storage() -> str:
    storage_conn = settings.azure_storage_connection_string or None
    if not storage_conn:
        return "not_configured"
    try:
        from azure.storage.blob import BlobServiceClient

        blob_client = BlobServiceClient.from_connection_string(storage_conn)
        blob_client.get_account_information()
        return "ok"
    except ImportError:
        return "sdk_not_installed"
    except Exception as e:
        return f"error: {str(e)[:100]}"


def _collect_circuit_breaker_health() -> list[dict]:
    result: list[dict] = []
    modules = [
        ("src.domain.services.email_service", "_email_circuit"),
        ("src.domain.services.sms_service", "_sms_circuit"),
        ("src.domain.services.document_ai_service", "_ai_circuit"),
        ("src.domain.services.ai_models", "_ai_models_circuit"),
    ]
    for mod_path, attr_name in modules:
        try:
            import importlib

            mod = importlib.import_module(mod_path)
            circuit = getattr(mod, attr_name)
            result.append(circuit.get_health())
        except Exception:
            pass
    return result


def _check_disk_space() -> dict[str, object]:
    """Return disk free space info; warn if < 1 GB free."""
    import shutil

    try:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024**3)
        return {
            "status": "ok" if free_gb >= 1.0 else "warning",
            "free_gb": round(free_gb, 2),
            "total_gb": round(usage.total / (1024**3), 2),
            "used_pct": round(usage.used / usage.total * 100, 1),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)[:120]}


def _check_memory() -> dict[str, object]:
    """Return process memory info; warn if system memory usage > 90%."""
    import os

    try:
        import psutil

        vm = psutil.virtual_memory()
        process = psutil.Process(os.getpid())
        rss_mb = process.memory_info().rss / (1024**2)
        return {
            "status": "ok" if vm.percent <= 90 else "warning",
            "system_used_pct": round(vm.percent, 1),
            "process_rss_mb": round(rss_mb, 1),
            "system_available_mb": round(vm.available / (1024**2), 1),
        }
    except ImportError:
        import resource

        rusage = resource.getrusage(resource.RUSAGE_SELF)
        return {
            "status": "ok",
            "process_maxrss_mb": round(rusage.ru_maxrss / 1024, 1),
            "detail": "psutil not installed; limited memory info",
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)[:120]}


def _get_uptime() -> dict[str, object]:
    elapsed = time.time() - _STARTUP_TIME
    days, rem = divmod(int(elapsed), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return {
        "seconds": round(elapsed, 1),
        "human": f"{days}d {hours}h {minutes}m {seconds}s",
    }


@app.get("/readyz", tags=["Health"])
async def readiness_check(request: Request, verbose: bool = False):
    """Readiness probe: Check if application is ready to accept traffic.

    Checks database and Redis connectivity. Returns 200 OK if ready, 503 if not ready.
    Use ?verbose=true to include individual check results.

    Per ADR-0003: Readiness Probe Database Check
    """
    checks: dict[str, str] = {
        "database": await _check_database(),
        "redis": await _check_redis(),
        "celery": _check_celery(),
        "azure_storage": _check_azure_storage(),
    }

    disk = _check_disk_space()
    memory = _check_memory()
    uptime = _get_uptime()

    ignored = ("unavailable", "not_configured", "sdk_not_installed")
    all_healthy = all(v in ("healthy", "ok") for v in checks.values() if v not in ignored)

    warnings: list[str] = []
    if disk.get("status") == "warning":
        warnings.append(f"Low disk space: {disk.get('free_gb')} GB free")
    if memory.get("status") == "warning":
        warnings.append(f"High memory usage: {memory.get('system_used_pct')}%")

    request_id = getattr(request.state, "request_id", "N/A")
    response: dict[str, object] = {
        "status": "healthy" if all_healthy else "unhealthy",
        "version": settings.app_version,
        "uptime": uptime,
        "flower_url": "http://flower:5555",
        "request_id": request_id,
    }
    if warnings:
        response["warnings"] = warnings

    if verbose:
        response["checks"] = checks
        response["disk"] = disk
        response["memory"] = memory
        response["circuit_breakers"] = _collect_circuit_breaker_health()

    status_code = 200 if all_healthy else 503
    return JSONResponse(content=response, status_code=status_code)
