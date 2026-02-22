"""GDPR compliance service for data export and erasure."""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class GDPRService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def export_user_data(self, user_id: int, tenant_id: int) -> dict[str, Any]:
        """Export all user data (Right of Access, GDPR Art. 15)."""
        from src.domain.models.user import User
        
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            from src.domain.exceptions import NotFoundError
            raise NotFoundError("User not found")
        
        data: dict[str, Any] = {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "user_profile": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "job_title": user.job_title,
                "department": user.department,
                "created_at": str(user.created_at) if user.created_at else None,
            },
            "incidents": await self._collect_user_entities("Incident", "reporter_id", user_id, tenant_id),
            "complaints": await self._collect_user_entities("Complaint", "owner_id", user_id, tenant_id),
            "incident_actions": await self._collect_user_entities("IncidentAction", "owner_id", user_id, tenant_id),
            "complaint_actions": await self._collect_user_entities("ComplaintAction", "owner_id", user_id, tenant_id),
            "audit_log": await self._collect_audit_entries(user_id, tenant_id),
        }
        return data
    
    async def _collect_user_entities(self, model_name: str, user_field: str, user_id: int, tenant_id: int) -> list[dict]:
        """Collect entities associated with a user."""
        try:
            # Handle action models that don't have tenant_id directly
            if model_name == "IncidentAction":
                from src.domain.models.incident import Incident, IncidentAction
                user_col = getattr(IncidentAction, user_field, None)
                if user_col is None:
                    return []
                stmt = (
                    select(IncidentAction)
                    .join(Incident, IncidentAction.incident_id == Incident.id)
                    .where(
                        user_col == user_id,
                        Incident.tenant_id == tenant_id
                    )
                    .limit(1000)
                )
                model_class = IncidentAction
            elif model_name == "ComplaintAction":
                from src.domain.models.complaint import Complaint, ComplaintAction
                user_col = getattr(ComplaintAction, user_field, None)
                if user_col is None:
                    return []
                stmt = (
                    select(ComplaintAction)
                    .join(Complaint, ComplaintAction.complaint_id == Complaint.id)
                    .where(
                        user_col == user_id,
                        Complaint.tenant_id == tenant_id
                    )
                    .limit(1000)
                )
                model_class = ComplaintAction
            elif model_name == "Incident":
                from src.domain.models.incident import Incident
                model_class = Incident
                user_col = getattr(model_class, user_field, None)
                if user_col is None:
                    return []
                stmt = select(model_class).where(
                    user_col == user_id,
                    model_class.tenant_id == tenant_id
                ).limit(1000)
            elif model_name == "Complaint":
                from src.domain.models.complaint import Complaint
                model_class = Complaint
                user_col = getattr(model_class, user_field, None)
                if user_col is None:
                    return []
                stmt = select(model_class).where(
                    user_col == user_id,
                    model_class.tenant_id == tenant_id
                ).limit(1000)
            else:
                # Generic fallback for other models
                import importlib
                model_module = importlib.import_module(f"src.domain.models.{model_name.lower()}")
                model_class = getattr(model_module, model_name)
                user_col = getattr(model_class, user_field, None)
                if user_col is None:
                    return []
                stmt = select(model_class).where(
                    user_col == user_id,
                    model_class.tenant_id == tenant_id
                ).limit(1000)
            
            result = await self.db.execute(stmt)
            entities = result.scalars().all()
            return [{"id": e.id, "type": model_name, "created_at": str(getattr(e, "created_at", ""))} for e in entities]
        except Exception as ex:
            logger.warning("GDPR export: could not collect %s: %s", model_name, ex)
            return []
    
    async def _collect_audit_entries(self, user_id: int, tenant_id: int) -> list[dict]:
        """Collect audit log entries for the user."""
        try:
            from src.domain.models.audit_log import AuditLogEntry
            stmt = select(AuditLogEntry).where(
                AuditLogEntry.user_id == user_id,
                AuditLogEntry.tenant_id == tenant_id,
            ).order_by(AuditLogEntry.timestamp.desc()).limit(5000)
            result = await self.db.execute(stmt)
            entries = result.scalars().all()
            return [
                {"timestamp": str(e.timestamp), "action": e.action, "entity_type": e.entity_type, "entity_id": e.entity_id}
                for e in entries
            ]
        except Exception as ex:
            logger.warning("GDPR export: audit entries unavailable: %s", ex)
            return []
    
    async def request_erasure(self, user_id: int, tenant_id: int, reason: str = "") -> dict:
        """Initiate data erasure request (Right to Erasure, GDPR Art. 17)."""
        from src.domain.models.user import User
        
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            from src.domain.exceptions import NotFoundError
            raise NotFoundError("User not found")
        
        # Anonymize PII
        user.email = f"deleted-{user.id}@anonymized.local"
        user.first_name = "REDACTED"
        user.last_name = "REDACTED"
        user.phone = None
        user.job_title = None
        user.department = None
        user.is_active = False
        
        await self.db.commit()
        
        return {
            "status": "completed",
            "user_id": user_id,
            "anonymized_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }
