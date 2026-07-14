"""Read-only asset health KPI aggregation for the safety asset hub."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.asset import Asset, AssetType


@dataclass(frozen=True)
class AssetHealthRow:
    """Minimal asset data required to calculate health KPIs."""

    asset_type: str | None
    status: str
    expiry_date: datetime | None


def _expiry_band(expiry_date: datetime | None, *, as_of: datetime) -> str:
    if expiry_date is None:
        return "no_expiry"
    if expiry_date < as_of:
        return "overdue"
    if expiry_date < as_of + timedelta(days=30):
        return "due_30"
    if expiry_date < as_of + timedelta(days=60):
        return "due_60"
    if expiry_date < as_of + timedelta(days=90):
        return "due_90"
    return "in_date"


def aggregate_asset_health_kpis(
    rows: list[AssetHealthRow],
    *,
    as_of: datetime | None = None,
) -> dict[str, object]:
    """Aggregate asset counts by mutually exclusive expiry band, type, and status."""

    as_of = as_of or datetime.now(timezone.utc)
    expiry_bands = Counter(
        {
            "overdue": 0,
            "due_30": 0,
            "due_60": 0,
            "due_90": 0,
            "in_date": 0,
            "no_expiry": 0,
        }
    )
    by_type: Counter[str] = Counter()
    by_status: Counter[str] = Counter()

    for row in rows:
        expiry_bands[_expiry_band(row.expiry_date, as_of=as_of)] += 1
        by_type[row.asset_type or "Unclassified"] += 1
        by_status[row.status] += 1

    return {
        "total": len(rows),
        "expiry_bands": dict(expiry_bands),
        "by_type": dict(sorted(by_type.items())),
        "by_status": dict(sorted(by_status.items())),
        "generated_at": as_of,
    }


class AssetHealthAnalyticsService:
    """Tenant-scoped, read-only KPI service for safety assets."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_summary(self, tenant_id: int) -> dict[str, object]:
        result = await self.db.execute(
            select(AssetType.name, Asset.status, Asset.expiry_date)
            .outerjoin(AssetType, Asset.asset_type_id == AssetType.id)
            .where(or_(Asset.tenant_id == tenant_id, Asset.tenant_id.is_(None)))
        )
        rows = [
            AssetHealthRow(
                asset_type=asset_type,
                status=status.value if hasattr(status, "value") else str(status),
                expiry_date=expiry_date,
            )
            for asset_type, status, expiry_date in result.all()
        ]
        return aggregate_asset_health_kpis(rows)
