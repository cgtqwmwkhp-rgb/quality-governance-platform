"""Alembic environment configuration for database migrations."""

import asyncio
import importlib
import json
import os
from pathlib import Path
from logging.config import fileConfig

from alembic.operations import ops as alembic_ops
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from src.core.config import settings

# Import ALL models so autogenerate sees the complete schema.
# The package __init__.py re-exports many models via __all__; side-effect-import the rest
# so Base.metadata matches migrated tables for `alembic check`.
from src.domain.models import *  # noqa: F401,F403

for _metadata_mod in (
    "src.domain.models.audit_log",
    "src.domain.models.auditor_competence",
    "src.domain.models.collaboration",
    "src.domain.models.compliance_automation",
    "src.domain.models.kri",
    "src.domain.models.near_miss",
    "src.domain.models.notification",
    "src.domain.models.pams_cache",
    "src.domain.models.permissions",
    "src.domain.models.policy_acknowledgment",
    "src.domain.models.rca_tools",
    "src.domain.models.token_blacklist",
    "src.domain.models.vehicle_defect",
    "src.domain.models.workflow",
    "src.domain.models.workflow_rules",
    "src.domain.models.ocr_artifact",
    "src.domain.models.failed_task",
):
    importlib.import_module(_metadata_mod)

from src.infrastructure.database import Base

# this is the Alembic Config object
config = context.config

# Override sqlalchemy.url with the value from settings
# For offline mode (migration generation), we need a sync driver URL
db_url = settings.database_url.replace("+asyncpg", "")
if "+aiosqlite" in db_url:
    db_url = db_url.replace("+aiosqlite", "")
config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model's MetaData object for 'autogenerate' support
target_metadata = Base.metadata

# ORM vs migration naming drift and models not yet covered by migrations.
# Excluded from `alembic check` / autogenerate compare until additive migrations land.
# Owner + reason inventory: docs/governance/alembic_check_excluded_tables.md
_ALEMBIC_CHECK_EXCLUDED_TABLES = frozenset(
    {
        # The eight legacy singular ISO27001/ISMS names that used to head this set
        # were removed on 2026-07-29: they are in neither Base.metadata nor the
        # migrated schema, so autogenerate produced no operation for any of them
        # with or without the exclusion. Measured on PostgreSQL 14.20 and 16.14 --
        # see docs/governance/alembic_check_excluded_tables.md.
        #
        # Plural ORM names (no matching table yet or rename pending)
        "access_control_records",
        "business_continuity_plans",
        # controlled_documents / controlled_document_versions: unfiltered — covered by
        # document_control tenancy migrations (20260710+) + TEN2 NOT NULL wave.
        "cross_standard_mappings",
        "document_access_logs",
        "document_approval_actions",
        "document_approval_instances",
        "document_approval_workflows",
        "document_distributions",
        "document_training_links",
        "ims_control_requirement_mappings",
        "ims_controls",
        "ims_objectives",
        "ims_process_maps",
        "ims_requirements",
        "information_assets",
        "information_security_risks",
        "iso27001_controls",
        "management_review_inputs",
        "management_reviews",
        "obsolete_document_records",
        "security_incidents",
        "soa_control_entries",
        "supplier_security_assessments",
        "unified_audit_plans",
        # Junction / config tables present in DB without SQLAlchemy models
        "audit_finding_clause_mapping",
        "audit_section_clause_mapping",
        "escalation_rules_config",
        "risk_audit_mapping",
        "risk_clause_mapping",
        "risk_control_mapping",
        "risk_incident_mapping",
        # ORM table name differs from migrated table (escalation_rules_config in DB)
        "escalation_rules",
    }
)


def include_object(object, name, type_, reflected, compare_to):  # noqa: ARG001
    if type_ == "table" and name in _ALEMBIC_CHECK_EXCLUDED_TABLES:
        return False
    return True


def _filter_upgrade_ops(ops_list: list) -> list:
    kept: list = []
    for op in ops_list:
        if isinstance(op, alembic_ops.ModifyTableOps):
            nested = _filter_upgrade_ops(list(op.ops))
            if nested:
                op.ops = nested
                kept.append(op)
            continue
        if isinstance(op, alembic_ops.CreateForeignKeyOp):
            continue
        if isinstance(op, alembic_ops.DropConstraintOp) and op.constraint_type == "foreignkey":
            continue
        if isinstance(op, alembic_ops.CreateIndexOp):
            continue
        if isinstance(op, alembic_ops.DropIndexOp):
            continue
        if isinstance(op, alembic_ops.AddColumnOp):
            continue
        if isinstance(op, alembic_ops.DropColumnOp):
            continue
        if isinstance(op, alembic_ops.AlterColumnOp):
            continue
        if isinstance(op, alembic_ops.DropConstraintOp) and op.constraint_type == "unique":
            continue
        kept.append(op)
    return kept


def _op_table_name(op) -> str | None:
    """The table an operation belongs to.

    ``table_name`` covers most operations but not ``CreateForeignKeyOp`` /
    ``DropConstraintOp`` built from a foreign key, which carry ``source_table``.
    Reading only ``table_name`` left 103 of the 1060 operations in the published
    inventory with no table recorded against them, so the artifact could not be
    read per table at all — which is the first thing anyone asks of it.
    """
    for attribute in ("table_name", "source_table", "target_table"):
        value = getattr(op, attribute, None)
        if isinstance(value, str) and value:
            return value
        name = getattr(value, "name", None)
        if isinstance(name, str) and name:
            return name
    return None


def _serialize_upgrade_ops(ops_list: list) -> list[dict]:
    """Return a stable, JSON-safe summary of Alembic autogenerate operations."""
    inventory: list[dict] = []
    for op in ops_list:
        entry = {"type": type(op).__name__}
        table_name = _op_table_name(op)
        if table_name:
            entry["table"] = table_name
        constraint_type = getattr(op, "constraint_type", None)
        if constraint_type:
            entry["constraint_type"] = constraint_type
        if isinstance(op, alembic_ops.ModifyTableOps):
            entry["ops"] = _serialize_upgrade_ops(list(op.ops))
        inventory.append(entry)
    return inventory


def _iter_leaf_entries(serialized: list[dict]):
    """Yield ``(table, entry)`` for every operation, descending into ModifyTableOps.

    A nested entry inherits its parent's table when it has none of its own, so
    every operation is attributable even if a future Alembic op type carries the
    table somewhere this module does not know to look.
    """
    for entry in serialized:
        nested = entry.get("ops")
        if nested is None:
            yield entry.get("table"), entry
            continue
        parent_table = entry.get("table")
        for table, leaf in _iter_leaf_entries(nested):
            yield table or parent_table, leaf


def summarize_drift(serialized: list[dict]) -> dict:
    """Count operations by type and by table.

    Exported (rather than private) because
    ``scripts/validate_alembic_drift_ratchet.py`` reads the same shape out of the
    published artifact and must not compute it a second, subtly different way.
    """
    by_operation: dict[str, int] = {}
    by_table: dict[str, dict[str, int]] = {}
    total = 0
    for table, entry in _iter_leaf_entries(serialized):
        op_type = entry["type"]
        total += 1
        by_operation[op_type] = by_operation.get(op_type, 0) + 1
        name = table or "<unattributed>"
        by_table.setdefault(name, {})
        by_table[name][op_type] = by_table[name].get(op_type, 0) + 1
    return {
        "total_operations": total,
        "tables_with_drift": len(by_table),
        "by_operation": dict(sorted(by_operation.items())),
        "by_table": {t: dict(sorted(ops.items())) for t, ops in sorted(by_table.items())},
    }


def _report_drift(before: dict, after: dict) -> None:
    """Print what the filter removed, so a green gate still states its cost.

    Without this the log said only "No new upgrade operations detected", which is
    true of the filtered result and silent about the 1060 operations that produced
    it. A suppression nobody can see stops being a deferral and becomes a blind
    spot.
    """
    suppressed = before["total_operations"] - after["total_operations"]
    print("=== Alembic drift: suppression report ===")
    print(f"operations before filter: {before['total_operations']} across {before['tables_with_drift']} table(s)")
    print(f"operations after filter:  {after['total_operations']} across {after['tables_with_drift']} table(s)")
    print(f"operations suppressed:    {suppressed}")
    for label, summary in (("before filter", before), ("after filter", after)):
        breakdown = ", ".join(f"{k}={v}" for k, v in summary["by_operation"].items()) or "none"
        print(f"  by operation ({label}): {breakdown}")
    add_columns = before["by_operation"].get("AddColumnOp", 0)
    print(
        f"  AddColumnOp before filter: {add_columns} "
        "(a column a model declares that the database lacks makes the whole table "
        "unreadable to a whole-entity ORM load, not just queries naming it)"
    )
    excluded = len(_ALEMBIC_CHECK_EXCLUDED_TABLES)
    print(
        f"  note: {excluded} table(s) are removed from the comparison entirely by "
        "include_object, so no drift of theirs -- including column drift -- appears "
        "in either count above. See docs/governance/alembic_check_excluded_tables.md."
    )


def _write_drift_inventory(before_filter: list, after_filter: list) -> None:
    """Write CI evidence when ALEMBIC_DRIFT_INVENTORY_FILE is configured."""
    inventory_file = os.environ.get("ALEMBIC_DRIFT_INVENTORY_FILE")
    if not inventory_file:
        return
    path = Path(inventory_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "before_filter": before_filter,
                "after_filter": after_filter,
                "summary_before_filter": summarize_drift(before_filter),
                "summary_after_filter": summarize_drift(after_filter),
                "excluded_tables": sorted(_ALEMBIC_CHECK_EXCLUDED_TABLES),
                "filter_enabled": os.environ.get("ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT") == "1",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def process_revision_directives(context, revision, directives):  # noqa: ARG001
    """Filter configured CI drift and emit pre/post-filter operation evidence."""
    if not directives:
        return
    script = directives[0]
    uo = getattr(script, "upgrade_ops", None)
    if uo is None:
        return
    before_filter = _serialize_upgrade_ops(list(uo.ops))
    if os.environ.get("ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT") == "1":
        uo.ops = _filter_upgrade_ops(list(uo.ops))
    after_filter = _serialize_upgrade_ops(list(uo.ops))
    _write_drift_inventory(before_filter, after_filter)
    _report_drift(summarize_drift(before_filter), summarize_drift(after_filter))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        process_revision_directives=process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        process_revision_directives=process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    # Get the config and ensure we have the async driver in the URL
    config_section = config.get_section(config.config_ini_section, {})
    url = config_section.get("sqlalchemy.url", db_url)

    # Ensure async driver is used
    if "sqlite" in url and "+aiosqlite" not in url:
        url = url.replace("sqlite:///", "sqlite+aiosqlite:///")
    elif "postgresql" in url and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://")

    config_section["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
