"""Unit tests for read-only asset health KPI aggregation."""

from datetime import datetime, timedelta, timezone

from src.domain.services.asset_health_analytics_service import AssetHealthRow, aggregate_asset_health_kpis


def test_aggregate_asset_health_kpis_groups_expiry_type_and_status():
    as_of = datetime(2026, 7, 14, tzinfo=timezone.utc)
    rows = [
        AssetHealthRow("Fire Extinguisher", "active", as_of - timedelta(seconds=1)),
        AssetHealthRow("Fire Extinguisher", "active", as_of + timedelta(days=29)),
        AssetHealthRow("First Aid Kit", "quarantined", as_of + timedelta(days=30)),
        AssetHealthRow("First Aid Kit", "maintenance", as_of + timedelta(days=60)),
        AssetHealthRow(None, "active", as_of + timedelta(days=90)),
        AssetHealthRow("First Aid Kit", "active", None),
    ]

    summary = aggregate_asset_health_kpis(rows, as_of=as_of)

    assert summary["total"] == 6
    assert summary["expiry_bands"] == {
        "overdue": 1,
        "due_30": 1,
        "due_60": 1,
        "due_90": 1,
        "in_date": 1,
        "no_expiry": 1,
    }
    assert summary["by_type"] == {
        "Fire Extinguisher": 2,
        "First Aid Kit": 3,
        "Unclassified": 1,
    }
    assert summary["by_status"] == {
        "active": 4,
        "maintenance": 1,
        "quarantined": 1,
    }
    assert summary["generated_at"] == as_of
