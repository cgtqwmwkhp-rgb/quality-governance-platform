"""PX-211: dashboard overdue-asset KPI must equal the safety asset register's count.

The register never calls a removed asset overdue — you cannot re-certify equipment that
has left service (`isOverdueAsset` in safetyAssetBoardHelpers.ts). The dashboard KPI
banded every row by expiry date regardless of status, so long-expired decommissioned
stock inflated it: 871 on the dashboard against 427 in the register, with 463 removed
assets sitting in the gap.
"""

from datetime import datetime, timedelta, timezone

from src.domain.services.asset_health_analytics_service import (
    REMOVED_ASSET_STATUSES,
    AssetHealthRow,
    aggregate_asset_health_kpis,
    is_removed_asset_status,
)

AS_OF = datetime(2026, 7, 26, 9, 30, tzinfo=timezone.utc)
LONG_EXPIRED = AS_OF - timedelta(days=400)


def _bands(rows: list[AssetHealthRow]) -> dict[str, int]:
    return aggregate_asset_health_kpis(rows, as_of=AS_OF)["expiry_bands"]


def test_removed_assets_are_not_overdue():
    rows = [
        AssetHealthRow("Harness", "active", LONG_EXPIRED),
        AssetHealthRow("Harness", "decommissioned", LONG_EXPIRED),
        AssetHealthRow("Harness", "decommissioned", LONG_EXPIRED),
    ]

    bands = _bands(rows)

    assert bands["overdue"] == 1, "only the in-service expired asset is overdue"
    assert bands["removed"] == 2


def test_overdue_counts_only_in_service_stock_at_register_scale():
    """Reproduces the reported split: 1445 in service + 463 removed = 1908 total."""
    rows = (
        [AssetHealthRow("Harness", "active", LONG_EXPIRED) for _ in range(427)]
        + [AssetHealthRow("Harness", "active", AS_OF + timedelta(days=200)) for _ in range(1018)]
        + [AssetHealthRow("Harness", "decommissioned", LONG_EXPIRED) for _ in range(444)]
        + [AssetHealthRow("Harness", "decommissioned", AS_OF + timedelta(days=200)) for _ in range(19)]
    )

    summary = aggregate_asset_health_kpis(rows, as_of=AS_OF)

    assert summary["total"] == 1908
    assert summary["expiry_bands"]["overdue"] == 427, "must match the register, not 871"
    assert summary["expiry_bands"]["removed"] == 463


def test_quarantined_assets_are_still_banded_by_expiry():
    """Quarantine is a state of in-service kit; the register still bands it."""
    rows = [AssetHealthRow("Harness", "quarantined", LONG_EXPIRED)]

    bands = _bands(rows)

    assert bands["overdue"] == 1
    assert bands["removed"] == 0


def test_expiry_today_is_due_not_overdue():
    """Day granularity: the register treats today's expiry as due, not already lapsed."""
    rows = [AssetHealthRow("Harness", "active", AS_OF.replace(hour=0, minute=0))]

    bands = _bands(rows)

    assert bands["overdue"] == 0
    assert bands["due_30"] == 1


def test_bands_partition_every_row():
    rows = [
        AssetHealthRow("Harness", "active", LONG_EXPIRED),
        AssetHealthRow("Harness", "decommissioned", LONG_EXPIRED),
        AssetHealthRow("Harness", "active", None),
        AssetHealthRow("Harness", "maintenance", AS_OF + timedelta(days=45)),
    ]

    summary = aggregate_asset_health_kpis(rows, as_of=AS_OF)

    assert sum(summary["expiry_bands"].values()) == summary["total"] == 4


def test_removed_status_helper_matches_the_registers_definition():
    assert REMOVED_ASSET_STATUSES == frozenset({"decommissioned"})
    assert is_removed_asset_status("DECOMMISSIONED") is True
    assert is_removed_asset_status("quarantined") is False
    assert is_removed_asset_status(None) is False
