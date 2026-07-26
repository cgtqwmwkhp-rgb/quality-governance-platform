"""PX-211: the overdue-assets drill-down must return exactly the rows the KPI counts.

The dashboard tile and the register are only reconciled if the aggregate and the list
query share one definition of "overdue". They did not: `aggregate_asset_health_kpis`
banded on expiry date alone while the register excluded removed assets, and the list
query compared against `now` rather than the start of the day.

These tests run the real query against SQLite and compare its result to the aggregate
over the same rows, so the two cannot drift apart silently.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.models.asset import Asset, AssetCategory, AssetStatus, AssetType
from src.domain.services.asset_health_analytics_service import AssetHealthRow, aggregate_asset_health_kpis
from src.domain.services.asset_service import AssetService

TENANT_ID = 1
NOW = datetime.now(timezone.utc)
TODAY_START = NOW.replace(hour=0, minute=0, second=0, microsecond=0)


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AssetType.__table__.create)
        await conn.run_sync(Asset.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


ASSET_TYPE_ID = 1


def _asset(number: str, status: AssetStatus, expiry: datetime | None) -> Asset:
    return Asset(
        tenant_id=TENANT_ID,
        asset_type_id=ASSET_TYPE_ID,
        asset_number=number,
        name=f"Asset {number}",
        status=status,
        expiry_date=expiry,
    )


#: Deliberately spans every boundary the two code paths disagreed on.
FIXTURE: list[tuple[str, AssetStatus, datetime | None]] = [
    ("A-EXPIRED-INSERVICE", AssetStatus.ACTIVE, TODAY_START - timedelta(days=30)),
    ("A-EXPIRED-YESTERDAY", AssetStatus.ACTIVE, TODAY_START - timedelta(seconds=1)),
    ("A-EXPIRED-QUARANTINED", AssetStatus.QUARANTINED, TODAY_START - timedelta(days=5)),
    ("A-EXPIRED-REMOVED", AssetStatus.DECOMMISSIONED, TODAY_START - timedelta(days=90)),
    ("A-EXPIRES-TODAY-MIDNIGHT", AssetStatus.ACTIVE, TODAY_START),
    ("A-EXPIRES-TODAY-LATER", AssetStatus.ACTIVE, TODAY_START + timedelta(hours=23)),
    ("A-DUE-SOON", AssetStatus.ACTIVE, NOW + timedelta(days=10)),
    ("A-IN-DATE", AssetStatus.ACTIVE, NOW + timedelta(days=400)),
    ("A-NO-EXPIRY", AssetStatus.ACTIVE, None),
]


async def _seed(session_factory) -> None:
    async with session_factory() as session:
        session.add(
            AssetType(
                id=ASSET_TYPE_ID,
                tenant_id=TENANT_ID,
                category=AssetCategory.LIFTING,
                name="Harness",
            )
        )
        await session.flush()
        for number, status, expiry in FIXTURE:
            session.add(_asset(number, status, expiry))
        await session.commit()


def _expected_overdue_count() -> int:
    rows = [AssetHealthRow(asset_type=None, status=s.value, expiry_date=e) for _n, s, e in FIXTURE]
    return int(aggregate_asset_health_kpis(rows, as_of=NOW)["expiry_bands"]["overdue"])


@pytest.mark.asyncio
async def test_overdue_drilldown_returns_exactly_the_rows_the_kpi_counts(session_factory):
    await _seed(session_factory)

    async with session_factory() as session:
        result = await AssetService(session).list_assets(TENANT_ID, page_size=100, expiry_band="overdue")

    numbers = {a.asset_number for a in result.items}
    assert numbers == {
        "A-EXPIRED-INSERVICE",
        "A-EXPIRED-YESTERDAY",
        "A-EXPIRED-QUARANTINED",
    }
    assert result.total == _expected_overdue_count() == 3


@pytest.mark.asyncio
async def test_removed_assets_never_appear_in_an_expiry_drilldown(session_factory):
    await _seed(session_factory)

    async with session_factory() as session:
        service = AssetService(session)
        for band in ("overdue", "due_30", "due_60", "due_90"):
            result = await service.list_assets(TENANT_ID, page_size=100, expiry_band=band)
            assert "A-EXPIRED-REMOVED" not in {a.asset_number for a in result.items}, band


@pytest.mark.asyncio
async def test_an_asset_expiring_today_is_due_not_overdue(session_factory):
    """The gap case: bounded at `now`, these rows fell out of overdue and due_30 both."""
    await _seed(session_factory)

    async with session_factory() as session:
        service = AssetService(session)
        overdue = await service.list_assets(TENANT_ID, page_size=100, expiry_band="overdue")
        due_30 = await service.list_assets(TENANT_ID, page_size=100, expiry_band="due_30")

    overdue_numbers = {a.asset_number for a in overdue.items}
    due_30_numbers = {a.asset_number for a in due_30.items}

    for number in ("A-EXPIRES-TODAY-MIDNIGHT", "A-EXPIRES-TODAY-LATER"):
        assert number not in overdue_numbers
        assert number in due_30_numbers


@pytest.mark.asyncio
async def test_overdue_and_due_bands_do_not_overlap(session_factory):
    await _seed(session_factory)

    async with session_factory() as session:
        service = AssetService(session)
        overdue = await service.list_assets(TENANT_ID, page_size=100, expiry_band="overdue")
        due_90 = await service.list_assets(TENANT_ID, page_size=100, expiry_band="due_90")

    assert not {a.asset_number for a in overdue.items} & {a.asset_number for a in due_90.items}
