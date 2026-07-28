"""Behavioural tests for Alembic revision ``20260831_lookup_enum_align``.

The migration only moves data, so what is worth testing is the outcome: that a
tenant carrying production's broken taxonomy ends up offering exactly the enum's
codes (PX-281/282, R22-01), that duplicate customers stop being offered twice
without any ``contracts`` row being disturbed (R22-02), that re-running changes
nothing, and that the downgrade puts every row back as it was.

Everything runs against a **scratch database** created per test. Integration
tests share a persistent schema where a downgrade would delete rows other tests
depend on, and this migration's whole subject is the contents of a table the
shared schema also uses.

The migration module is loaded by file path because ``alembic/versions`` is not
an importable package. The repo also ships an empty ``alembic/__init__.py`` that
shadows the installed distribution once the repo root is on ``sys.path``, so
``alembic.op`` is stubbed for the load: these tests drive the migration's helpers
directly and never go through ``op.get_bind()``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from src.domain.services.lookup_enum_contract import ENUM_BACKED_LOOKUPS, lookup_for_category

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20260831_realign_enum_lookups_and_dedupe_customers.py"

TENANT = 1


def _load_migration() -> ModuleType:
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("qgp_lookup_taxonomy_repair", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migration = _load_migration()
TABLES = migration._tables()
LOOKUPS = TABLES["lookup_options"]


# The taxonomy production is actually carrying: one active complaint type and
# one active incident type, neither of which the API will accept for complaints.
PRODUCTION_TAXONOMY = (
    ("complaint_types", "workmanship", "Workmanship / repair defect"),
    ("incident_types", "injury", "Injury / accident"),
)

# The customers duplicates reported in R22-02.
DUPLICATE_CUSTOMERS = (
    ("customers", "thames_water", "Thames Water"),
    ("customers", "thames-water", "Thames Water"),
    ("customers", "plantexpand", "Plantexpand Ltd"),
    ("customers", "plantexpand_ltd", "Plantexpand Ltd"),
)


class ScratchDb:
    """A private database with the app schema and a single tenant."""

    def __init__(self, engine):
        self._engine = engine

    async def run(self, fn):
        async with self._engine.begin() as conn:
            return await conn.run_sync(fn)

    async def fetch(self, statement):
        async with self._engine.connect() as conn:
            return (await conn.execute(statement)).all()

    async def scalar(self, statement):
        async with self._engine.connect() as conn:
            return (await conn.execute(statement)).scalar_one()

    async def options(self, category: str):
        return await self.fetch(
            sa.select(LOOKUPS.c.id, LOOKUPS.c.tenant_id, LOOKUPS.c.code, LOOKUPS.c.label, LOOKUPS.c.is_active)
            .where(LOOKUPS.c.category == category)
            .order_by(LOOKUPS.c.id)
        )

    async def active_codes(self, category: str, tenant_id: int = TENANT) -> list[str]:
        """What a tenant-filtered, active-only read would offer — i.e. the dropdown."""
        rows = await self.fetch(
            sa.select(LOOKUPS.c.code).where(
                LOOKUPS.c.category == category,
                LOOKUPS.c.tenant_id == tenant_id,
                LOOKUPS.c.is_active.is_(True),
            )
        )
        return sorted(row.code for row in rows)

    async def add_tenant(self, tenant_id: int) -> None:
        await self.run(_insert_tenant(tenant_id))

    async def add_options(self, *rows, tenant_id: int | None = TENANT, is_active: bool = True) -> None:
        await self.run(_insert_lookup_options(tenant_id, rows, is_active))

    async def add_contract(self, code: str, name: str, tenant_id: int = TENANT) -> None:
        await self.run(_insert_contract(tenant_id, code, name))

    async def apply(self):
        return await self.run(migration.apply_lookup_taxonomy_repair)

    async def revert(self):
        return await self.run(migration.revert_lookup_taxonomy_repair)

    async def ledger(self) -> dict:
        settings = TABLES["system_settings"]
        raw = await self.fetch(sa.select(settings.c.value).where(settings.c.key == migration.REPAIR_LEDGER_KEY))
        return json.loads(raw[0].value) if raw else {}


@pytest.fixture
async def scratch(tmp_path) -> ScratchDb:
    """A throwaway database, so a downgrade never touches the shared schema."""
    import src.domain.models  # noqa: F401  — registers every table on Base.metadata
    from src.infrastructure.database import Base

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'scratch.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    db = ScratchDb(engine)
    await db.add_tenant(TENANT)
    try:
        yield db
    finally:
        await engine.dispose()


def _insert_tenant(tenant_id: int):
    def _apply(conn):
        from src.domain.models.tenant import Tenant

        conn.execute(
            Tenant.__table__.insert().values(
                id=tenant_id,
                name=f"Tenant {tenant_id}",
                slug=f"tenant-{tenant_id}",
                admin_email=f"admin@tenant-{tenant_id}.example.com",
            )
        )

    return _apply


def _insert_contract(tenant_id: int, code: str, name: str):
    def _apply(conn):
        from src.domain.models.form_config import Contract

        # The ORM table, not the migration's read-only view, so the model's
        # column defaults are applied.
        conn.execute(Contract.__table__.insert().values(tenant_id=tenant_id, code=code, name=name, is_active=True))

    return _apply


def _insert_lookup_options(tenant_id: int | None, rows, is_active: bool):
    def _apply(conn):
        for category, code, label in rows:
            conn.execute(
                LOOKUPS.insert().values(
                    tenant_id=tenant_id,
                    category=category,
                    code=code,
                    label=label,
                    is_active=is_active,
                    display_order=1,
                    created_at=sa.func.now(),
                    updated_at=sa.func.now(),
                )
            )

    return _apply


CATEGORY_IDS = [lookup.category for lookup in ENUM_BACKED_LOOKUPS]


class TestEnumRealignment:
    """PX-281/282, R22-01 — the dropdown ends up equal to the enum."""

    @pytest.mark.parametrize("category", CATEGORY_IDS)
    async def test_dropdown_becomes_exactly_the_enum(self, scratch: ScratchDb, category: str):
        await scratch.add_options(*PRODUCTION_TAXONOMY)

        await scratch.apply()

        contract = lookup_for_category(category)
        assert contract is not None
        assert await scratch.active_codes(category) == sorted(contract.allowed_codes)

    async def test_the_single_unusable_complaint_option_stops_being_offered(self, scratch: ScratchDb):
        await scratch.add_options(("complaint_types", "workmanship", "Workmanship / repair defect"))

        report = await scratch.apply()

        assert "workmanship" not in await scratch.active_codes("complaint_types")
        assert len(report["per_category"]["complaint_types"]["deactivated"]) == 1

    async def test_non_enum_codes_are_deactivated_not_deleted(self, scratch: ScratchDb):
        await scratch.add_options(
            ("complaint_types", "workmanship", "Workmanship / repair defect"),
            ("complaint_types", "hse_concern", "Health, safety or environmental concern"),
        )

        await scratch.apply()

        legacy = {row.code: row for row in await scratch.options("complaint_types") if row.code == "workmanship"}
        assert legacy, "the row must survive: its label may be curated and its code may appear in stored submissions"
        assert not legacy["workmanship"].is_active
        assert legacy["workmanship"].label == "Workmanship / repair defect", "labels are the admin's, not ours"

    async def test_an_enum_code_that_was_switched_off_comes_back(self, scratch: ScratchDb):
        await scratch.add_options(("complaint_types", "service", "Service"), is_active=False)

        report = await scratch.apply()

        assert "service" in await scratch.active_codes("complaint_types")
        assert len(report["per_category"]["complaint_types"]["reactivated"]) == 1
        assert len(report["per_category"]["complaint_types"]["inserted"]) == 8, "service already existed"

    async def test_an_admin_curated_label_on_an_enum_code_is_kept(self, scratch: ScratchDb):
        await scratch.add_options(("complaint_types", "service", "Service or repair standard (our wording)"))

        await scratch.apply()

        rows = {row.code: row.label for row in await scratch.options("complaint_types")}
        assert rows["service"] == "Service or repair standard (our wording)"

    async def test_every_tenant_gets_a_usable_dropdown(self, scratch: ScratchDb):
        await scratch.add_tenant(2)
        await scratch.add_options(*PRODUCTION_TAXONOMY)

        await scratch.apply()

        contract = lookup_for_category("complaint_types")
        assert contract is not None
        for tenant_id in (1, 2):
            assert await scratch.active_codes("complaint_types", tenant_id) == sorted(contract.allowed_codes)

    async def test_rows_invisible_to_every_caller_are_left_alone(self, scratch: ScratchDb):
        """``tenant_id IS NULL`` rows are unreadable through the tenant-filtered API."""
        await scratch.add_options(("complaint_types", "workmanship", "Orphan"), tenant_id=None)

        await scratch.apply()

        orphan = next(row for row in await scratch.options("complaint_types") if row.tenant_id is None)
        assert orphan.is_active, "flipping a row nobody can read is churn, not a repair"

    async def test_an_empty_category_is_populated(self, scratch: ScratchDb):
        report = await scratch.apply()

        contract = lookup_for_category("incident_types")
        assert contract is not None
        assert await scratch.active_codes("incident_types") == sorted(contract.allowed_codes)
        assert len(report["per_category"]["incident_types"]["inserted"]) == len(contract.allowed_codes)


class TestCustomerDeduplication:
    """R22-02 — two active rows sharing a code also break contract resolution."""

    async def test_each_customer_is_offered_once(self, scratch: ScratchDb):
        await scratch.add_options(*DUPLICATE_CUSTOMERS)

        await scratch.apply()

        rows = [row for row in await scratch.options("customers") if row.is_active]
        assert sorted(row.label for row in rows) == ["Plantexpand Ltd", "Thames Water"]

    async def test_the_same_code_twice_is_reduced_to_one(self, scratch: ScratchDb):
        await scratch.add_options(
            ("customers", "thames_water", "Thames Water"),
            ("customers", "thames_water", "Thames Water (dup import)"),
        )

        report = await scratch.apply()

        assert len(report["duplicate_customers"]) == 1
        active = [row for row in await scratch.options("customers") if row.is_active]
        assert [row.label for row in active] == ["Thames Water"], "the oldest row wins when nothing else separates them"

    async def test_the_row_with_a_contract_survives(self, scratch: ScratchDb):
        """Keeping the resolvable row is what stops the customers → contracts bridge breaking."""
        await scratch.add_options(
            ("customers", "thames-water", "Thames Water"),
            ("customers", "thames_water", "Thames Water"),
        )
        await scratch.add_contract("thames_water", "Thames Water")

        await scratch.apply()

        active = [row for row in await scratch.options("customers") if row.is_active]
        assert [row.code for row in active] == ["thames_water"]

    async def test_duplicates_are_deactivated_not_deleted(self, scratch: ScratchDb):
        await scratch.add_options(*DUPLICATE_CUSTOMERS)

        await scratch.apply()

        assert len(await scratch.options("customers")) == len(DUPLICATE_CUSTOMERS)

    async def test_no_contract_row_is_touched(self, scratch: ScratchDb):
        """Cases carry ``contract_id``, so deleting or altering contracts would orphan them."""
        await scratch.add_options(*DUPLICATE_CUSTOMERS)
        await scratch.add_contract("thames_water", "Thames Water")
        await scratch.add_contract("thames-water", "Thames Water")

        await scratch.apply()

        contracts = await scratch.fetch(sa.select(TABLES["contracts"].c.code, TABLES["contracts"].c.name))
        assert sorted(row.code for row in contracts) == ["thames-water", "thames_water"]

    async def test_distinct_customers_are_left_alone(self, scratch: ScratchDb):
        await scratch.add_options(
            ("customers", "ukpn", "UK Power Networks"),
            ("customers", "cadent", "Cadent Gas"),
            ("customers", "openreach", "Openreach"),
        )

        report = await scratch.apply()

        assert report["duplicate_customers"] == []
        assert len(await scratch.active_codes("customers")) == 3

    async def test_the_same_name_under_two_tenants_is_not_a_duplicate(self, scratch: ScratchDb):
        await scratch.add_tenant(2)
        await scratch.add_options(("customers", "thames_water", "Thames Water"), tenant_id=1)
        await scratch.add_options(("customers", "thames_water", "Thames Water"), tenant_id=2)

        report = await scratch.apply()

        assert report["duplicate_customers"] == []


class TestIdempotency:
    async def test_repeat_runs_change_nothing(self, scratch: ScratchDb):
        await scratch.add_options(*PRODUCTION_TAXONOMY, *DUPLICATE_CUSTOMERS)

        first = await scratch.apply()
        assert first["duplicate_customers"], "first run should have found the duplicates"
        baseline = {
            category: await scratch.options(category) for category in ("complaint_types", "incident_types", "customers")
        }

        for _ in range(2):
            repeat = await scratch.apply()
            assert repeat["duplicate_customers"] == []
            assert all(not changed[key] for changed in repeat["per_category"].values() for key in changed)

        for category, rows in baseline.items():
            assert await scratch.options(category) == rows


class TestDowngrade:
    async def test_downgrade_restores_the_previous_state_exactly(self, scratch: ScratchDb):
        await scratch.add_options(*PRODUCTION_TAXONOMY, *DUPLICATE_CUSTOMERS)
        before = {
            category: await scratch.options(category) for category in ("complaint_types", "incident_types", "customers")
        }
        await scratch.apply()

        await scratch.revert()

        for category, rows in before.items():
            assert await scratch.options(category) == rows, f"'{category}' was not restored"

    async def test_downgrade_deletes_only_the_rows_it_inserted(self, scratch: ScratchDb):
        await scratch.add_options(("complaint_types", "workmanship", "Workmanship / repair defect"))
        report = await scratch.apply()
        inserted = [row_id for changed in report["per_category"].values() for row_id in changed["inserted"]]

        reverted = await scratch.revert()

        assert reverted["inserted"] == len(inserted)
        assert [row.code for row in await scratch.options("complaint_types")] == ["workmanship"]

    async def test_downgrade_re_offers_the_deduplicated_customers(self, scratch: ScratchDb):
        await scratch.add_options(*DUPLICATE_CUSTOMERS)
        await scratch.apply()

        reverted = await scratch.revert()

        assert reverted["deactivated"] == 2
        assert len(await scratch.active_codes("customers")) == len(DUPLICATE_CUSTOMERS)

    async def test_downgrade_leaves_rows_it_never_touched_alone(self, scratch: ScratchDb):
        await scratch.add_options(("customers", "ukpn", "UK Power Networks"))
        await scratch.apply()

        await scratch.revert()

        rows = await scratch.options("customers")
        assert [(row.code, bool(row.is_active)) for row in rows] == [("ukpn", True)]

    async def test_downgrade_clears_the_ledger(self, scratch: ScratchDb):
        await scratch.add_options(*PRODUCTION_TAXONOMY)
        await scratch.apply()
        assert await scratch.ledger(), "the upgrade should have recorded what it changed"

        await scratch.revert()

        assert await scratch.ledger() == {}

    async def test_downgrade_is_safe_when_nothing_was_applied(self, scratch: ScratchDb):
        assert await scratch.revert() == {"inserted": 0, "deactivated": 0, "reactivated": 0}

    async def test_downgrade_releases_a_child_before_deleting_its_parent(self, scratch: ScratchDb):
        """``parent_id`` is a self-referential FK; a seeded row may have become a parent."""
        report = await scratch.apply()
        parent_id = report["per_category"]["complaint_types"]["inserted"][0]
        await scratch.run(
            lambda conn: conn.execute(
                LOOKUPS.insert().values(
                    tenant_id=TENANT,
                    category="complaint_subtypes",
                    code="child",
                    label="Child of a seeded option",
                    is_active=True,
                    display_order=1,
                    parent_id=parent_id,
                    created_at=sa.func.now(),
                    updated_at=sa.func.now(),
                )
            )
        )

        await scratch.revert()

        child = (await scratch.options("complaint_subtypes"))[0]
        assert child.code == "child", "the child must survive its parent being rolled back"
        assert (
            await scratch.scalar(sa.select(sa.func.count()).select_from(LOOKUPS).where(LOOKUPS.c.id == parent_id)) == 0
        )


class TestRevisionChain:
    def test_migration_follows_the_current_head(self):
        source = MIGRATION_PATH.read_text(encoding="utf-8")
        assert 'revision: str = "20260831_lookup_enum_align"' in source
        assert 'down_revision: Union[str, Sequence[str], None] = "20260830_sla_cam_ref"' in source
        assert len("20260831_lookup_enum_align") <= 32
