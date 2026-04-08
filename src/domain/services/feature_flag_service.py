"""Feature flag evaluation service with caching and toggle audit logging (D19)."""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.feature_flag import FeatureFlag

_audit_logger = logging.getLogger("feature_flag.audit")

_flag_cache: Dict[str, FeatureFlag] = {}


class FeatureFlagService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def is_enabled(
        self,
        key: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        flag = await self._get_flag(key)
        if not flag:
            return False
        if not flag.enabled:
            return False
        if tenant_id and flag.tenant_overrides:
            override = flag.tenant_overrides.get(str(tenant_id))
            if override is not None:
                return override
        if flag.rollout_percentage >= 100:
            return True
        if flag.rollout_percentage <= 0:
            return False
        bucket = (
            int(
                hashlib.md5(
                    f"{key}:{user_id or tenant_id or 'default'}".encode(),
                    usedforsecurity=False,
                ).hexdigest(),
                16,
            )
            % 100
        )
        return bool(bucket < flag.rollout_percentage)

    async def _get_flag(self, key: str) -> Optional[FeatureFlag]:
        if key in _flag_cache:
            return _flag_cache[key]
        result = await self.db.execute(select(FeatureFlag).where(FeatureFlag.key == key))
        flag = result.scalar_one_or_none()
        if flag:
            _flag_cache[key] = flag
        return flag

    async def list_flags(self) -> List[FeatureFlag]:
        result = await self.db.execute(select(FeatureFlag).order_by(FeatureFlag.key))
        return list(result.scalars().all())

    def _emit_toggle_audit(
        self,
        action: str,
        key: str,
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
        actor: str = "system",
    ) -> None:
        """Emit a structured audit log entry for every flag create/update/delete.

        Log entries are machine-parseable JSON via Python's structured logging.
        In production these are shipped to Azure Monitor via the OTel log exporter.
        """
        _audit_logger.info(
            "feature_flag_toggle",
            extra={
                "event": "feature_flag_toggle",
                "action": action,
                "flag_key": key,
                "before": before,
                "after": after,
                "actor": actor,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def create_flag(
        self,
        key: str,
        name: str,
        description: str = "",
        enabled: bool = False,
        rollout_percentage: int = 0,
        created_by: str = "",
    ) -> FeatureFlag:
        flag = FeatureFlag(
            key=key,
            name=name,
            description=description,
            enabled=enabled,
            rollout_percentage=rollout_percentage,
            created_by=created_by,
        )
        self.db.add(flag)
        await self.db.flush()
        _flag_cache[key] = flag
        self._emit_toggle_audit(
            action="create",
            key=key,
            after={"enabled": enabled, "rollout_percentage": rollout_percentage, "name": name},
            actor=created_by or "system",
        )
        return flag

    async def update_flag(self, key: str, actor: str = "system", **kwargs) -> Optional[FeatureFlag]:
        flag = await self._get_flag(key)
        if not flag:
            return None
        before = {k: getattr(flag, k) for k in kwargs if hasattr(flag, k)}
        for k, v in kwargs.items():
            if hasattr(flag, k):
                setattr(flag, k, v)
        await self.db.flush()
        _flag_cache[key] = flag
        after = {k: getattr(flag, k) for k in kwargs if hasattr(flag, k)}
        self._emit_toggle_audit(action="update", key=key, before=before, after=after, actor=actor)
        return flag

    async def delete_flag(self, key: str, actor: str = "system") -> bool:
        flag = await self._get_flag(key)
        if not flag:
            return False
        before = {"enabled": flag.enabled, "rollout_percentage": flag.rollout_percentage, "name": flag.name}
        await self.db.delete(flag)
        _flag_cache.pop(key, None)
        self._emit_toggle_audit(action="delete", key=key, before=before, actor=actor)
        return True

    @staticmethod
    def clear_cache():
        _flag_cache.clear()
