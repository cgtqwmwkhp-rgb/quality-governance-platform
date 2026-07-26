"""Behavioural tests for Alembic revision ``20260827_lookup_tenant_fix``.

The migration only moves and seeds data, so what is worth testing is the
outcome: that lookup options stranded at ``tenant_id IS NULL`` become readable
through the tenant-filtered API (PX-119, PX-120), that the four portal intake
templates are served instead of 404ing (PX-306), that re-running changes
nothing and creates no duplicates, and that the downgrade puts everything back.

Two harnesses, deliberately:

* Migration mechanics — adoption counts, collisions, tenant resolution,
  idempotency, downgrade, ledger — run against a **scratch database** created
  per test. Integration tests share a persistent schema on Postgres, where this
  migration has already been applied by the CI ``alembic upgrade head`` step; a
  downgrade run against that shared database would delete rows other tests
  depend on and leave the schema mid-rollback.
* Visibility through the API runs against the app database, using a generated
  lookup category so the assertions read only this test's rows, and driving the
  seed helpers with an explicit tenant so the result does not depend on how
  many tenants earlier tests happened to leave behind.

The migration module is loaded by file path because ``alembic/versions`` is not
an importable package. The repo also ships an empty ``alembic/__init__.py`` that
shadows the installed distribution once the repo root is on ``sys.path``, so
``alembic.op`` is stubbed for the load: these tests drive the migration's
helpers directly and never go through ``op.get_bind()``.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20260827_backfill_lookup_tenant_and_seed_portal_forms.py"

PORTAL_SLUGS = ("incident", "near-miss", "complaint", "rta")
TENANT = 1


def _load_migration() -> ModuleType:
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("qgp_portal_intake_repair", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migration = _load_migration()
TABLES = migration._tables()


# --------------------------------------------------------------------------- #
#  Scratch database — migration mechanics, isolated from the shared schema      #
# --------------------------------------------------------------------------- #


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

    async def lookup_rows(self, category: str):
        table = TABLES["lookup_options"]
        return await self.fetch(
            sa.select(table.c.id, table.c.code, table.c.tenant_id, table.c.label)
            .where(table.c.category == category)
            .order_by(table.c.code)
        )

    async def add_tenant(self, tenant_id: int) -> None:
        await self.run(_insert_tenant(tenant_id))

    async def add_orphans(self, *rows: tuple[str, str, str]) -> None:
        await self.run(_insert_lookup_options(None, *rows))

    async def add_tenant_options(self, *rows: tuple[str, str, str]) -> None:
        await self.run(_insert_lookup_options(TENANT, *rows))

    async def apply(self):
        return await self.run(migration.apply_portal_intake_repair)

    async def revert(self):
        return await self.run(migration.revert_portal_intake_repair)


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

        # The ORM table, not raw SQL, so the model's column defaults are applied.
        conn.execute(
            Tenant.__table__.insert().values(
                id=tenant_id,
                name=f"Tenant {tenant_id}",
                slug=f"tenant-{tenant_id}",
                admin_email=f"admin@tenant-{tenant_id}.example.com",
            )
        )

    return _apply


def _insert_lookup_options(tenant_id: int | None, *rows: tuple[str, str, str]):
    """Insert options at a given scope; ``None`` reproduces the orphaned rows."""

    def _apply(conn):
        for category, code, label in rows:
            conn.execute(
                TABLES["lookup_options"]
                .insert()
                .values(
                    tenant_id=tenant_id,
                    category=category,
                    code=code,
                    label=label,
                    is_active=True,
                    display_order=1,
                    created_at=sa.func.now(),
                    updated_at=sa.func.now(),
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


# The seven workforce_roles production is carrying at tenant_id NULL.
PRODUCTION_ORPHANS = (
    ("workforce_roles", "mobile-engineer", "Mobile Engineer"),
    ("workforce_roles", "workshop-pehq", "Workshop (PE HQ)"),
    ("workforce_roles", "workshop-fixed", "Vehicle Workshop (Fixed Customer Site)"),
    ("workforce_roles", "office", "Office Based Employee"),
    ("workforce_roles", "trainee", "Trainee/Apprentice"),
    ("workforce_roles", "non-pe", "Non-Plantexpand Employee"),
    ("workforce_roles", "other", "Other"),
)


class TestAdoption:
    """PX-119 / PX-120 — the values are configured, the tenant just cannot see them."""

    async def test_orphans_are_adopted_with_their_values_intact(self, scratch: ScratchDb):
        await scratch.add_orphans(*PRODUCTION_ORPHANS)

        await scratch.apply()

        rows = await scratch.lookup_rows("workforce_roles")
        assert {r.tenant_id for r in rows} == {TENANT}
        assert sorted(r.label for r in rows) == sorted(
            label for _, _, label in PRODUCTION_ORPHANS
        ), "the repair should adopt the administrator's existing values, not substitute new ones"

    async def test_counts_are_reported_per_category(self, scratch: ScratchDb):
        await scratch.add_orphans(*PRODUCTION_ORPHANS)
        await scratch.add_orphans(("severity_levels", "low", "Low"), ("severity_levels", "high", "High"))

        report = await scratch.apply()

        assert report["per_category"] == {
            "severity_levels": {"adopted": 2, "skipped_duplicate": 0},
            "workforce_roles": {"adopted": 7, "skipped_duplicate": 0},
        }

    async def test_nothing_to_adopt_is_not_an_error(self, scratch: ScratchDb):
        report = await scratch.apply()
        assert report["per_category"] == {}
        assert report["adopted_lookup_options"] == []


class TestCollisionHandling:
    """``customers`` has rows at both scopes on production; adopting blindly duplicates."""

    async def test_orphan_is_skipped_when_the_tenant_already_has_that_code(self, scratch: ScratchDb):
        await scratch.add_tenant_options(("customers", "ukpn", "UK Power Networks (renamed)"))
        await scratch.add_orphans(("customers", "ukpn", "UKPN"), ("customers", "cadent", "Cadent"))

        report = await scratch.apply()

        assert report["per_category"]["customers"] == {"adopted": 1, "skipped_duplicate": 1}
        visible = [r for r in await scratch.lookup_rows("customers") if r.tenant_id == TENANT]
        assert sorted(r.code for r in visible) == ["cadent", "ukpn"], "the tenant should see each code exactly once"
        assert next(r for r in visible if r.code == "ukpn").label == "UK Power Networks (renamed)"

    async def test_skipped_orphan_is_left_exactly_where_it_was(self, scratch: ScratchDb):
        await scratch.add_tenant_options(("customers", "ukpn", "UKPN (tenant)"))
        await scratch.add_orphans(("customers", "ukpn", "UKPN (orphan)"))

        await scratch.apply()

        rows = await scratch.lookup_rows("customers")
        assert sorted(((r.tenant_id, r.label) for r in rows), key=lambda r: r[1]) == [
            (None, "UKPN (orphan)"),
            (TENANT, "UKPN (tenant)"),
        ]

    async def test_two_orphans_sharing_a_code_do_not_both_get_adopted(self, scratch: ScratchDb):
        await scratch.add_orphans(("customers", "ukpn", "UKPN one"), ("customers", "ukpn", "UKPN two"))

        report = await scratch.apply()

        assert report["per_category"]["customers"] == {"adopted": 1, "skipped_duplicate": 1}

    async def test_no_duplicate_code_within_a_tenant_and_category(self, scratch: ScratchDb):
        await scratch.add_tenant_options(("customers", "ukpn", "UKPN (tenant)"))
        await scratch.add_orphans(*PRODUCTION_ORPHANS, ("customers", "ukpn", "UKPN"))

        await scratch.apply()

        table = TABLES["lookup_options"]
        duplicates = await scratch.fetch(
            sa.select(table.c.category, table.c.code, sa.func.count())
            .where(table.c.tenant_id.is_not(None))
            .group_by(table.c.category, table.c.code, table.c.tenant_id)
            .having(sa.func.count() > 1)
        )
        assert duplicates == []


class TestTenantResolution:
    """The tenant is resolved from the database, never assumed to be 1."""

    async def test_repair_refuses_rather_than_guessing_when_tenants_are_ambiguous(self, scratch: ScratchDb):
        await scratch.add_orphans(*PRODUCTION_ORPHANS)
        await scratch.add_tenant(2)

        with pytest.raises(migration.AmbiguousTenantError):
            await scratch.apply()

        assert all(
            row.tenant_id is None for row in await scratch.lookup_rows("workforce_roles")
        ), "a refused migration must not have adopted anything"

    async def test_extra_tenants_are_harmless_when_there_is_nothing_to_adopt(self, scratch: ScratchDb):
        await scratch.add_tenant(2)

        report = await scratch.apply()

        assert report["per_category"] == {}
        assert len(report["form_templates"]) == len(migration.PORTAL_FORM_TEMPLATES)

    async def test_orphans_are_adopted_by_whichever_tenant_exists(self, tmp_path):
        """The tenant id is read from the table, so a non-default id still works."""
        import src.domain.models  # noqa: F401
        from src.infrastructure.database import Base

        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'other-tenant.db'}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        db = ScratchDb(engine)
        try:
            await db.add_tenant(7)
            await db.add_orphans(*PRODUCTION_ORPHANS)

            await db.apply()

            assert {r.tenant_id for r in await db.lookup_rows("workforce_roles")} == {7}
        finally:
            await engine.dispose()


class TestSeededTemplates:
    async def test_the_four_portal_templates_are_created_published(self, scratch: ScratchDb):
        await scratch.apply()

        table = TABLES["form_templates"]
        rows = await scratch.fetch(sa.select(table.c.slug, table.c.is_published, table.c.is_active, table.c.tenant_id))
        assert sorted(r.slug for r in rows) == sorted(PORTAL_SLUGS)
        assert all(bool(r.is_published) and bool(r.is_active) and r.tenant_id == TENANT for r in rows)

    async def test_steps_and_fields_mirror_the_frontend_fallbacks(self, scratch: ScratchDb):
        await scratch.apply()

        templates, steps, fields = TABLES["form_templates"], TABLES["form_steps"], TABLES["form_fields"]
        incident_id = await scratch.scalar(sa.select(templates.c.id).where(templates.c.slug == "incident"))
        step_rows = await scratch.fetch(
            sa.select(steps.c.id, steps.c.name).where(steps.c.template_id == incident_id).order_by(steps.c.order)
        )
        assert [s.name for s in step_rows] == [
            "Customer Details",
            "People & Location",
            "What Happened",
            "Injuries & Evidence",
        ]

        person_role = await scratch.fetch(
            sa.select(fields.c.field_type, fields.c.is_required).where(
                fields.c.step_id.in_([s.id for s in step_rows]), fields.c.name == "person_role"
            )
        )
        assert len(person_role) == 1
        assert person_role[0].field_type == "select"
        assert bool(person_role[0].is_required) is True

    async def test_an_existing_slug_is_never_replaced(self, scratch: ScratchDb):
        await scratch.run(
            lambda conn: conn.execute(
                TABLES["form_templates"]
                .insert()
                .values(
                    tenant_id=TENANT,
                    name="Bespoke Incident Form",
                    slug="incident",
                    form_type="incident",
                    version=1,
                    is_active=True,
                    is_published=False,
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

        report = await scratch.apply()

        assert len(report["form_templates"]) == len(migration.PORTAL_FORM_TEMPLATES) - 1
        table = TABLES["form_templates"]
        assert await scratch.scalar(sa.select(table.c.name).where(table.c.slug == "incident")) == (
            "Bespoke Incident Form"
        )


class TestIdempotency:
    async def test_repeat_runs_change_nothing(self, scratch: ScratchDb):
        await scratch.add_orphans(*PRODUCTION_ORPHANS)

        first = await scratch.apply()
        assert first["adopted_lookup_options"], "first run should have adopted the orphans"
        assert first["form_templates"], "first run should have seeded the templates"
        baseline = await scratch.lookup_rows("workforce_roles")

        for _ in range(2):
            repeat = await scratch.apply()
            assert repeat["adopted_lookup_options"] == []
            assert repeat["form_templates"] == []

        assert await scratch.lookup_rows("workforce_roles") == baseline
        assert await scratch.scalar(sa.select(sa.func.count()).select_from(TABLES["form_templates"])) == len(
            migration.PORTAL_FORM_TEMPLATES
        )
        assert await scratch.scalar(sa.select(sa.func.count()).select_from(TABLES["form_steps"])) == 13
        assert await scratch.scalar(sa.select(sa.func.count()).select_from(TABLES["form_fields"])) == 42


class TestDowngrade:
    async def test_downgrade_restores_the_previous_state_exactly(self, scratch: ScratchDb):
        await scratch.add_orphans(*PRODUCTION_ORPHANS)
        before = await scratch.lookup_rows("workforce_roles")
        await scratch.apply()

        reverted = await scratch.revert()

        assert reverted == {"adopted_lookup_options": 7, "form_templates": 4}
        assert await scratch.lookup_rows("workforce_roles") == before
        for table in ("form_templates", "form_steps", "form_fields"):
            remaining = await scratch.scalar(sa.select(sa.func.count()).select_from(TABLES[table]))
            assert remaining == 0, f"{table} still has {remaining} rows after downgrade"

    async def test_downgrade_releases_adopted_rows_instead_of_deleting_them(self, scratch: ScratchDb):
        await scratch.add_orphans(*PRODUCTION_ORPHANS)
        await scratch.apply()

        await scratch.revert()

        assert (
            len(await scratch.lookup_rows("workforce_roles")) == 7
        ), "the migration did not create these rows, so it must not delete them"

    async def test_downgrade_leaves_rows_it_never_adopted_alone(self, scratch: ScratchDb):
        await scratch.add_tenant_options(("customers", "ukpn", "UKPN (tenant)"))
        await scratch.add_orphans(("customers", "cadent", "Cadent"))
        await scratch.apply()

        await scratch.revert()

        rows = {r.code: r.tenant_id for r in await scratch.lookup_rows("customers")}
        assert rows == {"ukpn": TENANT, "cadent": None}

    async def test_downgrade_clears_the_ledger(self, scratch: ScratchDb):
        await scratch.add_orphans(*PRODUCTION_ORPHANS)
        await scratch.apply()

        await scratch.revert()

        settings_table = TABLES["system_settings"]
        remaining = await scratch.scalar(
            sa.select(sa.func.count())
            .select_from(settings_table)
            .where(settings_table.c.key == migration.SEED_LEDGER_KEY)
        )
        assert remaining == 0

    async def test_downgrade_keeps_a_template_an_administrator_has_edited(self, scratch: ScratchDb):
        """The API bumps ``version`` on every edit; anything past 1 is not ours to delete."""
        await scratch.apply()
        await scratch.run(_bump_template_version("incident"))

        await scratch.revert()

        table = TABLES["form_templates"]
        assert [r.slug for r in await scratch.fetch(sa.select(table.c.slug))] == ["incident"]

    async def test_downgrade_is_safe_when_nothing_was_applied(self, scratch: ScratchDb):
        assert await scratch.revert() == {"adopted_lookup_options": 0, "form_templates": 0}


# --------------------------------------------------------------------------- #
#  App database — what a real caller sees through the API afterwards            #
# --------------------------------------------------------------------------- #


async def _run_on_app_db(fn):
    from src.infrastructure.database import engine

    async with engine.begin() as conn:
        return await conn.run_sync(fn)


@pytest.fixture
def category() -> str:
    """A lookup category unique to this test, so assertions read only its rows."""
    return f"px119_{uuid4().hex[:12]}"


class TestVisibleThroughTheApi:
    """The point of the repair: a tenant-filtered read returns the configured values."""

    async def test_orphans_are_invisible_until_they_are_adopted(self, admin_client: AsyncClient, category: str):
        await _run_on_app_db(_insert_lookup_options(None, (category, "mobile-engineer", "Mobile Engineer")))

        before = await admin_client.get(f"/api/v1/admin/config/lookup/{category}?is_active=true")
        assert before.status_code == 200, before.text
        assert before.json()["total"] == 0, "a tenant-filtered read must not see tenant_id NULL rows"

        # Driven with an explicit tenant: tenant resolution is covered against the
        # scratch database, and the shared schema's tenant count is not this
        # test's business.
        await _run_on_app_db(
            lambda conn: migration._adopt_orphaned_lookup_options(conn, TABLES, [TENANT], datetime.now(timezone.utc))
        )

        after = await admin_client.get(f"/api/v1/admin/config/lookup/{category}?is_active=true")
        assert after.status_code == 200, after.text
        assert [item["code"] for item in after.json()["items"]] == ["mobile-engineer"]


class TestPortalTemplatesAreServed:
    """PX-306 — the by-slug endpoint must return the template, not 404 and not 500."""

    @pytest.fixture(autouse=True)
    async def _templates_present(self):
        """Seeded by the deploy migration on Postgres; seed here for a fresh schema."""
        await _run_on_app_db(
            lambda conn: migration._seed_form_templates(conn, TABLES, [TENANT], datetime.now(timezone.utc))
        )

    @pytest.mark.parametrize("slug", PORTAL_SLUGS)
    async def test_by_slug_returns_a_published_template_with_its_steps(self, admin_client: AsyncClient, slug: str):
        response = await admin_client.get(f"/api/v1/admin/config/templates/by-slug/{slug}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["slug"] == slug
        assert body["is_published"] is True
        assert body["is_active"] is True
        assert body["steps"], f"template '{slug}' was served with no steps"

    async def test_incident_template_carries_the_required_person_role_field(self, admin_client: AsyncClient):
        response = await admin_client.get("/api/v1/admin/config/templates/by-slug/incident")
        assert response.status_code == 200, response.text
        fields = [field for step in response.json()["steps"] for field in step["fields"]]
        person_role = next(f for f in fields if f["name"] == "person_role")
        assert person_role["field_type"] == "select"
        assert person_role["is_required"] is True

    async def test_served_form_matches_the_frontend_fallback(self, admin_client: AsyncClient):
        """The seed mirrors PortalDynamicForm's FALLBACK_TEMPLATES, not an invented set."""
        response = await admin_client.get("/api/v1/admin/config/templates/by-slug/incident")
        steps = response.json()["steps"]
        assert [s["name"] for s in steps] == [
            "Customer Details",
            "People & Location",
            "What Happened",
            "Injuries & Evidence",
        ]
        assert [f["name"] for f in steps[0]["fields"]] == ["contract"]

    async def test_all_four_are_listed_for_the_tenant(self, admin_client: AsyncClient):
        response = await admin_client.get("/api/v1/admin/config/templates?page_size=100")
        assert response.status_code == 200, response.text
        slugs = {item["slug"] for item in response.json()["items"]}
        assert set(PORTAL_SLUGS) <= slugs
