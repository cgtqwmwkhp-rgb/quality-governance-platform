"""
Audit Logging Middleware for FastAPI.

Automatically logs all mutating requests (POST, PUT, PATCH, DELETE) to the audit log
with PII masking, hash chain integrity, and asynchronous background processing.
"""

import json
import logging
from typing import Any, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Mutating HTTP methods to audit
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths to skip (health checks and auth endpoints with sensitive data)
SKIP_PATHS = {
    "/health",
    "/healthz",
    "/readyz",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
}

# PII fields to mask in request bodies
PII_FIELDS = {
    "password",
    "secret",
    "token",
    "ssn",
    "credit_card",
    "creditCard",
    "card_number",
    "cardNumber",
    "cvv",
    "pin",
}


def _should_skip_path(path: str) -> bool:
    """Check if the path should be skipped from audit logging."""
    # Exact match
    if path in SKIP_PATHS:
        return True
    # Check if path starts with any skip prefix
    for skip_path in SKIP_PATHS:
        if skip_path != "/" and path.startswith(skip_path):
            return True
    return False


def _mask_pii(data: Any) -> Any:
    """
    Recursively mask PII fields in a data structure.

    Args:
        data: The data structure to mask (dict, list, or primitive)

    Returns:
        The data structure with PII fields masked as "***REDACTED***"
    """
    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            # Check if key contains any PII field name (case-insensitive)
            key_lower = key.lower()
            if any(pii_field.lower() in key_lower for pii_field in PII_FIELDS):
                masked[key] = "***REDACTED***"
            else:
                masked[key] = _mask_pii(value)
        return masked
    elif isinstance(data, list):
        return [_mask_pii(item) for item in data]
    else:
        return data


async def _get_request_body(request: Request) -> Optional[dict]:
    """
    Safely read and parse request body as JSON.

    Returns None if body cannot be read or parsed.
    """
    try:
        body = await request.body()
        if not body:
            return None
        return json.loads(body)
    except (json.JSONDecodeError, ValueError, RuntimeError):
        # Body might not be JSON or might have been consumed
        return None


def _get_user_info(request: Request) -> tuple[Optional[int], Optional[int]]:
    """
    Extract user_id and tenant_id from request state or JWT token.

    This function does NOT make database calls to avoid blocking the request.
    It only extracts info that's already available (request.state or JWT payload).

    Returns:
        Tuple of (user_id, tenant_id) - both may be None if not authenticated
    """
    # First, try to get from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)
    tenant_id = getattr(request.state, "tenant_id", None)

    # If user_id is set but tenant_id is not, try to get it from user object
    if user_id and not tenant_id:
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "tenant_id"):
            tenant_id = user.tenant_id

    # If still no user_id, try to extract from JWT token (synchronous, no DB)
    if not user_id:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from src.core.security import decode_token

                token = auth_header[7:]
                payload = decode_token(token)
                if payload:
                    user_id_raw = payload.get("sub")
                    if user_id_raw:
                        try:
                            user_id = int(user_id_raw)
                        except (ValueError, TypeError):
                            pass
            except Exception:
                pass

    # Note: We don't do DB lookups here to avoid blocking the request.
    # If tenant_id is not available, we'll skip logging (which is fine for
    # unauthenticated or system requests).

    return user_id, tenant_id


async def _log_audit_entry(
    request: Request,
    response: Response,
    user_id: Optional[int],
    tenant_id: Optional[int],
    request_body: Optional[dict],
) -> None:
    """
    Log an audit entry asynchronously using the audit log service.

    This function runs in a background task and should not block the request.
    """
    try:
        # Conditional import to avoid circular dependencies
        from sqlalchemy import select

        from src.domain.models.user import User
        from src.domain.services.audit_log_service import AuditLogService
        from src.infrastructure.database import async_session_maker

        # If we have user_id but no tenant_id, try to get it from database
        # This is OK in background task since it doesn't block the response
        if user_id and not tenant_id:
            try:
                async with async_session_maker() as session:
                    result = await session.execute(select(User.tenant_id).where(User.id == user_id))
                    tenant_id = result.scalar_one_or_none()
            except Exception:
                # If DB lookup fails, skip logging
                pass

        # Skip if no tenant_id (unauthenticated or system request)
        if not tenant_id:
            return

        # Mask PII in request body
        masked_body = _mask_pii(request_body) if request_body else None

        # Create audit log entry using the service
        async with async_session_maker() as session:
            audit_service = AuditLogService(session)

            # Map HTTP method to action
            method = request.method.upper()
            action_map = {
                "POST": "create",
                "PUT": "update",
                "PATCH": "update",
                "DELETE": "delete",
            }
            action = action_map.get(method, method.lower())

            # Extract entity info from path (e.g., /api/v1/risks/123 -> entity_type="risks", entity_id="123")
            path_parts = request.url.path.strip("/").split("/")
            entity_type = None
            entity_id = None

            # Try to extract entity type and ID from path
            # Pattern: /api/v1/{entity_type}/{entity_id}
            if len(path_parts) >= 4 and path_parts[0] == "api" and path_parts[1] == "v1":
                entity_type = path_parts[2]
                if len(path_parts) >= 4:
                    # Try to parse as int, fallback to string
                    try:
                        entity_id = int(path_parts[3])
                    except (ValueError, IndexError):
                        entity_id = path_parts[3] if len(path_parts) > 3 else None
                else:
                    entity_id = None

            # If we can't extract entity info, use endpoint as entity_type
            if not entity_type:
                entity_type = "endpoint"
                entity_id = request.url.path

            # Get user info from request state
            user_email = None
            user_name = None
            user_role = None
            user = getattr(request.state, "user", None)
            if user:
                user_email = getattr(user, "email", None)
                user_name = getattr(user, "full_name", None)
                # Get first role if available
                if hasattr(user, "roles") and user.roles:
                    user_role = user.roles[0].name if hasattr(user.roles[0], "name") else None

            # Get request metadata
            request_id = getattr(request.state, "request_id", None)
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

            # Determine if this is a create or update based on method
            if method == "POST":
                # Create action - log new_values only
                await audit_service.log(
                    tenant_id=tenant_id,
                    entity_type=entity_type,
                    entity_id=str(entity_id) if entity_id else "unknown",
                    action=action,
                    user_id=user_id,
                    user_email=user_email,
                    user_name=user_name,
                    user_role=user_role,
                    new_values=masked_body,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_id=request_id,
                    metadata={
                        "endpoint": request.url.path,
                        "method": method,
                        "status_code": response.status_code,
                        "query_params": dict(request.query_params) if request.query_params else None,
                    },
                    action_category="api_request",
                )
            elif method in ("PUT", "PATCH"):
                # Update action - log both old and new values
                # Note: We don't have old_values in middleware, so we log new_values only
                await audit_service.log(
                    tenant_id=tenant_id,
                    entity_type=entity_type,
                    entity_id=str(entity_id) if entity_id else "unknown",
                    action=action,
                    user_id=user_id,
                    user_email=user_email,
                    user_name=user_name,
                    user_role=user_role,
                    new_values=masked_body,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_id=request_id,
                    metadata={
                        "endpoint": request.url.path,
                        "method": method,
                        "status_code": response.status_code,
                        "query_params": dict(request.query_params) if request.query_params else None,
                    },
                    action_category="api_request",
                )
            elif method == "DELETE":
                # Delete action - log old_values (the entity being deleted)
                await audit_service.log(
                    tenant_id=tenant_id,
                    entity_type=entity_type,
                    entity_id=str(entity_id) if entity_id else "unknown",
                    action=action,
                    user_id=user_id,
                    user_email=user_email,
                    user_name=user_name,
                    user_role=user_role,
                    old_values=masked_body,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_id=request_id,
                    metadata={
                        "endpoint": request.url.path,
                        "method": method,
                        "status_code": response.status_code,
                        "query_params": dict(request.query_params) if request.query_params else None,
                    },
                    action_category="api_request",
                )

    except Exception as e:
        # Log warning but don't fail the request
        logger.warning(
            "Failed to log audit entry",
            extra={
                "error": str(e),
                "path": request.url.path,
                "method": request.method,
                "user_id": user_id,
                "tenant_id": tenant_id,
            },
            exc_info=True,
        )


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically log all mutating requests to the audit log.

    Features:
    - Only logs POST/PUT/PATCH/DELETE requests
    - Skips health check and auth paths
    - Masks PII fields in request bodies
    - Logs asynchronously using background tasks
    - Uses hash chain for tamper-proofing
    - Never fails the request if logging fails
    """

    async def dispatch(self, request: Request, call_next):
        # Only process mutating methods
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        # Skip health check and auth paths
        if _should_skip_path(request.url.path):
            return await call_next(request)

        # Read request body before it's consumed
        request_body = await _get_request_body(request)

        # Process the request
        response = await call_next(request)

        # Only log successful requests (2xx, 3xx) or client errors (4xx)
        # Skip server errors (5xx) as they might indicate system issues
        if response.status_code >= 500:
            return response

        # Get user info from request state or JWT
        user_id, tenant_id = _get_user_info(request)

        # Skip if no tenant_id (unauthenticated requests)
        if not tenant_id:
            return response

        # Log audit entry in background task
        # Use background task to avoid blocking the response
        from starlette.background import BackgroundTask

        background_task = BackgroundTask(
            _log_audit_entry,
            request=request,
            response=response,
            user_id=user_id,
            tenant_id=tenant_id,
            request_body=request_body,
        )

        # Attach background task to response
        response.background = background_task

        return response
