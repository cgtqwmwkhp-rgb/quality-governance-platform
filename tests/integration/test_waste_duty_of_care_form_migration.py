"""Behavioural tests for Alembic revision ``20261117_reg_ssot_d2_waste`` (REG-SSOT-D2).

The revision only seeds data, so what is worth testing is the outcome: that
PEL-HSEQ-5052 has a form definition on the shared form-config spine, that the
record points at a Governance Library document rather than carrying a second
copy of the transfer note, that it is a *draft* rather than an advertised
portal journey, that a repeat run inserts nothing, and that the downgrade
removes exactly what this migration added — not the D1 trio.

Harness choices follow ``test_register_form_trio_migration.py``:

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
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20261117_seed_waste_duty_of_care_form.py"

TENANT = 1

DOC_REF = "PEL-HSEQ-5052"
# Mirrors frontend/src/data/registerCatalogue.ts — if the slug changes on one
# side without the other, the hub's Open lands on a Form Builder list where
# nothing matches the note the caption banner just printed.
SLUG = "waste-duty-of-care-record"

# Slugs seeded by 20261116_reg_ssot_d1_forms. D2 must not be able to remove them.
D1_TRIO_SLUGS = ("worker-consultation-record", "permit-to-work-record", "remote-working-record")


def _load_migration() -> ModuleType:
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("qgp_reg_ssot_d2_waste", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migration = _load_migration()
TABLES = migration._tables()

EXPECTED_STEPS = sum(len(d["steps"]) for d in migration.REGISTER_FORM_TEMPLATES)
EXPECTED_FIELDS = sum(len(step["fields"]) for d in migration.REGISTER_FORM_TEMPLATES for step in d["steps"])


def test_revision_chains_serially_from_the_d1_form_trio():
    """Single-head ratchet: this revision is what W4/W5 head pins must name next."""
    assert migration.revision == "20261117_reg_ssot_d2_waste"
    assert migration.down_revision == "20261116_reg_ssot_d1_forms"


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
        return await self.run(migration.seed_waste_duty_of_care_form)

    async def revert(self):
        return await self.run(migration.revert_waste_duty_of_care_form)


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


def _insert_template(slug: str, name: str, *, published: bool = False):
    def _apply(conn):
        conn.execute(
            TABLES["form_templates"]
            .insert()
            .values(
                tenant_id=TENANT,
                name=name,
                slug=slug,
                form_type="custom",
                version=1,
                is_active=True,
                is_published=published,
                allow_drafts=True,
                allow_attachments=True,
                require_signature=False,
                auto_assign_reference=True,
                notify_on_submit=False,
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


async def _fields(scratch: ScratchDb):
    fields = TABLES["form_fields"]
    return await scratch.fetch(
        sa.select(fields.c.name, fields.c.field_type, fields.c.pattern, fields.c.is_required, fields.c.help_text)
    )


class TestSeed:
    async def test_the_waste_register_template_is_created(self, scratch: ScratchDb):
        inserted = await scratch.apply()

        assert len(inserted) == 1
        table = TABLES["form_templates"]
        rows = await scratch.fetch(sa.select(table.c.slug, table.c.tenant_id, table.c.form_type))
        assert [r.slug for r in rows] == [SLUG]
        assert rows[0].tenant_id == TENANT
        assert (
            rows[0].form_type == "custom"
        ), "this is not an incident/complaint/rta/near_miss intake form and must not claim to be"

    async def test_the_template_is_seeded_as_an_unpublished_draft(self, scratch: ScratchDb):
        """Publishing means 'available in the portal'; no portal route serves this slug."""
        await scratch.apply()

        table = TABLES["form_templates"]
        row = (
            await scratch.fetch(
                sa.select(table.c.is_active, table.c.is_published, table.c.published_at).where(table.c.slug == SLUG)
            )
        )[0]
        assert bool(row.is_active)
        assert not bool(row.is_published)
        assert row.published_at is None

    async def test_the_template_names_its_pel_reference(self, scratch: ScratchDb):
        """The hub Open lands on a list; the PEL ref has to be visible on the card."""
        await scratch.apply()

        table = TABLES["form_templates"]
        name = await scratch.scalar(sa.select(table.c.name).where(table.c.slug == SLUG))
        assert name.startswith(DOC_REF)


class TestPointerNotASecondLibrary:
    """The register stores where the transfer note is filed, never the note."""

    async def test_attachments_are_off(self, scratch: ScratchDb):
        await scratch.apply()

        table = TABLES["form_templates"]
        allow_attachments = await scratch.scalar(sa.select(table.c.allow_attachments).where(table.c.slug == SLUG))
        assert not bool(
            allow_attachments
        ), "attachments here would grow a second blob store beside the Governance Library"

    async def test_no_field_uploads_a_file(self, scratch: ScratchDb):
        await scratch.apply()

        uploads = [f.name for f in await _fields(scratch) if f.field_type in {"file", "image"}]
        assert uploads == [], f"{uploads} would duplicate the note the Library already holds"

    async def test_the_pointer_field_is_required_and_names_the_library(self, scratch: ScratchDb):
        await scratch.apply()

        pointer = next(f for f in await _fields(scratch) if f.name == "transfer_note_pel_doc_ref")
        assert bool(pointer.is_required)
        assert pointer.field_type == "text"
        assert "Library" in (pointer.help_text or "")

    async def test_the_pointer_pattern_still_matches_the_authority_pack(self, scratch: ScratchDb):
        """R01 lives in northern-star-rules-v6.json; the migration carries a frozen copy.

        A migration has to keep producing the same rows forever, so it cannot
        read a spec file that may change. This is the guard on that copy: if
        the pack's reference pattern moves, someone has to decide whether the
        seeded field follows it, rather than the two silently diverging.
        """
        from src.domain.services.library_rules import reference_pattern

        await scratch.apply()

        pointer = next(f for f in await _fields(scratch) if f.name == "transfer_note_pel_doc_ref")
        assert pointer.pattern == reference_pattern().pattern

    async def test_the_pointer_pattern_accepts_an_allocated_reference_and_rejects_prose(self, scratch: ScratchDb):
        await scratch.apply()

        pointer = next(f for f in await _fields(scratch) if f.name == "transfer_note_pel_doc_ref")
        compiled = re.compile(pointer.pattern)
        # Shape issued by document_category_service.allocate_pel_doc_ref for
        # function HSEQ at cascade level 5 (Form/Register/Record).
        assert compiled.fullmatch("PEL-HSEQ-5001")
        for rejected in ("transfer note.pdf", "PEL-HSEQ-5052 Waste", "HSEQ-5001", "PEL-WASTE-5001"):
            assert not compiled.fullmatch(rejected), f"{rejected!r} is not a Library reference"

    async def test_the_ewc_code_pattern_accepts_hazardous_entries(self, scratch: ScratchDb):
        await scratch.apply()

        ewc = next(f for f in await _fields(scratch) if f.name == "ewc_code")
        compiled = re.compile(ewc.pattern)
        assert compiled.fullmatch("17 05 04")
        assert compiled.fullmatch("170503*"), "mirror/absolute hazardous entries carry a trailing asterisk"
        assert not compiled.fullmatch("1705")


class TestFormDefinition:
    async def test_no_field_depends_on_an_admin_lookup_catalogue(self, scratch: ScratchDb):
        """A required lookup-backed field with no options blocks publishing forever."""
        from src.domain.services.form_publish_validation import resolve_lookup_category

        await scratch.apply()

        fields = await _fields(scratch)
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
        template_id = await scratch.scalar(sa.select(templates.c.id).where(templates.c.slug == SLUG))
        step_rows = await scratch.fetch(
            sa.select(steps.c.id, steps.c.name).where(steps.c.template_id == template_id).order_by(steps.c.order)
        )
        assert [s.name for s in step_rows] == ["Waste Movement", "Transfer Parties", "Filed Transfer Note"]

        last_step_fields = await scratch.fetch(
            sa.select(fields.c.name).where(fields.c.step_id == step_rows[-1].id).order_by(fields.c.order)
        )
        assert [f.name for f in last_step_fields] == [
            "transfer_note_reference",
            "transfer_note_pel_doc_ref",
            "retain_until",
            "duty_of_care_notes",
        ]

    async def test_the_statutory_transfer_note_contents_are_captured(self, scratch: ScratchDb):
        """Reg 35 minimum: description, EWC code, quantity, containment, both parties, SIC."""
        await scratch.apply()

        names = {f.name for f in await _fields(scratch)}
        assert {
            "waste_description",
            "ewc_code",
            "quantity_description",
            "containment_type",
            "transferor_name",
            "transferor_sic_code",
            "transferee_name",
            "carrier_registration_number",
            "transfer_date",
        } <= names

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
        await scratch.run(_insert_template(SLUG, "Bespoke Waste Form"))

        assert await scratch.apply() == []

        table = TABLES["form_templates"]
        assert await scratch.scalar(sa.select(table.c.name).where(table.c.slug == SLUG)) == "Bespoke Waste Form"


class TestIdempotency:
    async def test_repeat_runs_change_nothing(self, scratch: ScratchDb):
        assert len(await scratch.apply()) == 1

        for _ in range(2):
            assert await scratch.apply() == []

        assert await scratch.scalar(sa.select(sa.func.count()).select_from(TABLES["form_templates"])) == 1
        assert await scratch.scalar(sa.select(sa.func.count()).select_from(TABLES["form_steps"])) == EXPECTED_STEPS
        assert await scratch.scalar(sa.select(sa.func.count()).select_from(TABLES["form_fields"])) == EXPECTED_FIELDS


class TestDowngrade:
    async def test_downgrade_removes_exactly_what_was_seeded(self, scratch: ScratchDb):
        await scratch.apply()

        assert await scratch.revert() == 1

        for table in ("form_templates", "form_steps", "form_fields"):
            remaining = await scratch.scalar(sa.select(sa.func.count()).select_from(TABLES[table]))
            assert remaining == 0, f"{table} still has {remaining} rows after downgrade"

    async def test_downgrade_keeps_a_template_an_administrator_has_edited(self, scratch: ScratchDb):
        await scratch.apply()
        await scratch.run(_bump_template_version(SLUG))

        assert await scratch.revert() == 0

        table = TABLES["form_templates"]
        assert [r.slug for r in await scratch.fetch(sa.select(table.c.slug))] == [SLUG]

    async def test_downgrade_leaves_the_d1_trio_alone(self, scratch: ScratchDb):
        """Separate ledger keys; D2's downgrade must not reach into D1's seed."""
        for slug in D1_TRIO_SLUGS:
            await scratch.run(_insert_template(slug, f"PEL-HSEQ-0000 {slug}"))
        await scratch.apply()

        await scratch.revert()

        table = TABLES["form_templates"]
        assert sorted(r.slug for r in await scratch.fetch(sa.select(table.c.slug))) == sorted(D1_TRIO_SLUGS)

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
    """What a staff user sees after opening PEL-HSEQ-5052 from the hub."""

    @pytest.fixture(autouse=True)
    async def _template_present(self):
        """Seeded by the deploy migration on Postgres; seed here for a fresh schema."""
        await _run_on_app_db(migration.seed_waste_duty_of_care_form)

    async def test_it_is_listed_in_the_form_builder(self, admin_client: AsyncClient):
        response = await admin_client.get("/api/v1/admin/config/templates?page_size=100")
        assert response.status_code == 200, response.text
        item = next(i for i in response.json()["items"] if i["slug"] == SLUG)
        assert item["name"].startswith(DOC_REF)
        assert item["is_published"] is False

    async def test_by_slug_refuses_the_unpublished_template(self, admin_client: AsyncClient):
        """The by-slug read is the portal's route in; a draft must not be served as live."""
        response = await admin_client.get(f"/api/v1/admin/config/templates/by-slug/{SLUG}")
        assert response.status_code == 404, response.text

    async def test_the_pointer_field_survives_the_api_round_trip(self, admin_client: AsyncClient):
        """`pattern` is only worth seeding if the Form Builder reads and keeps it."""
        listing = await admin_client.get("/api/v1/admin/config/templates?page_size=100")
        template_id = next(i["id"] for i in listing.json()["items"] if i["slug"] == SLUG)

        response = await admin_client.get(f"/api/v1/admin/config/templates/{template_id}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["allow_attachments"] is False
        fields = [f for step in body["steps"] for f in step["fields"]]
        pointer = next(f for f in fields if f["name"] == "transfer_note_pel_doc_ref")
        assert pointer["pattern"] == migration.PEL_DOC_REF_PATTERN
        assert not any(f["field_type"] in {"file", "image"} for f in fields)
