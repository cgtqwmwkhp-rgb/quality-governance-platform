"""
Immutable Audit Trail API Routes

Provides endpoints for:
- Viewing audit logs with pagination
- Verifying chain integrity
- Exporting logs for compliance
- Statistics and analytics
- Reference data for actions and entity types
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select

from src.api.dependencies import DbSession
from src.domain.models.audit_log import AuditLogEntry, AuditLogExport, AuditLogVerification

router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_TENANT_ID = 1


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
    per_page: int


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


@router.get("/actions")
async def list_actions() -> Any:
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


@router.get("/entity-types")
async def list_entity_types() -> Any:
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
    days: int = Query(30, ge=1, le=365),
) -> Any:
    """Get audit log statistics for the specified period."""
    tenant_id = DEFAULT_TENANT_ID
    date_from = datetime.utcnow() - timedelta(days=days)

    try:
        total_result = await db.execute(
            select(func.count(AuditLogEntry.id)).where(
                AuditLogEntry.tenant_id == tenant_id,
                AuditLogEntry.timestamp >= date_from,
            )
        )
        total = total_result.scalar() or 0

        action_result = await db.execute(
            select(AuditLogEntry.action, func.count(AuditLogEntry.id))
            .where(
                AuditLogEntry.tenant_id == tenant_id,
                AuditLogEntry.timestamp >= date_from,
            )
            .group_by(AuditLogEntry.action)
        )
        by_action = dict(action_result.all())

        entity_result = await db.execute(
            select(AuditLogEntry.entity_type, func.count(AuditLogEntry.id))
            .where(
                AuditLogEntry.tenant_id == tenant_id,
                AuditLogEntry.timestamp >= date_from,
            )
            .group_by(AuditLogEntry.entity_type)
        )
        by_entity = dict(entity_result.all())

        user_result = await db.execute(
            select(AuditLogEntry.user_email, func.count(AuditLogEntry.id))
            .where(
                AuditLogEntry.tenant_id == tenant_id,
                AuditLogEntry.timestamp >= date_from,
                AuditLogEntry.user_email.isnot(None),
            )
            .group_by(AuditLogEntry.user_email)
            .order_by(desc(func.count(AuditLogEntry.id)))
            .limit(10)
        )
        top_users = [{"email": row[0], "count": row[1]} for row in user_result.all()]

        return {
            "total_entries": total,
            "by_action": by_action,
            "by_entity_type": by_entity,
            "top_users": top_users,
            "period_days": days,
        }
    except Exception as e:
        logger.error("Failed to get audit stats: %s", e)
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
    limit: int = Query(10, ge=1, le=50),
) -> Any:
    """Get history of chain verifications."""
    tenant_id = DEFAULT_TENANT_ID

    try:
        result = await db.execute(
            select(AuditLogVerification)
            .where(AuditLogVerification.tenant_id == tenant_id)
            .order_by(desc(AuditLogVerification.verified_at))
            .limit(limit)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error("Failed to list verifications: %s", e)
        return []


# ============================================================================
# Audit Log CRUD
# ============================================================================


@router.get("/", response_model=AuditLogListResponse)
async def list_audit_logs(
    db: DbSession,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
) -> Any:
    """List audit log entries with filters and pagination."""
    tenant_id = DEFAULT_TENANT_ID

    try:
        conditions = [AuditLogEntry.tenant_id == tenant_id]
        if entity_type:
            conditions.append(AuditLogEntry.entity_type == entity_type)
        if entity_id:
            conditions.append(AuditLogEntry.entity_id == entity_id)
        if action:
            conditions.append(AuditLogEntry.action == action)
        if user_id:
            conditions.append(AuditLogEntry.user_id == user_id)
        if date_from:
            conditions.append(AuditLogEntry.timestamp >= date_from)
        if date_to:
            conditions.append(AuditLogEntry.timestamp <= date_to)

        count_result = await db.execute(select(func.count(AuditLogEntry.id)).where(*conditions))
        total = count_result.scalar() or 0

        offset = (page - 1) * per_page
        result = await db.execute(
            select(AuditLogEntry)
            .where(*conditions)
            .order_by(desc(AuditLogEntry.timestamp))
            .offset(offset)
            .limit(per_page)
        )
        entries = result.scalars().all()

        return {
            "items": entries,
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    except Exception as e:
        logger.error("Failed to list audit logs: %s", e)
        return {
            "items": [],
            "total": 0,
            "page": page,
            "per_page": per_page,
        }


@router.get("/entity/{entity_type}/{entity_id}", response_model=list[AuditLogDetailResponse])
async def get_entity_history(
    entity_type: str,
    entity_id: str,
    db: DbSession,
) -> Any:
    """Get complete audit history for a specific entity."""
    tenant_id = DEFAULT_TENANT_ID

    try:
        result = await db.execute(
            select(AuditLogEntry)
            .where(
                AuditLogEntry.tenant_id == tenant_id,
                AuditLogEntry.entity_type == entity_type,
                AuditLogEntry.entity_id == entity_id,
            )
            .order_by(AuditLogEntry.timestamp)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error("Failed to get entity history: %s", e)
        return []


@router.get("/user/{user_id}", response_model=list[AuditLogEntryResponse])
async def get_user_activity(
    user_id: int,
    db: DbSession,
    days: int = Query(30, ge=1, le=365),
) -> Any:
    """Get recent activity for a specific user."""
    tenant_id = DEFAULT_TENANT_ID
    date_from = datetime.utcnow() - timedelta(days=days)

    try:
        result = await db.execute(
            select(AuditLogEntry)
            .where(
                AuditLogEntry.tenant_id == tenant_id,
                AuditLogEntry.user_id == user_id,
                AuditLogEntry.timestamp >= date_from,
            )
            .order_by(desc(AuditLogEntry.timestamp))
            .limit(100)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error("Failed to get user activity: %s", e)
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
) -> Any:
    """Get a single audit log entry with full details."""
    try:
        result = await db.execute(select(AuditLogEntry).where(AuditLogEntry.id == entry_id))
        entry = result.scalar_one_or_none()
    except Exception as e:
        logger.error("Failed to get audit entry %s: %s", entry_id, e)
        raise HTTPException(status_code=500, detail="Failed to retrieve audit entry")

    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    return entry


# ============================================================================
# Chain Verification (POST)
# ============================================================================


@router.post("/verify", response_model=VerificationResponse)
async def verify_chain(
    db: DbSession,
    start_sequence: Optional[int] = None,
    end_sequence: Optional[int] = None,
) -> Any:
    """
    Verify the integrity of the audit log hash chain.

    Recomputes cryptographic hashes and checks for tampering.
    """
    tenant_id = DEFAULT_TENANT_ID
    verified_by = 1

    try:
        stmt = select(AuditLogEntry).where(AuditLogEntry.tenant_id == tenant_id)
        if start_sequence is not None:
            stmt = stmt.where(AuditLogEntry.sequence >= start_sequence)
        if end_sequence is not None:
            stmt = stmt.where(AuditLogEntry.sequence <= end_sequence)
        stmt = stmt.order_by(AuditLogEntry.sequence)

        result = await db.execute(stmt)
        entries = result.scalars().all()

        if not entries:
            verification = AuditLogVerification(
                tenant_id=tenant_id,
                start_sequence=start_sequence or 0,
                end_sequence=end_sequence or 0,
                is_valid=True,
                entries_verified=0,
                verified_by_id=verified_by,
            )
            db.add(verification)
            await db.flush()
            await db.refresh(verification)
            return verification

        genesis_hash = "0" * 64
        invalid_entries = []
        previous_hash = genesis_hash

        for entry in entries:
            if entry.previous_hash != previous_hash:
                invalid_entries.append(
                    {
                        "sequence": entry.sequence,
                        "error": "Previous hash mismatch",
                        "expected": previous_hash,
                        "actual": entry.previous_hash,
                    }
                )

            computed_hash = AuditLogEntry.compute_hash(
                sequence=entry.sequence,
                previous_hash=entry.previous_hash,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                action=entry.action,
                user_id=entry.user_id,
                timestamp=entry.timestamp,
                old_values=entry.old_values,
                new_values=entry.new_values,
            )

            if computed_hash != entry.entry_hash:
                invalid_entries.append(
                    {
                        "sequence": entry.sequence,
                        "error": "Entry hash mismatch",
                        "expected": computed_hash,
                        "actual": entry.entry_hash,
                    }
                )

            previous_hash = entry.entry_hash

        verification = AuditLogVerification(
            tenant_id=tenant_id,
            start_sequence=entries[0].sequence,
            end_sequence=entries[-1].sequence,
            is_valid=len(invalid_entries) == 0,
            entries_verified=len(entries),
            invalid_entries=invalid_entries if invalid_entries else None,
            verified_by_id=verified_by,
        )

        db.add(verification)
        await db.flush()
        await db.refresh(verification)
        return verification
    except Exception as e:
        logger.error("Failed to verify chain: %s", e)
        raise HTTPException(status_code=500, detail="Chain verification failed")


# ============================================================================
# Export
# ============================================================================


@router.post("/export")
async def export_audit_logs(
    data: ExportRequest,
    db: DbSession,
) -> Any:
    """Export audit logs for compliance with integrity hash."""
    tenant_id = DEFAULT_TENANT_ID
    exported_by = 1

    try:
        stmt = select(AuditLogEntry).where(AuditLogEntry.tenant_id == tenant_id)
        if data.entity_type:
            stmt = stmt.where(AuditLogEntry.entity_type == data.entity_type)
        if data.date_from:
            stmt = stmt.where(AuditLogEntry.timestamp >= data.date_from)
        if data.date_to:
            stmt = stmt.where(AuditLogEntry.timestamp <= data.date_to)
        stmt = stmt.order_by(desc(AuditLogEntry.timestamp)).limit(100000)

        result = await db.execute(stmt)
        entries = result.scalars().all()

        exported_data = [
            {
                "sequence": e.sequence,
                "timestamp": e.timestamp.isoformat(),
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "entity_name": e.entity_name,
                "action": e.action,
                "user_id": e.user_id,
                "user_email": e.user_email,
                "user_name": e.user_name,
                "old_values": e.old_values,
                "new_values": e.new_values,
                "changed_fields": e.changed_fields,
                "ip_address": e.ip_address,
                "entry_hash": e.entry_hash,
            }
            for e in entries
        ]

        export_hash = hashlib.sha256(json.dumps(exported_data, sort_keys=True, default=str).encode()).hexdigest()

        export_record = AuditLogExport(
            tenant_id=tenant_id,
            export_format=data.format,
            export_type="filtered" if (data.date_from or data.date_to or data.entity_type) else "full",
            filters={
                "entity_type": data.entity_type,
                "date_from": data.date_from.isoformat() if data.date_from else None,
                "date_to": data.date_to.isoformat() if data.date_to else None,
            },
            date_from=data.date_from,
            date_to=data.date_to,
            entries_exported=len(exported_data),
            file_hash=export_hash,
            exported_by_id=exported_by,
            reason=data.reason,
        )

        db.add(export_record)
        await db.flush()
        await db.refresh(export_record)

        return {
            "export_id": export_record.id,
            "entries_count": len(exported_data),
            "file_hash": export_hash,
            "data": exported_data if data.format == "json" else None,
        }
    except Exception as e:
        logger.error("Failed to export audit logs: %s", e)
        raise HTTPException(status_code=500, detail="Export failed")
