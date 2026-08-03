"""Every active lookup option must be a value its API field will accept (PX-281/282).

A lookup category that feeds an enum-validated field is one half of a contract.
The form loads ``lookup_options`` for the category with ``is_active=true`` and
submits the chosen ``code`` verbatim; the API validates that string against a
Python enum. Nothing in the schema, the ORM or CI held those two halves
together, so they drifted: ``complaint_types`` ended up offering ``workmanship``
and only ``workmanship``, which ``ComplaintType`` has never contained, and every
complaint submitted through the UI came back 422. ``incident_types`` carried five
codes with the same defect.

These tests close the drift from both ends:

* ``TestSeedDataIsWithinItsEnum`` and ``TestMigrationDefaultsMatchTheSeed`` are
  pure-data checks — no database, so they run in any suite and fail the moment
  someone adds a code the enum does not have.
* ``TestActiveOptionsAreAcceptedByTheApi`` is the real contract: it seeds the
  defaults, reads the dropdown back through the same endpoint and query string
  the frontend uses, and posts a case for every code it was offered. It is the
  test that would have caught PX-281/282 before a user saw it.
* ``TestTheContractTestHasTeeth`` reproduces the production defect against a
  rogue option, so a future refactor cannot leave these assertions passing
  vacuously.

``severity_levels`` joined the registry in B-9. It is the one category that fills
more than one field — incident ``severity``, complaint ``priority``, near-miss
``potential_severity`` — which is why it waited for the product decision that
those three carry the same five values. The probe below exercises it through
incident severity; the other two bindings are covered statically by write-contract
Guard 3.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Callable

import pytest
import sqlalchemy as sa
from httpx import AsyncClient

from src.domain.services.lookup_defaults_seed import count_active_lookup_options, seed_lookup_defaults
from src.domain.services.lookup_defaults_seed_data import rows_for_category
from src.domain.services.lookup_enum_contract import (
    ENUM_BACKED_CATEGORIES,
    ENUM_BACKED_LOOKUPS,
    EnumBackedLookup,
    rejected_codes,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = REPO_ROOT / "alembic" / "versions"

# The migration that decides what a *migrated* tenant is offered for each
# enum-backed category, and the name of the constant inside it holding those
# defaults as ``(code, label, display_order)``.
#
# ``complaint_types`` and ``incident_types`` are owned by the PX-281/282 repair,
# which reseeded them because their codes were not enum members. ``severity_levels``
# is owned by the B-9 repair, for a different reason: its codes were always valid,
# but a migrated tenant only ever had four of the five. ``20260827_lookup_tenant_fix``
# adopts the pre-existing orphan rows, which leaves the category non-empty, and
# ``20260828_lookup_defaults`` inserts only into a category with no rows at all — so
# the seed module's ``negligible`` row was skipped on every migrated database.
CATEGORY_DEFAULT_MIGRATIONS: dict[str, tuple[str, str]] = {
    "complaint_types": ("20260831_realign_enum_lookups_and_dedupe_customers.py", "ENUM_LOOKUP_DEFAULTS"),
    "incident_types": ("20260831_realign_enum_lookups_and_dedupe_customers.py", "ENUM_LOOKUP_DEFAULTS"),
    "severity_levels": ("20260911_shared_severity_negligible.py", "ENUM_LOOKUP_DEFAULTS"),
}

TENANT = 1
LOOKUP_ENDPOINT = "/api/v1/admin/config/lookup/{category}"


def _load_migration(filename: str) -> ModuleType:
    """Load a migration by path; ``alembic/versions`` is not a package.

    The repo ships an empty ``alembic/__init__.py`` that shadows the installed
    distribution once the repo root is on ``sys.path``, so ``alembic.op`` is
    stubbed for the load. These tests only read the migration's constants.
    """
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    module_name = f"qgp_migration_{Path(filename).stem}"
    spec = importlib.util.spec_from_file_location(module_name, VERSIONS_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _migration_defaults(category: str) -> tuple[tuple[str, str, int], ...]:
    """The ``(code, label, display_order)`` rows the owning migration installs.

    ``_DEFAULT_ROWS`` is a flat list across categories and ``ENUM_LOOKUP_DEFAULTS``
    is keyed by category; both are normalised to the same shape here so the
    comparison against the seed module is one assertion.
    """
    filename, constant = CATEGORY_DEFAULT_MIGRATIONS[category]
    defaults = getattr(_load_migration(filename), constant)
    if isinstance(defaults, dict):
        return tuple(defaults[category])
    return tuple((code, label, order) for row_category, code, label, order in defaults if row_category == category)


def _recent() -> str:
    """A timestamp in the recent past; the case schemas reject future dates."""
    return (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


def _complaint_payload(code: str) -> dict[str, Any]:
    return {
        "title": f"Lookup contract probe: {code}",
        "description": f"Submitted with the active complaint_types option '{code}'.",
        "complaint_type": code,
        "received_date": _recent(),
        "complainant_name": "Contract Test",
    }


def _incident_payload(code: str) -> dict[str, Any]:
    return {
        "title": f"Lookup contract probe: {code}",
        "description": f"Submitted with the active incident_types option '{code}'.",
        "incident_type": code,
        "incident_date": _recent(),
    }


def _severity_payload(code: str) -> dict[str, Any]:
    """Probe ``severity_levels`` through incident severity, the enum behind it.

    The category also fills complaint ``priority`` and near-miss
    ``potential_severity``; those two are checked against the same set by the
    static write-contract guard (``tests/contract/test_write_contract_guards.py``,
    Guard 3), which reads all three bindings out of the OpenAPI schema.
    """
    return {
        "title": f"Lookup contract probe: severity {code}",
        "description": f"Submitted with the active severity_levels option '{code}'.",
        "incident_type": "other",
        "severity": code,
        "incident_date": _recent(),
    }


# The case endpoint each enum-backed category feeds, and how to build a minimal
# valid create payload for it. Keyed by category so a new entry in
# ENUM_BACKED_LOOKUPS without a probe fails ``test_every_registered_category_is_probed``
# rather than silently going unverified.
CASE_PROBES: dict[str, tuple[str, Callable[[str], dict[str, Any]]]] = {
    "complaint_types": ("/api/v1/complaints/", _complaint_payload),
    "incident_types": ("/api/v1/incidents/", _incident_payload),
    "severity_levels": ("/api/v1/incidents/", _severity_payload),
}


def _ids(lookups: tuple[EnumBackedLookup, ...]) -> list[str]:
    return [lookup.category for lookup in lookups]


@pytest.fixture(params=ENUM_BACKED_LOOKUPS, ids=_ids(ENUM_BACKED_LOOKUPS))
def enum_lookup(request) -> EnumBackedLookup:
    return request.param


class TestSeedDataIsWithinItsEnum:
    """The seeded defaults are the values the form will offer out of the box."""

    def test_every_seeded_code_is_an_enum_member(self, enum_lookup: EnumBackedLookup):
        seeded = [row.code for row in rows_for_category(enum_lookup.category)]
        assert seeded, f"'{enum_lookup.category}' has no defaults, so the dropdown would be empty"

        rejected = rejected_codes(enum_lookup.category, seeded)
        assert rejected == (), (
            f"{enum_lookup.ticket}: seeded '{enum_lookup.category}' codes {list(rejected)} are not members of "
            f"{enum_lookup.enum_class.__name__}, so choosing one returns HTTP 422 on "
            f"'{enum_lookup.request_field}'. Allowed: {list(enum_lookup.allowed_codes)}"
        )

    def test_every_enum_member_is_offered(self, enum_lookup: EnumBackedLookup):
        """The other direction: a member with no option is a value users cannot pick."""
        seeded = {row.code for row in rows_for_category(enum_lookup.category)}
        missing = sorted(set(enum_lookup.allowed_codes) - seeded)
        assert missing == [], (
            f"{enum_lookup.enum_class.__name__} members {missing} have no '{enum_lookup.category}' option, "
            "so no user can submit them"
        )

    def test_codes_are_unique_and_labelled(self, enum_lookup: EnumBackedLookup):
        rows = rows_for_category(enum_lookup.category)
        codes = [row.code for row in rows]
        assert len(codes) == len(set(codes)), f"'{enum_lookup.category}' seeds a duplicate code: {sorted(codes)}"
        assert all(row.label.strip() for row in rows), f"'{enum_lookup.category}' seeds an option with no label"

    def test_every_registered_category_is_probed(self):
        assert set(CASE_PROBES) == set(ENUM_BACKED_CATEGORIES), (
            "every enum-backed lookup category needs a create-payload probe here, otherwise its "
            "contract is registered but never exercised against the API"
        )


class TestMigrationDefaultsMatchTheSeed:
    """Migrations inline the codes; the copy must not drift.

    The invariant is that a tenant whose options came from a migration and a
    tenant freshly seeded by ``lookup_defaults_seed_data`` are offered the same
    dropdown. Which migration installed them differs by category — see
    ``CATEGORY_DEFAULT_MIGRATIONS`` — but the comparison is the same one.
    """

    def test_migration_defaults_are_identical_to_the_seed_module(self, enum_lookup: EnumBackedLookup):
        filename, constant = CATEGORY_DEFAULT_MIGRATIONS[enum_lookup.category]
        inline = _migration_defaults(enum_lookup.category)
        seeded = tuple((row.code, row.label, row.display_order) for row in rows_for_category(enum_lookup.category))
        assert inline == seeded, (
            f"alembic {filename} ({constant}) and lookup_defaults_seed_data disagree about "
            f"'{enum_lookup.category}'; a migrated tenant and a freshly seeded one would offer different options"
        )

    def test_every_enum_backed_category_has_an_owning_migration(self):
        assert set(CATEGORY_DEFAULT_MIGRATIONS) == set(ENUM_BACKED_CATEGORIES), (
            "every enum-backed category needs a migration that installs its defaults, otherwise a tenant "
            "that predates the seed module is offered something nothing checks"
        )


async def _active_codes(client: AsyncClient, category: str) -> list[str]:
    """Read the dropdown exactly as the frontend does: this category, active only."""
    response = await client.get(LOOKUP_ENDPOINT.format(category=category), params={"is_active": "true"})
    assert response.status_code == 200, response.text
    return [item["code"] for item in response.json()["items"]]


async def _rejected_by_the_api(client: AsyncClient, category: str, codes: list[str]) -> dict[str, str]:
    """Post a case per code; return the codes the API refused and why."""
    endpoint, build_payload = CASE_PROBES[category]
    refused: dict[str, str] = {}
    for code in codes:
        response = await client.post(endpoint, json=build_payload(code))
        if response.status_code != 201:
            refused[code] = f"HTTP {response.status_code}: {response.text[:300]}"
    return refused


@pytest.fixture
async def seeded_lookups(test_session):
    """Guarantee the tenant has its lookup defaults, however it got them.

    Seeding is insert-only-when-empty, so this is a no-op on a database CI has
    already run ``alembic upgrade head`` against — there the options come from
    the migrations instead, which is the stronger check of the two. On a fresh
    schema (``create_all``, no migrations) it does the seeding itself. Either
    way the postcondition is what the tests need, so that is what is asserted.
    """
    await seed_lookup_defaults(test_session, tenant_id=TENANT)

    for lookup in ENUM_BACKED_LOOKUPS:
        active = await count_active_lookup_options(test_session, tenant_id=TENANT, category=lookup.category)
        assert active, (
            f"'{lookup.category}' has no active option for tenant {TENANT}, so the "
            f"'{lookup.request_field}' select would render empty"
        )


@pytest.fixture
async def rogue_complaint_type(test_session):
    """Add the option production actually offered, and take it away again.

    The integration schema is shared on Postgres, so leaving an invalid active
    option behind would break whichever sibling test ran next — and would be a
    dishonest thing for a test about invalid options to do.
    """
    from src.domain.models.form_config import LookupOption

    option = LookupOption(
        tenant_id=TENANT,
        category="complaint_types",
        code="workmanship",
        label="Workmanship / repair defect",
        is_active=True,
        display_order=99,
    )
    test_session.add(option)
    await test_session.commit()
    option_id = option.id
    try:
        yield option
    finally:
        await test_session.execute(sa.delete(LookupOption).where(LookupOption.id == option_id))
        await test_session.commit()


class TestActiveOptionsAreAcceptedByTheApi:
    """PX-281/282 — the form may only offer values the API will take."""

    async def test_every_active_option_is_accepted(
        self,
        admin_client: AsyncClient,
        seeded_lookups,
        enum_lookup: EnumBackedLookup,
    ):
        codes = await _active_codes(admin_client, enum_lookup.category)
        assert codes, (
            f"'{enum_lookup.category}' served no active options, so the "
            f"'{enum_lookup.request_field}' select would be empty"
        )

        refused = await _rejected_by_the_api(admin_client, enum_lookup.category, codes)
        assert refused == {}, (
            f"{enum_lookup.ticket}: the {enum_lookup.category} dropdown offers values the API rejects on "
            f"'{enum_lookup.request_field}' — {refused}"
        )

    async def test_the_offered_options_are_exactly_the_enum(
        self,
        admin_client: AsyncClient,
        seeded_lookups,
        enum_lookup: EnumBackedLookup,
    ):
        codes = await _active_codes(admin_client, enum_lookup.category)
        assert sorted(codes) == sorted(enum_lookup.allowed_codes)


class TestTheContractTestHasTeeth:
    """Reproduce PX-281 so these assertions cannot pass for the wrong reason."""

    async def test_a_rogue_active_option_is_detected(
        self,
        admin_client: AsyncClient,
        seeded_lookups,
        rogue_complaint_type,
    ):
        """'workmanship' is what production actually offered; the API 422s on it."""
        codes = await _active_codes(admin_client, "complaint_types")
        assert "workmanship" in codes

        refused = await _rejected_by_the_api(admin_client, "complaint_types", codes)
        assert list(refused) == ["workmanship"], refused
        assert "422" in refused["workmanship"]

        assert rejected_codes("complaint_types", codes) == ("workmanship",)

    def test_a_free_form_category_constrains_nothing(self):
        """Only registered categories are contracts; customers stays free-form."""
        assert rejected_codes("customers", ["thames_water", "anything"]) == ()

    async def test_admin_cannot_create_a_rogue_enum_backed_code(
        self,
        superuser_client: AsyncClient,
        seeded_lookups,
    ):
        """R22-03 — admin write path must refuse the PX-281 shape before it lands.

        Uses ``superuser_client`` so auth clears ``form:create`` and the
        assertion measures the enum guard (422), not RBAC (403).
        """
        response = await superuser_client.post(
            LOOKUP_ENDPOINT.format(category="complaint_types"),
            json={
                "code": "workmanship",
                "label": "Workmanship / repair defect",
                "is_active": True,
                "display_order": 99,
            },
        )
        assert response.status_code == 422, response.text
        assert "workmanship" in response.text

        codes = await _active_codes(superuser_client, "complaint_types")
        assert "workmanship" not in codes
