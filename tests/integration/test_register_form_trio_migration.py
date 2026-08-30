"""Behavioural tests for Alembic revision ``20261116_reg_ssot_d1_forms`` (REG-SSOT-D1).

The revision only seeds data, so what is worth testing is the outcome: that the
three register templates exist on the shared form-config spine, that they are
seeded as *drafts* rather than advertised as published portal journeys, that a
repeat run inserts nothing, and that the downgrade removes exactly what the
migration added and nothing an administrator has since edited.

Harness choices follow ``test_portal_intake_repair_migration.py``:

* Migration mechanics run against a **scratch database** created per test.
  Integration tests share a persistent schema on Postgres where this migration
  has already run; a downgrade there would delete rows other tests rely on.
* Visibility through the API runs against the app database, driving the seed
  helper with an explicit tenant.

The migration module is loaded by file path because ``alembic/versions`` is not
an importable package, and ``alembic.op`` is stubbed for the load because the
repo ships an empty ``alembic/__init__.py`` that shadows the installed
distribution. These tests drive the helpers directly and never call
``op.get_bind()``.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20261116_seed_register_form_trio.py"

TENANT = 1

# The Register of Registers rows this revision exists to serve. Mirrors
# frontend/src/data/registerCatalogue.ts — if a slug changes on one side without
# the other, the hub's Open lands on a Form Builder with nothing to show.
DOC_REF_TO_SLUG = {
    "PEL-HSEQ-5026": "worker-consultation-record",
    "PEL-HSEQ-5036": "permit-to-work-record",
    "PEL-HSEQ-5043": "remote-working-record",
}


def _load_migration() -> ModuleType:
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("qgp_reg_ssot_d1_forms", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migration = _load_migration()
TABLES = migration._tables()

EXPECTED_STEPS = sum(len(d["steps"]) for d in migration.REGISTER_FORM_TEMPLATES)
EXPECTED_FIELDS = sum(len(step["fields"]) for d in migration.REGISTER_FORM_TEMPLATES for step in d["steps"])


def test_revision_chains_serially_from_aud_dev_2():
    """Single-head ratchet: this revision is what W4/W5 head pins must name next."""
    assert migration.revision == "20261116_reg_ssot_d1_forms"
    assert migration.down_revision == "20261115_aud_notify"


class ScratchDb:
    """A private database with the app schema and a single tenant."""

    def __init__(self, engine):
        self._engine = engine

    async def run(self, fn):
        async with self._engine.begin() as conn:
            return await conn.run_sync(fn)

    async def fetch(self, statement: sa.sql.expression.Executable):
        async with self._engine.connect() as conn:
            return (await conn.execute(statement)).all()

    async def scalar(self, statement: sa.sql.expression.Executable):
        async with self._engine.connect() as conn:
            return (await conn.execute(statement)).scalar_one()

    async def add_tenant(self, tenant_id: int) -> None:
        await self.run(_insert_tenant(tenant_id))

    async def apply(self):
        return await self.run(migration.seed_register_form_templates)

    async def revert(self):
        return await self.run(migration.revert_register_form_templates)


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


def _bump_template_version(slug: str):
    """Stand in for an administrator editing the template through the API."""

    def _apply(conn):
        table = TABLES["form_templates"]
        result = conn.execute(table.update().where(table.c.slug == slug).values(version=2))
        assert result.rowcount == 1, f"no template with slug '{slug}' to edit"

    return _apply


class TestSeed:
    async def test_the_three_register_templates_are_created(self, scratch: ScratchDb):
        inserted = await scratch.apply()

        assert len(inserted) == 3
        table = TABLES["form_templates"]
        rows = await scratch.fetch(sa.select(table.c.slug, table.c.tenant_id, table.c.form_type))
        assert sorted(r.slug for r in rows) == sorted(DOC_REF_TO_SLUG.values())
        assert all(r.tenant_id == TENANT for r in rows)
        assert {r.form_type for r in rows} == {
            "custom"
        }, "these are not incident/complaint/rta/near_miss intake forms and must not claim to be"

    async def test_templates_are_seeded_as_unpublished_drafts(self, scratch: ScratchDb):
        """Publishing means 'available in the portal'; no portal route serves these slugs."""
        await scratch.apply()

        table = TABLES["form_templates"]
        rows = await scratch.fetch(
            sa.select(table.c.slug, table.c.is_active, table.c.is_published, table.c.published_at)
        )
        assert all(bool(r.is_active) for r in rows)
        assert not any(bool(r.is_published) for r in rows)
        assert all(r.published_at is None for r in rows)

    @pytest.mark.parametrize("doc_ref,slug", sorted(DOC_REF_TO_SLUG.items()))
    async def test_each_template_names_its_pel_reference(self, scratch: ScratchDb, doc_ref: str, slug: str):
        """The hub Open lands on a list; the PEL ref has to be visible on the card."""
        await scratch.apply()

        table = TABLES["form_templates"]
        name = await scratch.scalar(sa.select(table.c.name).where(table.c.slug == slug))
        assert name.startswith(doc_ref)

    async def test_no_field_depends_on_an_admin_lookup_catalogue(self, scratch: ScratchDb):
        """A required lookup-backed field with no options blocks publishing forever."""
        from src.domain.services.form_publish_validation import resolve_lookup_category

        await scratch.apply()

        fields = await scratch.fetch(sa.select(TABLES["form_fields"].c.name, TABLES["form_fields"].c.field_type))
        assert fields
        offenders = [
            f.name
            for f in fields
            if resolve_lookup_category(SimpleNamespace(name=f.name, field_type=f.field_type, options=None))
        ]
        assert offenders == []

    async def test_steps_and_fields_are_written_in_order(self, scratch: ScratchDb):
        await scratch.apply()

        templates, steps, fields = TABLES["form_templates"], TABLES["form_steps"], TABLES["form_fields"]
        permit_id = await scratch.scalar(sa.select(templates.c.id).where(templates.c.slug == "permit-to-work-record"))
        step_rows = await scratch.fetch(
            sa.select(steps.c.id, steps.c.name).where(steps.c.template_id == permit_id).order_by(steps.c.order)
        )
        assert [s.name for s in step_rows] == ["Permit Details", "Work and Precautions", "Handback"]

        first_step_fields = await scratch.fetch(
            sa.select(fields.c.name).where(fields.c.step_id == step_rows[0].id).order_by(fields.c.order)
        )
        assert [f.name for f in first_step_fields] == [
            "permit_reference",
            "permit_category",
            "work_location",
            "valid_from",
            "valid_to",
        ]

    async def test_nothing_is_seeded_without_a_tenant(self, tmp_path):
        import src.domain.models  # noqa: F401
        from src.infrastructure.database import Base

        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'no-tenant.db'}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        db = ScratchDb(engine)
        try:
            assert await db.apply() == []
            assert await db.scalar(sa.select(sa.func.count()).select_from(TABLES["form_templates"])) == 0
        finally:
            await engine.dispose()

    async def test_an_existing_slug_is_never_replaced(self, scratch: ScratchDb):
        await scratch.run(
            lambda conn: conn.execute(
                TABLES["form_templates"]
                .insert()
                .values(
                    tenant_id=TENANT,
                    name="Bespoke Permit Form",
                    slug="permit-to-work-record",
                    form_type="custom",
                    version=1,
                    is_active=True,
                    is_published=False,
                    allow_drafts=True,
                    allow_attachments=True,
                    require_signature=False,
                    auto_assign_reference=True,
                    notify_on_submit=False,
                    created_at=sa.func.now(),
                    updated_at=sa.func.now(),
                )
            )
        )

        inserted = await scratch.apply()

        assert len(inserted) == 2
        table = TABLES["form_templates"]
        assert (
            await scratch.scalar(sa.select(table.c.name).where(table.c.slug == "permit-to-work-record"))
            == "Bespoke Permit Form"
        )


class TestIdempotency:
    async def test_repeat_runs_change_nothing(self, scratch: ScratchDb):
        assert len(await scratch.apply()) == 3

        for _ in range(2):
            assert await scratch.apply() == []

        assert await scratch.scalar(sa.select(sa.func.count()).select_from(TABLES["form_templates"])) == 3
        assert await scratch.scalar(sa.select(sa.func.count()).select_from(TABLES["form_steps"])) == EXPECTED_STEPS
        assert await scratch.scalar(sa.select(sa.func.count()).select_from(TABLES["form_fields"])) == EXPECTED_FIELDS


class TestDowngrade:
    async def test_downgrade_removes_exactly_what_was_seeded(self, scratch: ScratchDb):
        await scratch.apply()

        assert await scratch.revert() == 3

        for table in ("form_templates", "form_steps", "form_fields"):
            remaining = await scratch.scalar(sa.select(sa.func.count()).select_from(TABLES[table]))
            assert remaining == 0, f"{table} still has {remaining} rows after downgrade"

    async def test_downgrade_keeps_a_template_an_administrator_has_edited(self, scratch: ScratchDb):
        await scratch.apply()
        await scratch.run(_bump_template_version("worker-consultation-record"))

        assert await scratch.revert() == 2

        table = TABLES["form_templates"]
        assert [r.slug for r in await scratch.fetch(sa.select(table.c.slug))] == ["worker-consultation-record"]

    async def test_downgrade_leaves_templates_it_never_inserted_alone(self, scratch: ScratchDb):
        await scratch.run(
            lambda conn: conn.execute(
                TABLES["form_templates"]
                .insert()
                .values(
                    tenant_id=TENANT,
                    name="Incident Report",
                    slug="incident",
                    form_type="incident",
                    version=1,
                    is_active=True,
                    is_published=True,
                    allow_drafts=True,
                    allow_attachments=True,
                    require_signature=False,
                    auto_assign_reference=True,
                    notify_on_submit=True,
                    created_at=sa.func.now(),
                    updated_at=sa.func.now(),
                )
            )
        )
        await scratch.apply()

        await scratch.revert()

        table = TABLES["form_templates"]
        assert [r.slug for r in await scratch.fetch(sa.select(table.c.slug))] == ["incident"]

    async def test_downgrade_clears_the_ledger(self, scratch: ScratchDb):
        await scratch.apply()

        await scratch.revert()

        settings_table = TABLES["system_settings"]
        remaining = await scratch.scalar(
            sa.select(sa.func.count())
            .select_from(settings_table)
            .where(settings_table.c.key == migration.SEED_LEDGER_KEY)
        )
        assert remaining == 0

    async def test_downgrade_is_safe_when_nothing_was_applied(self, scratch: ScratchDb):
        assert await scratch.revert() == 0


async def _run_on_app_db(fn):
    from src.infrastructure.database import engine

    async with engine.begin() as conn:
        return await conn.run_sync(fn)


class TestVisibleThroughTheApi:
    """What a staff user sees after opening the register from the hub."""

    @pytest.fixture(autouse=True)
    async def _templates_present(self):
        """Seeded by the deploy migration on Postgres; seed here for a fresh schema."""
        await _run_on_app_db(migration.seed_register_form_templates)

    async def test_all_three_are_listed_in_the_form_builder(self, admin_client: AsyncClient):
        response = await admin_client.get("/api/v1/admin/config/templates?page_size=100")
        assert response.status_code == 200, response.text
        slugs = {item["slug"] for item in response.json()["items"]}
        assert set(DOC_REF_TO_SLUG.values()) <= slugs

    @pytest.mark.parametrize("doc_ref,slug", sorted(DOC_REF_TO_SLUG.items()))
    async def test_the_listed_template_carries_its_pel_reference(
        self, admin_client: AsyncClient, doc_ref: str, slug: str
    ):
        response = await admin_client.get("/api/v1/admin/config/templates?page_size=100")
        item = next(i for i in response.json()["items"] if i["slug"] == slug)
        assert item["name"].startswith(doc_ref)
        assert item["is_published"] is False

    @pytest.mark.parametrize("slug", sorted(DOC_REF_TO_SLUG.values()))
    async def test_by_slug_refuses_an_unpublished_template(self, admin_client: AsyncClient, slug: str):
        """The by-slug read is the portal's route in; a draft must not be served as live."""
        response = await admin_client.get(f"/api/v1/admin/config/templates/by-slug/{slug}")
        assert response.status_code == 404, response.text
