"""Workforce P0 spine helpers — intervals, start-gate enforcement."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.domain.error_codes import ErrorCode
from src.domain.exceptions import AuthorizationError
from src.domain.models.engineer import CompetencyRequirement
from src.domain.services.governance_service import GovernanceService

DEFAULT_REASSESSMENT_INTERVAL_DAYS = 365


async def resolve_reassessment_interval_days(
    db: AsyncSession,
    *,
    asset_type_id: Optional[int],
    template_id: Optional[int],
    tenant_id: Optional[int],
) -> int:
    """Resolve expiry interval from CompetencyRequirement — never invent scheme rules.

    Preference order:
    1. Exact asset_type + template match (tenant-scoped)
    2. Mandatory requirement for asset_type alone
    3. Column default (365) as last resort for legacy runs without a requirement row
    """
    if asset_type_id is None:
        return DEFAULT_REASSESSMENT_INTERVAL_DAYS

    if template_id is not None:
        exact = select(CompetencyRequirement).where(
            CompetencyRequirement.asset_type_id == asset_type_id,
            CompetencyRequirement.template_id == template_id,
        )
        if tenant_id is not None:
            exact = exact.where(CompetencyRequirement.tenant_id == tenant_id)
        result = await db.execute(exact.order_by(CompetencyRequirement.id).limit(1))
        row = result.scalar_one_or_none()
        if row is not None and row.reassessment_interval_days:
            return int(row.reassessment_interval_days)

    by_asset = select(CompetencyRequirement).where(
        CompetencyRequirement.asset_type_id == asset_type_id,
        CompetencyRequirement.is_mandatory.is_(True),
    )
    if tenant_id is not None:
        by_asset = by_asset.where(CompetencyRequirement.tenant_id == tenant_id)
    result = await db.execute(by_asset.order_by(CompetencyRequirement.id).limit(1))
    row = result.scalar_one_or_none()
    if row is not None and row.reassessment_interval_days:
        return int(row.reassessment_interval_days)

    return DEFAULT_REASSESSMENT_INTERVAL_DAYS


def competency_gate_mode() -> str:
    mode = (settings.competency_gate_mode or "soft").strip().lower()
    return mode if mode in {"soft", "hard"} else "soft"


async def enforce_competency_gate_on_start(
    db: AsyncSession,
    *,
    engineer_id: int,
    asset_type_id: Optional[int],
    tenant_id: Optional[int],
) -> Optional[dict[str, Any]]:
    """Apply competency gate at assessment/induction start.

    Returns gate payload when evaluated. Raises AuthorizationError in hard mode
    when not cleared. Returns None when no asset_type is set (nothing to gate).
    """
    if asset_type_id is None:
        return None

    gate = await GovernanceService.check_competency_gate(
        db,
        engineer_id=engineer_id,
        asset_type_id=asset_type_id,
        tenant_id=tenant_id,
    )
    if gate.get("cleared"):
        return {
            "cleared": True,
            "reason": None,
            "records": gate.get("records") or [],
            "active_count": gate.get("active_count"),
            "mode": competency_gate_mode(),
        }

    mode = competency_gate_mode()
    payload = {
        "cleared": False,
        "reason": gate.get("reason"),
        "records": gate.get("records") or [],
        "mode": mode,
    }
    if mode == "hard":
        raise AuthorizationError(
            gate.get("reason") or "Competency gate blocked start",
            code=ErrorCode.COMPETENCY_GATE_BLOCKED.value,
            details=payload,
        )
    return payload
