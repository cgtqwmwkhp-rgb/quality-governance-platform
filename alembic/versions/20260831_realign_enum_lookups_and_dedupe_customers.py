"""Realign enum-backed lookup codes and de-duplicate customers.

Three data repairs. None of them changes a schema; all of them change what the
dropdowns offer, which is where the defects live.

1. PX-281/282 — ``complaint_types`` offered codes ``ComplaintType`` does not
   contain. ``Complaints.tsx`` loads ``lookup_options`` for the category with
   ``is_active=true`` and submits the chosen ``code`` verbatim as
   ``complaint_type``, which ``ComplaintCreate`` validates against the enum.
   Production held a single active option, ``workmanship``; the enum has never
   had that member, so ``POST /api/v1/complaints/`` answered 422 to the only
   value the form could produce and no complaint could be raised through the UI
   at all. The seed data itself was wrong: seven of its ten codes
   (``workmanship``, ``service_quality``, ``delay``, ``damage``, ``conduct``,
   ``hse_concern``, ``vehicle_standard``) are not enum members, so a fully
   seeded tenant was broken too, just less obviously.

2. R22-01 — ``incident_types`` has the same defect in the same place:
   ``ill_health``, ``dangerous_occurrence``, ``vehicle_incident``, ``fire`` and
   ``utility_strike`` are not ``IncidentType`` members, and ``near_miss`` is a
   member the lookup never offered.

   The product decision is to reseed the lookups to the enums, not to widen the
   enums, so both categories are brought to exactly their enum's members here.
   Codes that are not enum members are **deactivated, never deleted**: an
   administrator may have curated the label, a row may be some other row's
   ``parent_id``, and the code may appear in stored ``form_submissions`` payloads
   that still need to resolve to a label. Deactivating removes it from every
   dropdown (the frontend asks for ``is_active=true``) while keeping the row
   readable and this migration reversible.

3. R22-02 — the ``customers`` category carries duplicates ("Thames Water" and
   "Plantexpand Ltd" twice each). Beyond the confusing dropdown this is a live
   500: ``contract_resolve.resolve_contract_id_by_code`` selects the customers
   row for a code with ``scalar_one_or_none()``, which raises
   ``MultipleResultsFound`` when two active rows in one tenant share a code.
   Redundant rows are deactivated rather than deleted. Nothing has a foreign key
   to ``lookup_options.id`` except its own ``parent_id``, but cases do not
   reference the lookup at all — they carry ``contract_id`` into ``contracts``,
   and every ``contracts`` row is left untouched, so no existing incident,
   complaint or near miss loses its customer. Where duplicates disagree, the row
   that already has a matching ``contracts`` row wins so the customers →
   contracts bridge keeps resolving; ties break on the lowest id, i.e. the
   oldest row.

Existing case rows are unaffected by all three. ``complaints.complaint_type``
and ``incidents.incident_type`` are ``CaseInsensitiveEnum`` (VARCHAR) columns
holding enum values with no foreign key to ``lookup_options``, and every write
path goes through the Pydantic enum (``incidents`` additionally carries a CHECK
constraint on the eight enum values), so no stored row can hold a code this
migration deactivates.

Every row inserted, deactivated or reactivated is recorded in a
``system_settings`` ledger so ``downgrade()`` reverses exactly this migration's
effect and nothing an administrator has done since.

Revision ID: 20260831_lookup_enum_align
Revises: 20260830_sla_cam_ref
Create Date: 2026-08-31
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260831_lookup_enum_align"
down_revision: Union[str, Sequence[str], None] = "20260830_sla_cam_ref"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Key of the system_settings row that records what this migration changed.
REPAIR_LEDGER_KEY = "migration.20260831_lookup_enum_align.applied"

# (code, label, display_order) per category. Codes are the members of
# ComplaintType / IncidentType; kept inline so the migration stays self-contained
# if src/domain/services moves, and pinned to the enums by
# tests/integration/test_lookup_enum_contract.py so the copy cannot drift.
ENUM_LOOKUP_DEFAULTS: dict[str, tuple[tuple[str, str, int], ...]] = {
    "complaint_types": (
        ("service", "Service or workmanship", 1),
        ("product", "Product, plant or materials supplied", 2),
        ("delivery", "Delivery, delay or missed appointment", 3),
        ("communication", "Communication or updates", 4),
        ("billing", "Billing or invoicing", 5),
        ("staff", "Staff conduct or behaviour", 6),
        ("safety", "Health and safety concern", 7),
        ("environmental", "Environmental (noise, spill, waste)", 8),
        ("other", "Other", 9),
    ),
    "incident_types": (
        ("injury", "Injury / accident", 1),
        ("near_miss", "Near miss / close call", 2),
        ("hazard", "Hazard / unsafe condition", 3),
        ("property_damage", "Property, plant or vehicle damage", 4),
        ("environmental", "Environmental (spill, leak, emission)", 5),
        ("security", "Security, theft or violence", 6),
        ("quality", "Quality or service failure", 7),
        ("other", "Other", 8),
    ),
}

CUSTOMERS_CATEGORY = "customers"


def _tables() -> dict[str, sa.Table]:
    """Minimal Core table definitions.

    Declared locally rather than imported from ``src.domain.models`` so the
    migration keeps working if the ORM changes later.
    """
    metadata = sa.MetaData()
    tenants = sa.Table(
        "tenants",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
    )
    lookup_options = sa.Table(
        "lookup_options",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer),
        sa.Column("category", sa.String(50)),
        sa.Column("code", sa.String(50)),
        sa.Column("label", sa.String(200)),
        sa.Column("description", sa.Text),
        sa.Column("is_active", sa.Boolean),
        sa.Column("display_order", sa.Integer),
        sa.Column("parent_id", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    contracts = sa.Table(
        "contracts",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer),
        sa.Column("code", sa.String(50)),
        sa.Column("name", sa.String(200)),
    )
    system_settings = sa.Table(
        "system_settings",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer),
        sa.Column("key", sa.String(100)),
        sa.Column("value", sa.Text),
        sa.Column("category", sa.String(50)),
        sa.Column("description", sa.Text),
        sa.Column("value_type", sa.String(20)),
        sa.Column("is_public", sa.Boolean),
        sa.Column("is_editable", sa.Boolean),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    return {
        "tenants": tenants,
        "lookup_options": lookup_options,
        "contracts": contracts,
        "system_settings": system_settings,
    }


_LEDGER_KEYS = ("inserted", "deactivated", "reactivated")


def _normalise(value: str | None) -> str:
    return (value or "").strip().lower()


def _read_ledger(connection: sa.engine.Connection, tables: dict[str, sa.Table]) -> dict[str, list[int]]:
    """Return previously recorded row ids, tolerating a missing/corrupt row."""
    settings_table = tables["system_settings"]
    raw = connection.execute(
        sa.select(settings_table.c.value).where(settings_table.c.key == REPAIR_LEDGER_KEY)
    ).scalar_one_or_none()
    empty: dict[str, list[int]] = {key: [] for key in _LEDGER_KEYS}
    if not raw:
        return empty
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return empty
    if not isinstance(parsed, dict):
        return empty
    return {key: [int(i) for i in parsed.get(key, []) if isinstance(i, int)] for key in _LEDGER_KEYS}


def _write_ledger(
    connection: sa.engine.Connection,
    tables: dict[str, sa.Table],
    ledger: dict[str, list[int]],
    now: datetime,
) -> None:
    settings_table = tables["system_settings"]
    payload = json.dumps({key: sorted(set(ledger[key])) for key in _LEDGER_KEYS}, sort_keys=True)
    existing = connection.execute(
        sa.select(settings_table.c.id).where(settings_table.c.key == REPAIR_LEDGER_KEY)
    ).scalar_one_or_none()
    if existing is None:
        connection.execute(
            settings_table.insert().values(
                tenant_id=None,
                key=REPAIR_LEDGER_KEY,
                value=payload,
                category="migration",
                description=(
                    "Lookup option rows inserted, deactivated or reactivated by Alembic revision "
                    "20260831_lookup_enum_align (PX-281, PX-282, R22-01, R22-02). Used by "
                    "downgrade() to reverse exactly this migration's effect — do not edit."
                ),
                value_type="json",
                is_public=False,
                is_editable=False,
                created_at=now,
                updated_at=now,
            )
        )
    else:
        connection.execute(
            settings_table.update().where(settings_table.c.id == existing).values(value=payload, updated_at=now)
        )


def _realign_enum_category(
    connection: sa.engine.Connection,
    tables: dict[str, sa.Table],
    category: str,
    tenant_ids: list[int],
    now: datetime,
) -> dict[str, list[int]]:
    """Make ``category`` hold exactly its enum's codes, active, for every tenant.

    Only tenant-scoped rows are touched. ``list_lookup_options`` filters
    ``tenant_id == current_user.tenant_id`` and every real user carries a
    non-NULL tenant, so a ``tenant_id IS NULL`` row is already invisible to every
    caller (PX-119) — flipping its flags would churn rows nobody can see.
    """
    lookup_options = tables["lookup_options"]
    defaults = ENUM_LOOKUP_DEFAULTS[category]
    permitted = {code for code, _label, _order in defaults}

    rows = connection.execute(
        sa.select(
            lookup_options.c.id,
            lookup_options.c.tenant_id,
            lookup_options.c.code,
            lookup_options.c.is_active,
        )
        .where(
            lookup_options.c.category == category,
            lookup_options.c.tenant_id.is_not(None),
        )
        .order_by(lookup_options.c.id)
    ).all()

    changed: dict[str, list[int]] = {key: [] for key in _LEDGER_KEYS}
    present: set[tuple[int, str]] = set()

    for row in rows:
        code = _normalise(row.code)
        present.add((int(row.tenant_id), code))
        if code in permitted:
            if not row.is_active:
                changed["reactivated"].append(int(row.id))
        elif row.is_active:
            changed["deactivated"].append(int(row.id))

    for ids, value in ((changed["reactivated"], True), (changed["deactivated"], False)):
        if ids:
            connection.execute(
                lookup_options.update().where(lookup_options.c.id.in_(ids)).values(is_active=value, updated_at=now)
            )

    for tenant_id in tenant_ids:
        for code, label, display_order in defaults:
            if (tenant_id, code) in present:
                continue
            inserted_id = connection.execute(
                lookup_options.insert().values(
                    tenant_id=tenant_id,
                    category=category,
                    code=code,
                    label=label,
                    description=None,
                    is_active=True,
                    display_order=display_order,
                    parent_id=None,
                    created_at=now,
                    updated_at=now,
                )
            ).inserted_primary_key[0]
            changed["inserted"].append(int(inserted_id))
            present.add((tenant_id, code))

    return changed


def _dedupe_customers(
    connection: sa.engine.Connection,
    tables: dict[str, sa.Table],
    now: datetime,
) -> list[int]:
    """Deactivate redundant ``customers`` rows, keeping one per code and per name.

    Two passes, because production carries both shapes: the same code twice, and
    the same customer name under two different codes. Within a group the keeper
    is the row that already has a ``contracts`` row for its code — that is the
    row ``resolve_contract_id_by_code`` can turn into a ``contract_id`` without
    creating anything — and otherwise the lowest id, i.e. the oldest.
    """
    lookup_options = tables["lookup_options"]
    contracts = tables["contracts"]

    contract_codes = {
        (int(row.tenant_id), _normalise(row.code))
        for row in connection.execute(
            sa.select(contracts.c.tenant_id, contracts.c.code).where(contracts.c.tenant_id.is_not(None))
        ).all()
    }

    deactivated: list[int] = []

    def _prune(key_of) -> None:
        rows = connection.execute(
            sa.select(
                lookup_options.c.id,
                lookup_options.c.tenant_id,
                lookup_options.c.code,
                lookup_options.c.label,
            )
            .where(
                lookup_options.c.category == CUSTOMERS_CATEGORY,
                lookup_options.c.tenant_id.is_not(None),
                lookup_options.c.is_active.is_(True),
            )
            .order_by(lookup_options.c.id)
        ).all()

        groups: dict[tuple[int, str], list[Any]] = {}
        for row in rows:
            key = key_of(row)
            if not key[1]:
                continue
            groups.setdefault(key, []).append(row)

        redundant: list[int] = []
        for (tenant_id, _value), group in sorted(groups.items()):
            if len(group) < 2:
                continue
            ranked = sorted(
                group,
                key=lambda row: (
                    (int(row.tenant_id), _normalise(row.code)) not in contract_codes,
                    int(row.id),
                ),
            )
            redundant.extend(int(row.id) for row in ranked[1:])

        if redundant:
            connection.execute(
                lookup_options.update()
                .where(lookup_options.c.id.in_(redundant))
                .values(is_active=False, updated_at=now)
            )
            deactivated.extend(redundant)

    _prune(lambda row: (int(row.tenant_id), _normalise(row.code)))
    _prune(lambda row: (int(row.tenant_id), _normalise(row.label)))

    return deactivated


def apply_lookup_taxonomy_repair(connection: sa.engine.Connection) -> dict[str, Any]:
    """Realign the enum-backed categories and de-duplicate customers. Repeat-safe.

    Returns what *this* call changed: per-category inserted / deactivated /
    reactivated ids, and the redundant customer rows deactivated. A repeat run
    reports empty lists.
    """
    tables = _tables()
    now = datetime.now(timezone.utc)

    tenant_ids = [
        int(row)
        for row in connection.execute(sa.select(tables["tenants"].c.id).order_by(tables["tenants"].c.id)).scalars()
    ]

    per_category: dict[str, dict[str, list[int]]] = {}
    ledger: dict[str, list[int]] = {key: [] for key in _LEDGER_KEYS}

    for category in sorted(ENUM_LOOKUP_DEFAULTS):
        changed = _realign_enum_category(connection, tables, category, tenant_ids, now)
        per_category[category] = changed
        for key in _LEDGER_KEYS:
            ledger[key].extend(changed[key])

    duplicate_customers = _dedupe_customers(connection, tables, now)
    ledger["deactivated"].extend(duplicate_customers)

    if any(ledger[key] for key in _LEDGER_KEYS):
        stored = _read_ledger(connection, tables)
        for key in _LEDGER_KEYS:
            stored[key].extend(ledger[key])
        _write_ledger(connection, tables, stored, now)

    return {"per_category": per_category, "duplicate_customers": duplicate_customers}


def revert_lookup_taxonomy_repair(connection: sa.engine.Connection) -> dict[str, int]:
    """Reverse exactly what ``apply_lookup_taxonomy_repair`` did, then clear the ledger.

    Rows this migration inserted are deleted; rows it only flagged have their
    flag put back. Rows it never touched are left alone, so an administrator's
    own edits since the upgrade survive the rollback.
    """
    tables = _tables()
    lookup_options = tables["lookup_options"]
    ledger = _read_ledger(connection, tables)
    reverted = {key: 0 for key in _LEDGER_KEYS}

    if ledger["inserted"]:
        # An inserted row may since have become another row's parent; releasing
        # the child first keeps the delete from tripping the self-referential FK.
        connection.execute(
            lookup_options.update().where(lookup_options.c.parent_id.in_(ledger["inserted"])).values(parent_id=None)
        )
        result = connection.execute(lookup_options.delete().where(lookup_options.c.id.in_(ledger["inserted"])))
        reverted["inserted"] = result.rowcount or 0

    for key, restore_to in (("deactivated", True), ("reactivated", False)):
        if ledger[key]:
            result = connection.execute(
                lookup_options.update().where(lookup_options.c.id.in_(ledger[key])).values(is_active=restore_to)
            )
            reverted[key] = result.rowcount or 0

    connection.execute(tables["system_settings"].delete().where(tables["system_settings"].c.key == REPAIR_LEDGER_KEY))
    return reverted


def upgrade() -> None:
    report = apply_lookup_taxonomy_repair(op.get_bind())
    for category, changed in sorted(report["per_category"].items()):
        print(
            f"lookup_options[{category}]: inserted {len(changed['inserted'])}, "
            f"deactivated {len(changed['deactivated'])} non-enum codes, "
            f"reactivated {len(changed['reactivated'])}"
        )
    print(f"lookup_options[customers]: deactivated {len(report['duplicate_customers'])} redundant rows")


def downgrade() -> None:
    revert_lookup_taxonomy_repair(op.get_bind())
