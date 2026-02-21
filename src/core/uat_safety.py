"""
UAT Safety Middleware for Production-Safe Testing.

Implements read-only mode for production UAT with audited override capability.

Behavior:
- UAT_MODE=READ_ONLY (production default): Block POST/PUT/PATCH/DELETE
- UAT_MODE=READ_WRITE (staging default): Allow all operations

Override Headers (for audited writes in READ_ONLY mode):
- X-UAT-WRITE-ENABLE: true
- X-UAT-ISSUE-ID: GOVPLAT-XXX (required for audit trail)
- X-UAT-OWNER: team-name (required for audit trail)
- X-UAT-EXPIRY: YYYY-MM-DD (optional, if expired -> blocked)

Only users in UAT_ADMIN_USERS list can use override headers.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.core.config import settings

logger = logging.getLogger(__name__)

# Methods that modify state
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths that are always allowed (health checks, meta endpoints)
ALWAYS_ALLOWED_PATHS = {
    "/healthz",
    "/readyz",
    "/api/v1/meta/version",
    "/api/v1/auth/login",
    "/api/v1/auth/token",
    "/api/v1/auth/refresh",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/",
}


class UATWriteBlockedResponse:
    """Standard response for blocked UAT writes."""

    @staticmethod
    def create(
        detail: str = "UAT on production is read-only by default",
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error_class": "UAT_WRITE_BLOCKED",
                "detail": detail,
                "how_to_enable": "See docs/uat/PROD_VIEW_UAT_RUNBOOK.md for override procedure",
            },
        )


def _is_path_always_allowed(path: str) -> bool:
    """Check if path is in the always-allowed list."""
    # Exact match first
    if path in ALWAYS_ALLOWED_PATHS:
        return True
    # Check if path starts with any allowed prefix (but only for multi-segment paths)
    # Exclude "/" from prefix matching to avoid matching all paths
    for allowed in ALWAYS_ALLOWED_PATHS:
        if allowed != "/" and len(allowed) > 1 and path.startswith(allowed):
            return True
    return False


def _validate_override_headers(request: Request) -> tuple[bool, Optional[str]]:
    """
    Validate UAT override headers for audited write access.

    Returns:
        (is_valid, error_message)
    """
    enable = request.headers.get("X-UAT-WRITE-ENABLE", "").lower()
    issue_id = request.headers.get("X-UAT-ISSUE-ID", "")
    owner = request.headers.get("X-UAT-OWNER", "")
    expiry = request.headers.get("X-UAT-EXPIRY", "")

    # Must have enable=true
    if enable != "true":
        return False, "X-UAT-WRITE-ENABLE header must be 'true'"

    # Must have issue ID
    if not issue_id:
        return False, "X-UAT-ISSUE-ID header required (e.g., GOVPLAT-123)"

    # Must have owner
    if not owner:
        return False, "X-UAT-OWNER header required (e.g., qa-team)"

    # Check expiry if provided
    if expiry:
        try:
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            if expiry_date < datetime.now().date():
                return False, f"X-UAT-EXPIRY has expired ({expiry})"
        except ValueError:
            return False, f"X-UAT-EXPIRY must be YYYY-MM-DD format, got: {expiry}"

    return True, None


def _get_user_id_from_request(request: Request) -> Optional[str]:
    """Extract user ID from request (non-PII identifier)."""
    if hasattr(request.state, "user_id"):
        return str(request.state.user_id)
    return None


def _is_user_uat_admin(user_id: Optional[str]) -> bool:
    """Check if user is in UAT admin list."""
    if not user_id:
        return False
    return user_id in settings.uat_admin_user_list


def _log_uat_write_attempt(
    request: Request,
    allowed: bool,
    user_id: Optional[str],
    issue_id: Optional[str] = None,
    owner: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Log UAT write attempt for audit trail (no payload/PII)."""
    log_data = {
        "event": "uat_write_attempt",
        "allowed": allowed,
        "method": request.method,
        "path": request.url.path,
        "user_id": user_id or "anonymous",
        "timestamp": datetime.utcnow().isoformat(),
    }
    if issue_id:
        log_data["issue_id"] = issue_id
    if owner:
        log_data["owner"] = owner
    if reason:
        log_data["reason"] = reason

    if allowed:
        logger.info("UAT write allowed via override", extra=log_data)
    else:
        logger.warning("UAT write blocked", extra=log_data)


class UATSafetyMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce UAT read-only mode in production.

    In READ_ONLY mode:
    - Blocks POST/PUT/PATCH/DELETE requests by default
    - Returns HTTP 409 with structured error
    - Allows writes only with valid override headers from admin users
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip if not in read-only mode
        if not settings.is_uat_read_only:
            return await call_next(request)

        # Always allow non-write methods
        if request.method not in WRITE_METHODS:
            return await call_next(request)

        # Always allow certain paths
        if _is_path_always_allowed(request.url.path):
            return await call_next(request)

        # Check for override headers
        user_id = _get_user_id_from_request(request)
        issue_id = request.headers.get("X-UAT-ISSUE-ID", "")
        owner = request.headers.get("X-UAT-OWNER", "")

        # If no override headers at all, block immediately
        if "X-UAT-WRITE-ENABLE" not in request.headers:
            _log_uat_write_attempt(
                request,
                allowed=False,
                user_id=user_id,
                reason="No override headers provided",
            )
            return UATWriteBlockedResponse.create()

        # Validate override headers
        is_valid, error_msg = _validate_override_headers(request)
        if not is_valid:
            _log_uat_write_attempt(
                request,
                allowed=False,
                user_id=user_id,
                issue_id=issue_id,
                owner=owner,
                reason=error_msg,
            )
            return UATWriteBlockedResponse.create(f"Override validation failed: {error_msg}")

        # Check if user is UAT admin
        if not _is_user_uat_admin(user_id):
            _log_uat_write_attempt(
                request,
                allowed=False,
                user_id=user_id,
                issue_id=issue_id,
                owner=owner,
                reason="User not in UAT admin list",
            )
            return UATWriteBlockedResponse.create("User not authorized for UAT writes. Contact platform admin.")

        # All checks passed - allow the write
        _log_uat_write_attempt(
            request,
            allowed=True,
            user_id=user_id,
            issue_id=issue_id,
            owner=owner,
        )
        return await call_next(request)
