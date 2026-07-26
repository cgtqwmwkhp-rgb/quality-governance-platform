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


#: Statuses meaning "no longer in service". A removed asset cannot be re-certified,
#: so it is never overdue — the safety asset register takes the same view
#: (`isRemovedAsset` in frontend/src/pages/safetyAssets/safetyAssetBoardHelpers.ts).
REMOVED_ASSET_STATUSES: frozenset[str] = frozenset({"decommissioned"})


def is_removed_asset_status(status: str | None) -> bool:
    """True when the asset has left service and must be excluded from expiry bands."""
    return (status or "").strip().lower() in REMOVED_ASSET_STATUSES


def _expiry_band(expiry_date: datetime | None, *, status: str, as_of: datetime) -> str:
    if is_removed_asset_status(status):
        return "removed"
    if expiry_date is None:
        return "no_expiry"
    # Day granularity: an asset expiring at any point today is still due, not overdue.
    # Comparing raw timestamps would report a midnight-stamped expiry as overdue from
    # 00:00, contradicting the register's day-based banding for the whole of that day.
    if expiry_date.date() < as_of.date():
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
    """Aggregate asset counts by mutually exclusive expiry band, type, and status.

    Bands partition every row, so they always sum to `total`. Assets that have left
    service land in `removed` instead of `overdue`, which is what keeps this KPI equal
    to the count the safety asset register shows for the same band.
    """

    as_of = as_of or datetime.now(timezone.utc)
    expiry_bands = Counter(
        {
            "overdue": 0,
            "due_30": 0,
            "due_60": 0,
            "due_90": 0,
            "in_date": 0,
            "no_expiry": 0,
            "removed": 0,
        }
    )
    by_type: Counter[str] = Counter()
    by_status: Counter[str] = Counter()

    for row in rows:
        expiry_bands[_expiry_band(row.expiry_date, status=row.status, as_of=as_of)] += 1
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
