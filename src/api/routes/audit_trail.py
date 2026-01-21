"""
Immutable Audit Trail API Routes

Provides endpoints for:
- Viewing audit logs
- Verifying chain integrity
- Exporting logs for compliance
- Statistics and analytics
"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.domain.services.audit_log_service import AuditLogService


router = APIRouter()


# ============================================================================
# Schemas
# ============================================================================


class AuditLogEntryResponse(BaseModel):
    id: int
    sequence: int
    entry_hash: str
    entity_type: str
    entity_id: str
    entity_name: Optional[str]
    action: str
    action_category: str
    user_id: Optional[int]
    user_email: Optional[str]
    user_name: Optional[str]
    changed_fields: Optional[list]
    ip_address: Optional[str]
    timestamp: datetime
    is_sensitive: bool

    class Config:
        from_attributes = True


class AuditLogDetailResponse(AuditLogEntryResponse):
    old_values: Optional[dict]
    new_values: Optional[dict]
    metadata: dict


class VerificationResponse(BaseModel):
    id: int
    start_sequence: int
    end_sequence: int
    is_valid: bool
    entries_verified: int
    invalid_entries: Optional[list]
    verified_at: datetime

    class Config:
        from_attributes = True


class ExportRequest(BaseModel):
    format: str = "json"  # json, csv
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    entity_type: Optional[str] = None
    reason: Optional[str] = None


# ============================================================================
# Audit Log Endpoints
# ============================================================================


@router.get("/", response_model=list[AuditLogEntryResponse])
def list_audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Any:
    """List audit log entries with filters."""
    service = AuditLogService(db)
    tenant_id = 1  # Should come from request context

    entries = service.get_entries(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    return entries


@router.get("/entity/{entity_type}/{entity_id}", response_model=list[AuditLogDetailResponse])
def get_entity_history(
    entity_type: str,
    entity_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Get complete audit history for an entity."""
    service = AuditLogService(db)
    tenant_id = 1  # Should come from request context

    entries = service.get_entity_history(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    return entries


@router.get("/user/{user_id}", response_model=list[AuditLogEntryResponse])
def get_user_activity(
    user_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> Any:
    """Get recent activity for a user."""
    service = AuditLogService(db)
    tenant_id = 1  # Should come from request context

    entries = service.get_user_activity(
        tenant_id=tenant_id,
        user_id=user_id,
        days=days,
    )

    return entries


@router.get("/{entry_id}", response_model=AuditLogDetailResponse)
def get_audit_entry(
    entry_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Get a single audit log entry with full details."""
    from src.domain.models.audit_log import AuditLogEntry

    entry = db.query(AuditLogEntry).filter(AuditLogEntry.id == entry_id).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    return entry


# ============================================================================
# Chain Verification
# ============================================================================


@router.post("/verify", response_model=VerificationResponse)
def verify_chain(
    start_sequence: Optional[int] = None,
    end_sequence: Optional[int] = None,
    db: Session = Depends(get_db),
) -> Any:
    """
    Verify the integrity of the audit log hash chain.

    This checks that no entries have been tampered with by recomputing
    and comparing cryptographic hashes.
    """
    service = AuditLogService(db)
    tenant_id = 1  # Should come from request context
    user_id = 1  # Should be current_user.id

    verification = service.verify_chain(
        tenant_id=tenant_id,
        start_sequence=start_sequence,
        end_sequence=end_sequence,
        verified_by_id=user_id,
    )

    return verification


@router.get("/verifications", response_model=list[VerificationResponse])
def list_verifications(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> Any:
    """Get history of chain verifications."""
    service = AuditLogService(db)
    tenant_id = 1  # Should come from request context

    verifications = service.get_verifications(
        tenant_id=tenant_id,
        limit=limit,
    )

    return verifications


# ============================================================================
# Export
# ============================================================================


@router.post("/export")
def export_audit_logs(
    data: ExportRequest,
    db: Session = Depends(get_db),
) -> Any:
    """
    Export audit logs for compliance.

    Returns the exported data and creates a record of the export
    for audit purposes.
    """
    service = AuditLogService(db)
    tenant_id = 1  # Should come from request context
    user_id = 1  # Should be current_user.id

    exported_data, export_record = service.export_logs(
        tenant_id=tenant_id,
        exported_by_id=user_id,
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


# ============================================================================
# Statistics
# ============================================================================


@router.get("/stats")
def get_audit_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> Any:
    """Get audit log statistics."""
    service = AuditLogService(db)
    tenant_id = 1  # Should come from request context

    stats = service.get_stats(tenant_id=tenant_id, days=days)

    return stats


# ============================================================================
# Actions Reference
# ============================================================================


@router.get("/actions")
def list_actions() -> Any:
    """Get list of possible audit actions."""
    return {
        "data": ["create", "update", "delete", "view", "export", "approve", "reject", "assign"],
        "auth": ["login", "logout", "login_failed", "password_change", "password_reset", "mfa_enabled", "mfa_disabled"],
        "admin": [
            "user_created",
            "user_deleted",
            "role_changed",
            "permission_granted",
            "permission_revoked",
            "settings_changed",
        ],
        "system": ["backup_created", "backup_restored", "migration_run", "maintenance_started", "maintenance_ended"],
    }


@router.get("/entity-types")
def list_entity_types() -> Any:
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
