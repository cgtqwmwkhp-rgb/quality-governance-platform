"""
Immutable Audit Trail API Routes

Provides endpoints for:
- Viewing audit logs with pagination
- Verifying chain integrity
- Exporting logs for compliance
- Statistics and analytics
- Reference data for actions and entity types
"""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from src.domain.exceptions import NotFoundError
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.api.schemas.error_codes import ErrorCode
from src.api.utils.pagination import PaginationParams, paginate
from src.domain.services.audit_log_service import AuditLogService
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Schemas
# ============================================================================


class AuditLogEntryResponse(BaseModel):
    id: int
    sequence: int
    entry_hash: str
    entity_type: str
    entity_id: str
    entity_name: Optional[str] = None
    action: str
    action_category: str
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    changed_fields: Optional[list] = None
    ip_address: Optional[str] = None
    timestamp: datetime
    is_sensitive: bool

    class Config:
        from_attributes = True


class AuditLogDetailResponse(AuditLogEntryResponse):
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    entry_metadata: dict = Field(default_factory=dict)

    class Config:
        from_attributes = True


class VerificationResponse(BaseModel):
    id: int
    start_sequence: int
    end_sequence: int
    is_valid: bool
    entries_verified: int
    invalid_entries: Optional[list] = None
    verified_at: datetime

    class Config:
        from_attributes = True


class ExportRequest(BaseModel):
    format: str = "json"
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    entity_type: Optional[str] = None
    reason: Optional[str] = None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntryResponse]
    total: int
    page: int
    page_size: int


class AuditActionsResponse(BaseModel):
    data: list[str]
    auth: list[str]
    admin: list[str]
    system: list[str]


class AuditLogExportDataResponse(BaseModel):
    export_id: int
    entries_count: int
    file_hash: str
    data: Optional[list[dict]] = None


class AuditStatsResponse(BaseModel):
    total_entries: int
    by_action: dict
    by_entity_type: dict
    top_users: list[dict]
    period_days: int


# ============================================================================
# IMPORTANT: Route ordering matters in FastAPI.
# Literal-path routes (/actions, /stats, /entity-types, /verifications)
# MUST be defined BEFORE the parameterized /{entry_id} route, otherwise
# FastAPI will try to parse "stats" as an int and return 422.
# ============================================================================


# ============================================================================
# Reference Endpoints (static data, no DB required)
# ============================================================================


@router.get("/actions", response_model=AuditActionsResponse)
async def list_actions(current_user: CurrentUser) -> Any:
    """Get list of possible audit actions."""
    return {
        "data": [
            "create",
            "update",
            "delete",
            "view",
            "export",
            "approve",
            "reject",
            "assign",
        ],
        "auth": [
            "login",
            "logout",
            "login_failed",
            "password_change",
            "password_reset",
            "mfa_enabled",
            "mfa_disabled",
        ],
        "admin": [
            "user_created",
            "user_deleted",
            "role_changed",
            "permission_granted",
            "permission_revoked",
            "settings_changed",
        ],
        "system": [
            "backup_created",
            "backup_restored",
            "migration_run",
            "maintenance_started",
            "maintenance_ended",
        ],
    }


@router.get("/entity-types", response_model=list[str])
async def list_entity_types(current_user: CurrentUser) -> Any:
    """Get list of auditable entity types."""
    return [
        "incident",
        "audit",
        "audit_finding",
        "risk",
        "complaint",
        "rta",
        "document",
        "policy",
        "action",
        "investigation",
        "user",
        "tenant",
        "workflow",
        "auth",
    ]


# ============================================================================
# Statistics
# ============================================================================


@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_stats(
    db: DbSession,
    current_user: CurrentUser,
    response: Response,
    days: int = Query(30, ge=1, le=365),
    request_id: str = Depends(get_request_id),
) -> Any:
    """Get audit log statistics for the specified period."""
    try:
        service = AuditLogService(db)
        return await service.get_stats(current_user.tenant_id, days)
    except SQLAlchemyError as e:
        logger.exception(
            "Failed to get audit stats [request_id=%s]: %s",
            request_id,
            type(e).__name__,
        )
        response.headers["X-Degraded"] = "audit-stats"
        return {
            "total_entries": 0,
            "by_action": {},
            "by_entity_type": {},
            "top_users": [],
            "period_days": days,
        }


# ============================================================================
# Verification History
# ============================================================================


@router.get("/verifications", response_model=list[VerificationResponse])
async def list_verifications(
    db: DbSession,
    current_user: CurrentUser,
    response: Response,
    limit: int = Query(10, ge=1, le=50),
    request_id: str = Depends(get_request_id),
) -> Any:
    """Get history of chain verifications."""
    try:
        service = AuditLogService(db)
        return await service.get_verifications(current_user.tenant_id, limit)
    except SQLAlchemyError as e:
        logger.exception(
            "Failed to list verifications [request_id=%s]: %s",
            request_id,
            type(e).__name__,
        )
        response.headers["X-Degraded"] = "verifications"
        return []


# ============================================================================
# Audit Log CRUD
# ============================================================================


@router.get("/", response_model=AuditLogListResponse)
async def list_audit_logs(
    db: DbSession,
    current_user: CurrentUser,
    response: Response,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    params: PaginationParams = Depends(),
    request_id: str = Depends(get_request_id),
) -> Any:
    """List audit log entries with filters and pagination."""
    try:
        service = AuditLogService(db)
        query = service.build_list_query(
            current_user.tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
        )
        track_metric("audit_trail.accessed", 1)
        return await paginate(db, query, params)
    except SQLAlchemyError as e:
        logger.exception(
            "Failed to list audit logs [request_id=%s]: %s",
            request_id,
            type(e).__name__,
        )
        response.headers["X-Degraded"] = "audit-logs"
        return {
            "items": [],
            "total": 0,
            "page": params.page,
            "page_size": params.page_size,
        }


@router.get("/entity/{entity_type}/{entity_id}", response_model=list[AuditLogDetailResponse])
async def get_entity_history(
    entity_type: str,
    entity_id: str,
    db: DbSession,
    current_user: CurrentUser,
    response: Response,
    request_id: str = Depends(get_request_id),
) -> Any:
    """Get complete audit history for a specific entity."""
    try:
        service = AuditLogService(db)
        return await service.get_entity_history(current_user.tenant_id, entity_type, entity_id)
    except SQLAlchemyError as e:
        logger.exception(
            "Failed to get entity history [request_id=%s]: %s",
            request_id,
            type(e).__name__,
        )
        response.headers["X-Degraded"] = "entity-history"
        return []


@router.get("/user/{user_id}", response_model=list[AuditLogEntryResponse])
async def get_user_activity(
    user_id: int,
    db: DbSession,
    current_user: CurrentUser,
    response: Response,
    days: int = Query(30, ge=1, le=365),
    request_id: str = Depends(get_request_id),
) -> Any:
    """Get recent activity for a specific user."""
    try:
        service = AuditLogService(db)
        return await service.get_user_activity(current_user.tenant_id, user_id, days)
    except SQLAlchemyError as e:
        logger.exception(
            "Failed to get user activity [request_id=%s]: %s",
            request_id,
            type(e).__name__,
        )
        response.headers["X-Degraded"] = "user-activity"
        return []


# ============================================================================
# Single Entry Lookup
# IMPORTANT: This parameterized route MUST be after all literal-path GET
# routes to prevent FastAPI from matching "/stats" as /{entry_id}.
# ============================================================================


@router.get("/{entry_id}", response_model=AuditLogDetailResponse)
async def get_audit_entry(
    entry_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> Any:
    """Get a single audit log entry with full details."""
    try:
        service = AuditLogService(db)
        entry = await service.get_entry_by_id(entry_id)
    except SQLAlchemyError as e:
        logger.exception(
            "Failed to get audit entry %s [request_id=%s]: %s",
            entry_id,
            request_id,
            type(e).__name__,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=ErrorCode.INTERNAL_ERROR)

    if not entry:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)

    return entry


# ============================================================================
# Chain Verification (POST)
# ============================================================================


@router.post("/verify", response_model=VerificationResponse)
async def verify_chain(
    db: DbSession,
    current_user: CurrentUser,
    start_sequence: Optional[int] = None,
    end_sequence: Optional[int] = None,
    request_id: str = Depends(get_request_id),
) -> Any:
    """
    Verify the integrity of the audit log hash chain.

    Recomputes cryptographic hashes and checks for tampering.
    """
    try:
        service = AuditLogService(db)
        return await service.verify_chain(
            current_user.tenant_id,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            verified_by_id=current_user.id,
        )
    except SQLAlchemyError as e:
        logger.exception(
            "Failed to verify chain [request_id=%s]: %s",
            request_id,
            type(e).__name__,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=ErrorCode.INTERNAL_ERROR)


# ============================================================================
# Export
# ============================================================================


@router.post("/export", response_model=AuditLogExportDataResponse)
async def export_audit_logs(
    data: ExportRequest,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> Any:
    """Export audit logs for compliance with integrity hash."""
    try:
        service = AuditLogService(db)
        exported_data, export_record = await service.export_logs(
            tenant_id=current_user.tenant_id,
            exported_by_id=current_user.id,
            export_format=data.format,
            date_from=data.date_from,
            date_to=data.date_to,
            entity_type=data.entity_type,
            reason=data.reason,
        )
        return {
            "export_id": export_record.id,
            "entries_count": len(exported_data),
            "file_hash": export_record.file_hash,
            "data": exported_data if data.format == "json" else None,
        }
    except SQLAlchemyError as e:
        logger.exception(
            "Failed to export audit logs [request_id=%s]: %s",
            request_id,
            type(e).__name__,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=ErrorCode.INTERNAL_ERROR)
