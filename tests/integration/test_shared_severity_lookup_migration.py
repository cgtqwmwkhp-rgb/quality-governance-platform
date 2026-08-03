"""Behavioural tests for the ``severity_levels`` half of ``20260911_shared_severity``.

The migration's schema half (widening ``ck_complaints_priority`` and
``ck_nm_severity_values``) is PostgreSQL DDL and is exercised by running the chain;
its data half is what needs behavioural cover, because the defect it repairs is
invisible from the seed module.

``lookup_defaults_seed_data`` lists five ``severity_levels`` codes, so a tenant
created through the runtime seeder is offered ``negligible``. A tenant built by
``alembic upgrade head`` is not: ``20260827_lookup_tenant_fix`` adopts the orphaned
``low / medium / high / critical`` rows into the tenant, which leaves the category
non-empty, and ``20260828_lookup_defaults`` only inserts into a category with no
rows at all — so its five-row block never runs. Measured on a fresh
``alembic upgrade head`` at ``20260908_soa_align``: four rows, no ``negligible``.

That is the state these tests start from. Everything runs against a **scratch
database** created per test, because the migration's subject is the contents of a
table the shared integration schema also uses and a downgrade here would delete
rows other tests depend on.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from src.domain.services.lookup_enum_contract import lookup_for_category

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20260911_shared_severity_negligible.py"

TENANT = 1
CATEGORY = "severity_levels"

# What ``alembic upgrade head`` actually leaves behind before this migration runs.
MIGRATED_TAXONOMY = (
    ("severity_levels", "low", "Low"),
    ("severity_levels", "medium", "Medium"),
    ("severity_levels", "high", "High"),
    ("severity_levels", "critical", "Critical"),
)


def _load_migration() -> ModuleType:
    """Load by file path; ``alembic/versions`` is not an importable package.

    The repo ships an empty ``alembic/__init__.py`` that shadows the installed
    distribution once the repo root is on ``sys.path``, so ``alembic.op`` is stubbed
    for the load. These tests drive the migration's helpers directly and never go
    through ``op.get_bind()``.
    """
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("qgp_shared_severity_repair", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migration = _load_migration()
TABLES = migration._tables()
LOOKUPS = TABLES["lookup_options"]


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

    async def options(self, category: str = CATEGORY):
        return await self.fetch(
            sa.select(LOOKUPS.c.id, LOOKUPS.c.tenant_id, LOOKUPS.c.code, LOOKUPS.c.label, LOOKUPS.c.is_active)
            .where(LOOKUPS.c.category == category)
            .order_by(LOOKUPS.c.id)
        )

    async def active_codes(self, tenant_id: int = TENANT) -> list[str]:
        """What a tenant-filtered, active-only read would offer — i.e. the dropdown."""
        rows = await self.fetch(
            sa.select(LOOKUPS.c.code).where(
                LOOKUPS.c.category == CATEGORY,
                LOOKUPS.c.tenant_id == tenant_id,
                LOOKUPS.c.is_active.is_(True),
            )
        )
        return sorted(row.code for row in rows)

    async def add_tenant(self, tenant_id: int) -> None:
        await self.run(_insert_tenant(tenant_id))

    async def add_options(self, *rows, tenant_id: int | None = TENANT, is_active: bool = True) -> None:
        await self.run(_insert_lookup_options(tenant_id, rows, is_active))

    async def apply(self):
        return await self.run(migration.apply_shared_severity_lookup)

    async def revert(self):
        return await self.run(migration.revert_shared_severity_lookup)

    async def ledger_exists(self) -> bool:
        settings = TABLES["system_settings"]
        rows = await self.fetch(sa.select(settings.c.value).where(settings.c.key == migration.REPAIR_LEDGER_KEY))
        return bool(rows)


@pytest.fixture
async def scratch(tmp_path) -> ScratchDb:
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


def _shared_codes() -> list[str]:
    contract = lookup_for_category(CATEGORY)
    assert contract is not None, "severity_levels must be registered in ENUM_BACKED_LOOKUPS"
    return sorted(contract.allowed_codes)


class TestTheMissingOptionIsRestored:
    async def test_a_migrated_tenant_gains_negligible(self, scratch: ScratchDb):
        await scratch.add_options(*MIGRATED_TAXONOMY)
        assert "negligible" not in await scratch.active_codes(), "precondition: the defect being repaired"

        report = await scratch.apply()

        assert await scratch.active_codes() == _shared_codes()
        assert len(report["inserted"]) == 1

    async def test_an_empty_category_is_populated(self, scratch: ScratchDb):
        report = await scratch.apply()

        assert await scratch.active_codes() == _shared_codes()
        assert len(report["inserted"]) == len(_shared_codes())

    async def test_every_tenant_gets_the_same_dropdown(self, scratch: ScratchDb):
        await scratch.add_tenant(2)
        await scratch.add_options(*MIGRATED_TAXONOMY)

        await scratch.apply()

        for tenant_id in (1, 2):
            assert await scratch.active_codes(tenant_id) == _shared_codes()

    async def test_a_shared_code_that_was_switched_off_comes_back(self, scratch: ScratchDb):
        await scratch.add_options(("severity_levels", "critical", "Critical"), is_active=False)

        report = await scratch.apply()

        assert "critical" in await scratch.active_codes()
        assert len(report["reactivated"]) == 1

    async def test_an_admin_curated_label_is_kept(self, scratch: ScratchDb):
        await scratch.add_options(("severity_levels", "critical", "Catastrophic (our wording)"))

        await scratch.apply()

        labels = {row.code: row.label for row in await scratch.options()}
        assert labels["critical"] == "Catastrophic (our wording)", "labels are the admin's, not ours"

    async def test_rows_invisible_to_every_caller_are_left_alone(self, scratch: ScratchDb):
        """``tenant_id IS NULL`` rows are unreadable through the tenant-filtered API."""
        await scratch.add_options(("severity_levels", "showstopper", "Orphan"), tenant_id=None)

        await scratch.apply()

        orphan = next(row for row in await scratch.options() if row.tenant_id is None)
        assert orphan.is_active, "flipping a row nobody can read is churn, not a repair"


class TestCodesOutsideTheSharedSetStopBeingOffered:
    async def test_a_code_the_api_would_reject_is_deactivated(self, scratch: ScratchDb):
        await scratch.add_options(("severity_levels", "showstopper", "Showstopper"))

        report = await scratch.apply()

        assert "showstopper" not in await scratch.active_codes()
        assert len(report["deactivated"]) == 1

    async def test_it_is_deactivated_not_deleted(self, scratch: ScratchDb):
        await scratch.add_options(("severity_levels", "showstopper", "Showstopper"))

        await scratch.apply()

        rows = {row.code: row for row in await scratch.options()}
        assert "showstopper" in rows, "the row may be a parent, or appear in stored submissions"
        assert not rows["showstopper"].is_active


class TestIdempotency:
    async def test_repeat_runs_change_nothing(self, scratch: ScratchDb):
        await scratch.add_options(*MIGRATED_TAXONOMY, ("severity_levels", "showstopper", "Showstopper"))
        await scratch.apply()
        baseline = await scratch.options()

        for _ in range(2):
            repeat = await scratch.apply()
            assert all(not ids for ids in repeat.values())

        assert await scratch.options() == baseline


class TestDowngrade:
    async def test_downgrade_restores_the_previous_state_exactly(self, scratch: ScratchDb):
        await scratch.add_options(*MIGRATED_TAXONOMY, ("severity_levels", "showstopper", "Showstopper"))
        before = await scratch.options()
        await scratch.apply()

        await scratch.revert()

        assert await scratch.options() == before

    async def test_downgrade_deletes_only_the_rows_it_inserted(self, scratch: ScratchDb):
        await scratch.add_options(*MIGRATED_TAXONOMY)
        report = await scratch.apply()

        reverted = await scratch.revert()

        assert reverted["inserted"] == len(report["inserted"])
        assert sorted(row.code for row in await scratch.options()) == sorted(
            code for _category, code, _label in MIGRATED_TAXONOMY
        )

    async def test_downgrade_leaves_rows_it_never_touched_alone(self, scratch: ScratchDb):
        await scratch.add_options(("severity_levels", "low", "Low"))
        await scratch.apply()
        await scratch.revert()

        rows = await scratch.options()
        assert [(row.code, bool(row.is_active)) for row in rows] == [("low", True)]

    async def test_downgrade_clears_the_ledger(self, scratch: ScratchDb):
        await scratch.add_options(*MIGRATED_TAXONOMY)
        await scratch.apply()
        assert await scratch.ledger_exists(), "the upgrade should have recorded what it changed"

        await scratch.revert()

        assert not await scratch.ledger_exists()

    async def test_downgrade_is_safe_when_nothing_was_applied(self, scratch: ScratchDb):
        assert await scratch.revert() == {"inserted": 0, "deactivated": 0, "reactivated": 0}


class TestRevisionChain:
    def test_migration_follows_the_expected_head(self):
        source = MIGRATION_PATH.read_text(encoding="utf-8")
        assert 'revision: str = "20260911_shared_severity"' in source
        assert 'down_revision: Union[str, Sequence[str], None] = "20260908_soa_align"' in source
        assert len("20260911_shared_severity") <= 32
