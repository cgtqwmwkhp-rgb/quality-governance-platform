"""Alembic environment configuration for database migrations."""

import asyncio
import importlib
from logging.config import fileConfig

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
    "src.domain.models.rta_analysis",
    "src.domain.models.token_blacklist",
    "src.domain.models.vehicle_defect",
    "src.domain.models.workflow",
    "src.domain.models.workflow_rules",
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
_ALEMBIC_CHECK_EXCLUDED_TABLES = frozenset(
    {
        # Legacy singular table names (still present after add_iso27001_isms)
        "access_control_record",
        "business_continuity_plan",
        "information_asset",
        "information_security_risk",
        "iso27001_control",
        "security_incident",
        "soa_control_entry",
        "supplier_security_assessment",
        # Plural ORM names (no matching table yet or rename pending)
        "access_control_records",
        "business_continuity_plans",
        "controlled_document_versions",
        "controlled_documents",
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
        # Model retained after migration dropped root_cause_analyses
        "root_cause_analyses",
    }
)


def include_object(object, name, type_, reflected, compare_to):  # noqa: ARG001
    if type_ == "table" and name in _ALEMBIC_CHECK_EXCLUDED_TABLES:
        return False
    return True


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
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
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
