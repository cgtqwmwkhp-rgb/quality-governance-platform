"""Give complaint priority and near-miss potential severity the shared severity set.

Revision ID: 20260911_shared_severity
Revises: 20260910_nm_status_align
Create Date: 2026-09-09

What was wrong
--------------
``severity_levels`` is one admin lookup category filling three differently-named
fields: incident ``severity``, complaint ``priority`` and near-miss
``potential_severity``. The three did not agree. Only incident severity accepted
``negligible``, so choosing it on a complaint or a near miss returned HTTP 422 —
the PX-281/282 shape, recorded as a known write-contract gap rather than fixed
because it needed a product decision.

B-9 is that decision: one shared set of ``critical / high / medium / low /
negligible`` across the three. ``ComplaintPriority`` gains ``negligible`` and the
near-miss request pattern widens; this migration moves the database to match, in
two parts.

Part 1 — the dropdown does not actually offer five options
-----------------------------------------------------------
``lookup_defaults_seed_data`` lists five ``severity_levels`` codes, so a tenant
created through the runtime seeder gets ``negligible``. A tenant built by
``alembic upgrade head`` does not, and neither does production:
``20260827_lookup_tenant_fix`` adopts the pre-existing orphaned rows —
``low``, ``medium``, ``high``, ``critical`` — into the tenant, which leaves the
category non-empty, and ``20260828_lookup_defaults`` only inserts into a category
that has no rows at all. So its five-row block is skipped and ``negligible`` never
lands. Measured on a database at ``20260908_soa_align``: four rows.

That is why widening the enums is not sufficient on its own. This migration
realigns the category to the five codes the same way ``20260831_lookup_enum_align``
realigns ``complaint_types`` and ``incident_types``: missing codes are inserted,
codes that were switched off are switched back on, and codes outside the set are
**deactivated, never deleted** (an administrator may have curated the label, the
row may be another row's ``parent_id``, and the code may appear in stored
``form_submissions`` payloads that still need to resolve to a label). Every row
touched is recorded in a ``system_settings`` ledger so ``downgrade`` reverses
exactly this migration's effect and nothing an administrator has done since.

Part 2 — the CHECK constraints the models declare do not exist
---------------------------------------------------------------
``Complaint`` and ``NearMiss`` declare ``ck_complaints_priority`` and
``ck_nm_severity_values`` in ``__table_args__``, but **no migration has ever
created them**. ``complaints.priority`` was a native ``complaintpriority`` enum
until ``20260118_enum_varchar`` converted it to ``VARCHAR(50)`` and the CHECK was
never added in its place; ``near_misses.potential_severity`` has been a bare
``VARCHAR(20)`` since ``20260121_near_miss_rta``. Only a database built by
``Base.metadata.create_all`` (the SQLite unit-test path) has ever enforced them.

So this is a *widen where present, create where absent* step. Both paths end at
the same predicate, so a database that had the four-value constraint and one that
had nothing agree afterwards, which is the point.

Creating a constraint that was not there before can fail on existing rows, and the
one column where that is plausible is ``near_misses.potential_severity``:
``QuickReportCreate.severity`` is an unvalidated string and the portal wrote it
through verbatim, so a client posting ``severity: "urgent"`` stored ``urgent``.
That intake hole is closed in the same change
(:mod:`src.domain.services.shared_severity`), but rows written before it are not
rewritten here. This migration counts them and **raises**, naming the offending
values. Skipping with a warning would leave the models declaring a constraint the
database does not have — the drift ``tests/unit/test_migration_schema_drift_lint``
exists to stop — and a refusal that names the rows is something an operator can
act on.

Not in scope
------------
``near_misses.priority`` (``ck_near_misses_priority``, four uppercase values) is a
workflow queue, not a severity, and keeps its own scale; ``RTASeverity`` is an
injury-outcome scale derived from reported harm; audit finding grading is a
separate taxonomy; ``CAPAPriority`` is a native PostgreSQL enum type describing
action urgency and is not fed by ``severity_levels``. None of them changes here.
``ck_incidents_severity`` is also absent from migrated databases, but incident
severity already accepts all five values, so adding it is a separate repair rather
than part of this decision.

Reversibility
-------------
``downgrade`` reverses the lookup rows through the ledger and then drops both
constraints, rather than restoring a four-value version of them, because on every
alembic-built database absent *is* the previous state. A narrower constraint would
also refuse to apply wherever a ``negligible`` row had since been written, which is
a rollback failing over data the newer version was right to accept.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260911_shared_severity"
down_revision = "20260910_nm_status_align"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

#: The shared set, in ``IncidentSeverity`` declaration order. Kept inline so the
#: migration stays self-contained if ``src/domain/models`` moves, and pinned to the
#: enum by ``tests/unit/test_shared_severity_set.py`` so the copy cannot drift.
SHARED_SEVERITY_VALUES: tuple[str, ...] = ("critical", "high", "medium", "low", "negligible")

SEVERITY_CATEGORY = "severity_levels"

#: ``(code, label, display_order)`` for the category, identical to
#: ``lookup_defaults_seed_data`` so a migrated tenant and a freshly seeded one are
#: offered the same dropdown. Held by
#: ``tests/integration/test_lookup_enum_contract.py``.
ENUM_LOOKUP_DEFAULTS: dict[str, tuple[tuple[str, str, int], ...]] = {
    SEVERITY_CATEGORY: (
        ("critical", "Critical", 1),
        ("high", "High", 2),
        ("medium", "Medium", 3),
        ("low", "Low", 4),
        ("negligible", "Negligible", 5),
    ),
}

#: Key of the ``system_settings`` row recording what this migration changed.
REPAIR_LEDGER_KEY = "migration.20260911_shared_severity.applied"

_LEDGER_KEYS = ("inserted", "deactivated", "reactivated")

_VALUE_LIST = ", ".join(f"'{value}'" for value in SHARED_SEVERITY_VALUES)

#: ``(table, column, constraint name, predicate)``. The predicate is what the ORM
#: declares in ``__table_args__``; both tolerate NULL because ``NULL IN (...)``
#: evaluates to unknown and a CHECK passes on unknown.
WIDENED_CONSTRAINTS: tuple[tuple[str, str, str, str], ...] = (
    ("complaints", "priority", "ck_complaints_priority", f"priority IN ({_VALUE_LIST})"),
    (
        "near_misses",
        "potential_severity",
        "ck_nm_severity_values",
        f"potential_severity IN ({_VALUE_LIST}) OR potential_severity IS NULL",
    ),
)


class UnconstrainableSeverityValuesError(RuntimeError):
    """Existing rows hold a severity outside the shared set."""


# ---------------------------------------------------------------------------
# Part 1 — the severity_levels dropdown
# ---------------------------------------------------------------------------


def _tables() -> dict[str, sa.Table]:
    """Minimal Core table definitions, declared locally so the ORM can move."""
    metadata = sa.MetaData()
    tenants = sa.Table("tenants", metadata, sa.Column("id", sa.Integer, primary_key=True))
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
    return {"tenants": tenants, "lookup_options": lookup_options, "system_settings": system_settings}


def _normalise(value: str | None) -> str:
    return (value or "").strip().lower()


def _read_ledger(connection: sa.engine.Connection, tables: dict[str, sa.Table]) -> dict[str, list[int]]:
    """Return previously recorded row ids, tolerating a missing or corrupt row."""
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
                    "20260911_shared_severity (B-9, shared severity set). Used by downgrade() to "
                    "reverse exactly this migration's effect — do not edit."
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


def apply_shared_severity_lookup(connection: sa.engine.Connection) -> dict[str, list[int]]:
    """Make ``severity_levels`` hold exactly the shared set, active, per tenant.

    Repeat-safe: a second call reports empty lists. Only tenant-scoped rows are
    touched — ``list_lookup_options`` filters on the caller's tenant and every real
    user carries one, so a ``tenant_id IS NULL`` row is already invisible to
    everybody (PX-119) and flipping its flags would be churn, not a repair.
    """
    tables = _tables()
    lookup_options = tables["lookup_options"]
    now = datetime.now(timezone.utc)
    defaults = ENUM_LOOKUP_DEFAULTS[SEVERITY_CATEGORY]
    permitted = {code for code, _label, _order in defaults}

    tenant_ids = [
        int(row)
        for row in connection.execute(sa.select(tables["tenants"].c.id).order_by(tables["tenants"].c.id)).scalars()
    ]

    rows = connection.execute(
        sa.select(
            lookup_options.c.id,
            lookup_options.c.tenant_id,
            lookup_options.c.code,
            lookup_options.c.is_active,
        )
        .where(
            lookup_options.c.category == SEVERITY_CATEGORY,
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
                    category=SEVERITY_CATEGORY,
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

    if any(changed[key] for key in _LEDGER_KEYS):
        stored = _read_ledger(connection, tables)
        for key in _LEDGER_KEYS:
            stored[key].extend(changed[key])
        _write_ledger(connection, tables, stored, now)

    return changed


def revert_shared_severity_lookup(connection: sa.engine.Connection) -> dict[str, int]:
    """Reverse exactly what :func:`apply_shared_severity_lookup` did, then clear the ledger."""
    tables = _tables()
    lookup_options = tables["lookup_options"]
    ledger = _read_ledger(connection, tables)
    reverted = {key: 0 for key in _LEDGER_KEYS}

    if ledger["inserted"]:
        # An inserted row may since have become another row's parent; releasing the
        # child first keeps the delete from tripping the self-referential FK.
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


# ---------------------------------------------------------------------------
# Part 2 — the CHECK constraints
# ---------------------------------------------------------------------------


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table: str) -> bool:
    return _inspector().has_table(table)


def _has_constraint(table: str, name: str) -> bool:
    return any(constraint.get("name") == name for constraint in _inspector().get_check_constraints(table))


def _offending_values(table: str, column: str) -> list[tuple[str, int]]:
    """Distinct values in ``column`` the shared set does not contain, with counts.

    Table, column and value list are module constants, not caller input; they are
    interpolated because an identifier cannot be a bind parameter.
    """
    statement = sa.text(
        f"SELECT {column} AS value, COUNT(*) AS row_count FROM {table} "
        f"WHERE {column} IS NOT NULL AND {column} NOT IN ({_VALUE_LIST}) "
        f"GROUP BY {column} ORDER BY {column}"
    )
    rows = op.get_bind().execute(statement).all()
    return [(str(row.value), int(row.row_count)) for row in rows]


def _widen_check_constraints() -> None:
    for table, column, name, predicate in WIDENED_CONSTRAINTS:
        if not _has_table(table):
            logger.warning("shared severity: table %s is absent, skipping %s", table, name)
            continue

        offending = _offending_values(table, column)
        if offending:
            detail = ", ".join(f"{value!r} ({count} row(s))" for value, count in offending)
            raise UnconstrainableSeverityValuesError(
                f"{table}.{column} holds values outside the shared severity set "
                f"({', '.join(SHARED_SEVERITY_VALUES)}): {detail}. "
                f"{name} cannot be created until those rows are corrected — decide what each "
                f"value meant rather than letting this migration guess."
            )

        if _has_constraint(table, name):
            op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, predicate)
        logger.info("shared severity: %s now allows %s", name, ", ".join(SHARED_SEVERITY_VALUES))


def _drop_check_constraints() -> None:
    for table, _column, name, _predicate in WIDENED_CONSTRAINTS:
        if _has_table(table) and _has_constraint(table, name):
            op.drop_constraint(name, table, type_="check")


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        _widen_check_constraints()
    else:
        # SQLite builds its schema from the models, which already carry the widened
        # predicate, and cannot alter a CHECK constraint without a table rebuild.
        logger.info("shared severity: %s is not PostgreSQL, leaving CHECK constraints alone", bind.dialect.name)

    changed = apply_shared_severity_lookup(bind)
    print(
        f"lookup_options[{SEVERITY_CATEGORY}]: inserted {len(changed['inserted'])}, "
        f"deactivated {len(changed['deactivated'])} codes outside the shared set, "
        f"reactivated {len(changed['reactivated'])}"
    )


def downgrade() -> None:
    bind = op.get_bind()
    revert_shared_severity_lookup(bind)
    if bind.dialect.name == "postgresql":
        _drop_check_constraints()
