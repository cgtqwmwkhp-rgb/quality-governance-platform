"""
Immutable Audit Log Service

Provides blockchain-style audit logging with:
- Hash chain integrity
- Tamper detection
- Complete change history
- Compliance-grade audit trail
- Verification and export
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit_log import AuditLogEntry, AuditLogExport, AuditLogVerification


class AuditLogService:
    """
    Immutable audit logging with blockchain-style hash chain.
    """

    # Genesis hash for first entry
    GENESIS_HASH = "0" * 64

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Logging
    # =========================================================================

    async def log(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
        action: str,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        user_name: Optional[str] = None,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        is_sensitive: bool = False,
        entity_name: Optional[str] = None,
        action_category: str = "data",
        user_role: Optional[str] = None,
    ) -> AuditLogEntry:
        """
        Create an immutable audit log entry.

        Each entry is linked to the previous via cryptographic hash,
        creating a tamper-evident chain.
        """
        # Get the previous entry for hash chain
        result = await self.db.execute(
            select(AuditLogEntry)
            .where(AuditLogEntry.tenant_id == tenant_id)
            .order_by(desc(AuditLogEntry.sequence))
            .limit(1)
        )
        previous_entry = result.scalar_one_or_none()

        if previous_entry:
            sequence = previous_entry.sequence + 1
            previous_hash = previous_entry.entry_hash
        else:
            sequence = 1
            previous_hash = self.GENESIS_HASH

        # Calculate changed fields
        changed_fields = None
        if old_values and new_values:
            changed_fields = [
                k for k in set(old_values.keys()) | set(new_values.keys()) if old_values.get(k) != new_values.get(k)
            ]

        timestamp = datetime.now(timezone.utc)

        # Compute entry hash
        entry_hash = AuditLogEntry.compute_hash(
            sequence=sequence,
            previous_hash=previous_hash,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            timestamp=timestamp,
            old_values=old_values,
            new_values=new_values,
        )

        # Create entry
        entry = AuditLogEntry(
            tenant_id=tenant_id,
            sequence=sequence,
            entry_hash=entry_hash,
            previous_hash=previous_hash,
            entity_type=entity_type,
            entity_id=str(entity_id),
            entity_name=entity_name,
            action=action,
            action_category=action_category,
            old_values=old_values,
            new_values=new_values,
            changed_fields=changed_fields,
            user_id=user_id,
            user_email=user_email,
            user_name=user_name,
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            session_id=session_id,
            entry_metadata=metadata or {},
            timestamp=timestamp,
            is_sensitive=is_sensitive,
        )

        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)

        return entry

    async def log_create(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
        new_values: dict,
        **kwargs,
    ) -> AuditLogEntry:
        """Log a create action."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action="create",
            new_values=new_values,
            **kwargs,
        )

    async def log_update(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
        old_values: dict,
        new_values: dict,
        **kwargs,
    ) -> AuditLogEntry:
        """Log an update action."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action="update",
            old_values=old_values,
            new_values=new_values,
            **kwargs,
        )

    async def log_delete(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
        old_values: dict,
        **kwargs,
    ) -> AuditLogEntry:
        """Log a delete action."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action="delete",
            old_values=old_values,
            **kwargs,
        )

    async def log_view(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
        **kwargs,
    ) -> AuditLogEntry:
        """Log a view/read action."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action="view",
            **kwargs,
        )

    async def log_auth(
        self,
        tenant_id: int,
        action: str,  # login, logout, login_failed, password_change, etc.
        user_id: Optional[int] = None,
        **kwargs,
    ) -> AuditLogEntry:
        """Log an authentication action."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type="auth",
            entity_id=str(user_id) if user_id else "anonymous",
            action=action,
            action_category="auth",
            user_id=user_id,
            **kwargs,
        )

    async def log_admin(
        self,
        tenant_id: int,
        action: str,
        entity_type: str,
        entity_id: str,
        **kwargs,
    ) -> AuditLogEntry:
        """Log an administrative action."""
        return await self.log(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            action_category="admin",
            **kwargs,
        )

    # =========================================================================
    # Querying
    # =========================================================================

    async def get_entries(
        self,
        tenant_id: int,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
        user_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """Query audit log entries with filters."""
        stmt = select(AuditLogEntry).where(AuditLogEntry.tenant_id == tenant_id)

        if entity_type:
            stmt = stmt.where(AuditLogEntry.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AuditLogEntry.entity_id == entity_id)
        if action:
            stmt = stmt.where(AuditLogEntry.action == action)
        if user_id:
            stmt = stmt.where(AuditLogEntry.user_id == user_id)
        if date_from:
            stmt = stmt.where(AuditLogEntry.timestamp >= date_from)
        if date_to:
            stmt = stmt.where(AuditLogEntry.timestamp <= date_to)

        stmt = stmt.order_by(desc(AuditLogEntry.timestamp)).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_entity_history(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
    ) -> list[AuditLogEntry]:
        """Get complete history for an entity."""
        result = await self.db.execute(
            select(AuditLogEntry)
            .where(
                AuditLogEntry.tenant_id == tenant_id,
                AuditLogEntry.entity_type == entity_type,
                AuditLogEntry.entity_id == entity_id,
            )
            .order_by(AuditLogEntry.timestamp)
        )
        return list(result.scalars().all())

    async def get_user_activity(
        self,
        tenant_id: int,
        user_id: int,
        days: int = 30,
    ) -> list[AuditLogEntry]:
        """Get recent activity for a user."""
        date_from = datetime.now(timezone.utc) - timedelta(days=days)
        return await self.get_entries(
            tenant_id=tenant_id,
            user_id=user_id,
            date_from=date_from,
        )

    # =========================================================================
    # Verification
    # =========================================================================

    async def verify_chain(
        self,
        tenant_id: int,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None,
        verified_by_id: Optional[int] = None,
    ) -> AuditLogVerification:
        """
        Verify the integrity of the audit log hash chain.

        Detects any tampering by recomputing and comparing hashes.
        """
        stmt = select(AuditLogEntry).where(AuditLogEntry.tenant_id == tenant_id)

        if start_sequence is not None:
            stmt = stmt.where(AuditLogEntry.sequence >= start_sequence)
        if end_sequence is not None:
            stmt = stmt.where(AuditLogEntry.sequence <= end_sequence)

        stmt = stmt.order_by(AuditLogEntry.sequence)
        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        if not entries:
            # No entries to verify
            return AuditLogVerification(
                tenant_id=tenant_id,
                start_sequence=start_sequence or 0,
                end_sequence=end_sequence or 0,
                is_valid=True,
                entries_verified=0,
                verified_by_id=verified_by_id,
            )

        invalid_entries = []
        previous_hash = self.GENESIS_HASH

        for entry in entries:
            # Verify hash chain link
            if entry.previous_hash != previous_hash:
                invalid_entries.append(
                    {
                        "sequence": entry.sequence,
                        "error": "Previous hash mismatch",
                        "expected": previous_hash,
                        "actual": entry.previous_hash,
                    }
                )

            # Verify entry hash
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

        # Record verification result
        verification = AuditLogVerification(
            tenant_id=tenant_id,
            start_sequence=entries[0].sequence,
            end_sequence=entries[-1].sequence,
            is_valid=len(invalid_entries) == 0,
            entries_verified=len(entries),
            invalid_entries=invalid_entries if invalid_entries else None,
            verified_by_id=verified_by_id,
        )

        self.db.add(verification)
        await self.db.commit()
        await self.db.refresh(verification)

        return verification

    async def get_verifications(
        self,
        tenant_id: int,
        limit: int = 10,
    ) -> list[AuditLogVerification]:
        """Get recent verification records."""
        result = await self.db.execute(
            select(AuditLogVerification)
            .where(AuditLogVerification.tenant_id == tenant_id)
            .order_by(desc(AuditLogVerification.verified_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    # =========================================================================
    # Export
    # =========================================================================

    async def export_logs(
        self,
        tenant_id: int,
        exported_by_id: int,
        export_format: str = "json",
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        entity_type: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> tuple[list[dict], AuditLogExport]:
        """
        Export audit logs with compliance tracking.

        Returns:
            Tuple of (exported_data, export_record)
        """
        entries = await self.get_entries(
            tenant_id=tenant_id,
            entity_type=entity_type,
            date_from=date_from,
            date_to=date_to,
            limit=100000,  # Large limit for export
        )

        # Convert to exportable format
        data = []
        for entry in entries:
            data.append(
                {
                    "sequence": entry.sequence,
                    "timestamp": entry.timestamp.isoformat(),
                    "entity_type": entry.entity_type,
                    "entity_id": entry.entity_id,
                    "entity_name": entry.entity_name,
                    "action": entry.action,
                    "user_id": entry.user_id,
                    "user_email": entry.user_email,
                    "user_name": entry.user_name,
                    "old_values": entry.old_values,
                    "new_values": entry.new_values,
                    "changed_fields": entry.changed_fields,
                    "ip_address": entry.ip_address,
                    "entry_hash": entry.entry_hash,
                }
            )

        # Compute hash of export for integrity
        export_hash = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

        # Record the export
        export_record = AuditLogExport(
            tenant_id=tenant_id,
            export_format=export_format,
            export_type="filtered" if (date_from or date_to or entity_type) else "full",
            filters={
                "entity_type": entity_type,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
            },
            date_from=date_from,
            date_to=date_to,
            entries_exported=len(data),
            file_hash=export_hash,
            exported_by_id=exported_by_id,
            reason=reason,
        )

        self.db.add(export_record)
        await self.db.commit()
        await self.db.refresh(export_record)

        return data, export_record

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self, tenant_id: int, days: int = 30) -> dict:
        """Get audit log statistics."""
        date_from = datetime.now(timezone.utc) - timedelta(days=days)

        # Total entries
        result = await self.db.execute(
            select(func.count(AuditLogEntry.id)).where(
                AuditLogEntry.tenant_id == tenant_id,
                AuditLogEntry.timestamp >= date_from,
            )
        )
        total: int = result.scalar() or 0

        # By action
        result = await self.db.execute(
            select(AuditLogEntry.action, func.count(AuditLogEntry.id))
            .where(
                AuditLogEntry.tenant_id == tenant_id,
                AuditLogEntry.timestamp >= date_from,
            )
            .group_by(AuditLogEntry.action)
        )
        by_action: dict[str, int] = dict(result.all())  # type: ignore[arg-type]  # TYPE-IGNORE: MYPY-OVERRIDE

        # By entity type
        result = await self.db.execute(
            select(AuditLogEntry.entity_type, func.count(AuditLogEntry.id))
            .where(
                AuditLogEntry.tenant_id == tenant_id,
                AuditLogEntry.timestamp >= date_from,
            )
            .group_by(AuditLogEntry.entity_type)
        )
        by_entity: dict[str, int] = dict(result.all())  # type: ignore[arg-type]  # TYPE-IGNORE: MYPY-OVERRIDE

        # Most active users
        result = await self.db.execute(
            select(AuditLogEntry.user_email, func.count(AuditLogEntry.id))
            .where(
                AuditLogEntry.tenant_id == tenant_id,
                AuditLogEntry.timestamp >= date_from,
                AuditLogEntry.user_email != None,
            )
            .group_by(AuditLogEntry.user_email)
            .order_by(desc(func.count(AuditLogEntry.id)))
            .limit(10)
        )
        top_users: list[Any] = list(result.all())

        return {
            "total_entries": total,
            "by_action": by_action,
            "by_entity_type": by_entity,
            "top_users": [{"email": u[0], "count": u[1]} for u in top_users],
            "period_days": days,
        }
