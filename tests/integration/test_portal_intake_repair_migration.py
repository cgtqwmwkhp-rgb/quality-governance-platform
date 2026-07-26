"""Behavioural tests for Alembic revision ``20260827_lookup_tenant_fix``.

The migration only moves and seeds data, so what is worth testing is the
outcome: that lookup options stranded at ``tenant_id IS NULL`` become readable
through the tenant-filtered API (PX-119, PX-120), that the four portal intake
templates stop returning 404 (PX-306), that re-running changes nothing and
creates no duplicates, and that the downgrade puts everything back.

The migration module is loaded by file path because ``alembic/versions`` is not
an importable package. The repo also ships an empty ``alembic/__init__.py`` that
shadows the installed distribution once the repo root is on ``sys.path``, so
``alembic.op`` is stubbed for the load: these tests drive the migration's
helpers directly against a real connection and never go through
``op.get_bind()``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import sqlalchemy as sa
from httpx import AsyncClient

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


async def _run(fn):
    """Execute a sync callable that takes a Connection, against the app engine."""
    from src.infrastructure.database import engine

    async with engine.begin() as conn:
        return await conn.run_sync(fn)


async def _fetch(statement: sa.sql.expression.Executable):
    from src.infrastructure.database import engine

    async with engine.connect() as conn:
        return (await conn.execute(statement)).all()


async def _scalar(statement: sa.sql.expression.Executable):
    from src.infrastructure.database import engine

    async with engine.connect() as conn:
        return (await conn.execute(statement)).scalar_one()


def _insert_orphans(*rows: tuple[str, str, str]):
    """Insert ``tenant_id IS NULL`` options, as the old seed migrations did."""

    def _apply(conn):
        for category, code, label in rows:
            conn.execute(
                TABLES["lookup_options"]
                .insert()
                .values(
                    tenant_id=None,
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


def _insert_template(slug: str, name: str):
    """Insert a template the way an administrator's own row would look."""

    def _apply(conn):
        conn.execute(
            TABLES["form_templates"]
            .insert()
            .values(
                tenant_id=TENANT,
                name=name,
                slug=slug,
                form_type=slug,
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

    return _apply


def _bump_template_version(slug: str):
    """Stand in for an administrator editing the template through the API."""

    def _apply(conn):
        table = TABLES["form_templates"]
        result = conn.execute(table.update().where(table.c.slug == slug).values(version=2))
        assert result.rowcount == 1, f"no template with slug '{slug}' to edit"

    return _apply


def _apply_repair(conn):
    return migration.apply_portal_intake_repair(conn)


def _revert_repair(conn):
    return migration.revert_portal_intake_repair(conn)


async def _lookup_rows(category: str):
    table = TABLES["lookup_options"]
    return await _fetch(
        sa.select(table.c.code, table.c.tenant_id, table.c.label)
        .where(table.c.category == category)
        .order_by(table.c.code)
    )


@pytest.fixture
async def orphaned_workforce_roles():
    """The seven ``workforce_roles`` production is carrying at tenant_id NULL."""
    await _run(
        _insert_orphans(
            ("workforce_roles", "mobile-engineer", "Mobile Engineer"),
            ("workforce_roles", "workshop-pehq", "Workshop (PE HQ)"),
            ("workforce_roles", "workshop-fixed", "Vehicle Workshop (Fixed Customer Site)"),
            ("workforce_roles", "office", "Office Based Employee"),
            ("workforce_roles", "trainee", "Trainee/Apprentice"),
            ("workforce_roles", "non-pe", "Non-Plantexpand Employee"),
            ("workforce_roles", "other", "Other"),
        )
    )


class TestOrphanedOptionsBecomeReadable:
    """PX-119 / PX-120 — the values are configured, the tenant just cannot see them."""

    async def test_orphans_are_invisible_before_the_repair(self, admin_client: AsyncClient, orphaned_workforce_roles):
        response = await admin_client.get("/api/v1/admin/config/lookup/workforce_roles?is_active=true")
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 0, "tenant-filtered read should not see tenant_id NULL rows"

    async def test_repair_makes_them_visible_without_inventing_values(
        self, admin_client: AsyncClient, orphaned_workforce_roles
    ):
        await _run(_apply_repair)

        response = await admin_client.get("/api/v1/admin/config/lookup/workforce_roles?is_active=true")
        assert response.status_code == 200, response.text
        codes = sorted(item["code"] for item in response.json()["items"])
        assert codes == [
            "mobile-engineer",
            "non-pe",
            "office",
            "other",
            "trainee",
            "workshop-fixed",
            "workshop-pehq",
        ], "the repair should adopt the administrator's existing values, not substitute new ones"

    async def test_repair_reports_counts_per_category(self, orphaned_workforce_roles):
        await _run(_insert_orphans(("severity_levels", "low", "Low"), ("severity_levels", "high", "High")))

        report = await _run(_apply_repair)

        assert report["per_category"]["workforce_roles"] == {"adopted": 7, "skipped_duplicate": 0}
        assert report["per_category"]["severity_levels"] == {"adopted": 2, "skipped_duplicate": 0}


class TestCollisionHandling:
    """``customers`` has rows at both scopes on production; adopting blindly duplicates."""

    async def test_orphan_is_skipped_when_the_tenant_already_has_that_code(
        self, superuser_client: AsyncClient, admin_client: AsyncClient
    ):
        create = await superuser_client.post(
            "/api/v1/admin/config/lookup/customers",
            json={"code": "ukpn", "label": "UK Power Networks (renamed)", "is_active": True, "display_order": 1},
        )
        assert create.status_code == 201, create.text
        await _run(_insert_orphans(("customers", "ukpn", "UKPN"), ("customers", "cadent", "Cadent")))

        report = await _run(_apply_repair)

        assert report["per_category"]["customers"] == {"adopted": 1, "skipped_duplicate": 1}

        listed = await admin_client.get("/api/v1/admin/config/lookup/customers")
        items = listed.json()["items"]
        assert sorted(i["code"] for i in items) == ["cadent", "ukpn"], "the tenant should see each code exactly once"
        ukpn = next(i for i in items if i["code"] == "ukpn")
        assert ukpn["label"] == "UK Power Networks (renamed)", "the tenant's own row must win"

    async def test_skipped_orphan_is_left_untouched(self, superuser_client: AsyncClient):
        await superuser_client.post(
            "/api/v1/admin/config/lookup/customers",
            json={"code": "ukpn", "label": "UKPN (tenant)", "is_active": True, "display_order": 1},
        )
        await _run(_insert_orphans(("customers", "ukpn", "UKPN (orphan)")))

        await _run(_apply_repair)

        rows = await _lookup_rows("customers")
        assert sorted(((r.tenant_id, r.label) for r in rows), key=lambda r: r[1]) == [
            (None, "UKPN (orphan)"),
            (TENANT, "UKPN (tenant)"),
        ]

    async def test_no_duplicate_code_within_a_tenant_and_category(self, orphaned_workforce_roles):
        await _run(_apply_repair)

        table = TABLES["lookup_options"]
        duplicates = await _fetch(
            sa.select(table.c.category, table.c.code, sa.func.count())
            .where(table.c.tenant_id.is_not(None))
            .group_by(table.c.category, table.c.code, table.c.tenant_id)
            .having(sa.func.count() > 1)
        )
        assert duplicates == []


class TestAmbiguousTenant:
    async def test_repair_refuses_rather_than_guessing_when_tenants_are_ambiguous(
        self, orphaned_workforce_roles, test_session
    ):
        from tests.factories import TenantFactory

        test_session.add(TenantFactory.build(id=99, name="Second Org", slug="second-org"))
        await test_session.commit()

        with pytest.raises(migration.AmbiguousTenantError):
            await _run(_apply_repair)

        assert all(row.tenant_id is None for row in await _lookup_rows("workforce_roles"))

    async def test_extra_tenants_are_harmless_when_there_is_nothing_to_adopt(self, test_session):
        from tests.factories import TenantFactory

        test_session.add(TenantFactory.build(id=99, name="Second Org", slug="second-org"))
        await test_session.commit()

        report = await _run(_apply_repair)
        assert report["per_category"] == {}


class TestFormTemplatesAreServed:
    """PX-306 — the by-slug endpoint 404s purely because nothing seeded the rows."""

    async def test_by_slug_returns_404_before_the_repair(self, admin_client: AsyncClient):
        response = await admin_client.get("/api/v1/admin/config/templates/by-slug/incident")
        assert response.status_code == 404, response.text

    @pytest.mark.parametrize("slug", PORTAL_SLUGS)
    async def test_by_slug_returns_a_published_template_after_the_repair(self, admin_client: AsyncClient, slug: str):
        await _run(_apply_repair)

        response = await admin_client.get(f"/api/v1/admin/config/templates/by-slug/{slug}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["slug"] == slug
        assert body["is_published"] is True
        assert body["is_active"] is True
        assert body["steps"], f"template '{slug}' was served with no steps"

    async def test_incident_template_carries_the_required_person_role_field(self, admin_client: AsyncClient):
        await _run(_apply_repair)

        response = await admin_client.get("/api/v1/admin/config/templates/by-slug/incident")
        assert response.status_code == 200, response.text
        fields = [field for step in response.json()["steps"] for field in step["fields"]]
        person_role = next(f for f in fields if f["name"] == "person_role")
        assert person_role["field_type"] == "select"
        assert person_role["is_required"] is True

    async def test_seeded_template_matches_the_frontend_fallback_shape(self, admin_client: AsyncClient):
        """The seed mirrors PortalDynamicForm's FALLBACK_TEMPLATES, not an invented set."""
        await _run(_apply_repair)

        response = await admin_client.get("/api/v1/admin/config/templates/by-slug/incident")
        steps = response.json()["steps"]
        assert [s["name"] for s in steps] == [
            "Customer Details",
            "People & Location",
            "What Happened",
            "Injuries & Evidence",
        ]
        assert [f["name"] for f in steps[0]["fields"]] == ["contract"]

    async def test_existing_template_slug_is_left_alone(self, admin_client: AsyncClient):
        await _run(_insert_template("incident", "Bespoke Incident Form"))

        report = await _run(_apply_repair)
        assert len(report["form_templates"]) == len(migration.PORTAL_FORM_TEMPLATES) - 1

        listed = await admin_client.get("/api/v1/admin/config/templates?page_size=100")
        incident = next(t for t in listed.json()["items"] if t["slug"] == "incident")
        assert incident["name"] == "Bespoke Incident Form"


class TestIdempotency:
    async def test_repeat_runs_change_nothing(self, admin_client: AsyncClient, orphaned_workforce_roles):
        first = await _run(_apply_repair)
        assert first["adopted_lookup_options"], "first run should have adopted the orphans"
        assert first["form_templates"], "first run should have seeded the templates"
        baseline = await _lookup_rows("workforce_roles")

        for _ in range(2):
            repeat = await _run(_apply_repair)
            assert repeat["adopted_lookup_options"] == []
            assert repeat["form_templates"] == []

        assert await _lookup_rows("workforce_roles") == baseline
        assert await _scalar(sa.select(sa.func.count()).select_from(TABLES["form_templates"])) == len(
            migration.PORTAL_FORM_TEMPLATES
        )
        assert await _scalar(sa.select(sa.func.count()).select_from(TABLES["form_steps"])) == 13
        assert await _scalar(sa.select(sa.func.count()).select_from(TABLES["form_fields"])) == 42


class TestDowngrade:
    async def test_downgrade_returns_adopted_rows_to_their_previous_state(self, orphaned_workforce_roles):
        before = await _lookup_rows("workforce_roles")
        await _run(_apply_repair)

        reverted = await _run(_revert_repair)

        assert reverted["adopted_lookup_options"] == 7
        assert await _lookup_rows("workforce_roles") == before

    async def test_downgrade_never_deletes_the_administrators_options(self, orphaned_workforce_roles):
        await _run(_apply_repair)
        await _run(_revert_repair)

        assert len(await _lookup_rows("workforce_roles")) == 7, "adopted rows must be released, not destroyed"

    async def test_downgrade_removes_the_seeded_templates(self, admin_client: AsyncClient):
        await _run(_apply_repair)

        await _run(_revert_repair)

        for slug in PORTAL_SLUGS:
            response = await admin_client.get(f"/api/v1/admin/config/templates/by-slug/{slug}")
            assert response.status_code == 404, f"template '{slug}' survived the downgrade"
        for table in ("form_templates", "form_steps", "form_fields"):
            remaining = await _scalar(sa.select(sa.func.count()).select_from(TABLES[table]))
            assert remaining == 0, f"{table} still has {remaining} rows after downgrade"

    async def test_downgrade_clears_the_ledger(self, orphaned_workforce_roles):
        await _run(_apply_repair)
        await _run(_revert_repair)

        settings_table = TABLES["system_settings"]
        remaining = await _scalar(
            sa.select(sa.func.count())
            .select_from(settings_table)
            .where(settings_table.c.key == migration.SEED_LEDGER_KEY)
        )
        assert remaining == 0

    async def test_downgrade_keeps_a_template_an_administrator_has_edited(self, admin_client: AsyncClient):
        """The API bumps ``version`` on every edit; anything past 1 is not ours to delete."""
        await _run(_apply_repair)
        await _run(_bump_template_version("incident"))

        await _run(_revert_repair)

        survivors = await admin_client.get("/api/v1/admin/config/templates?page_size=100")
        assert [t["slug"] for t in survivors.json()["items"]] == ["incident"]

    async def test_downgrade_is_safe_when_nothing_was_applied(self):
        assert await _run(_revert_repair) == {"adopted_lookup_options": 0, "form_templates": 0}
