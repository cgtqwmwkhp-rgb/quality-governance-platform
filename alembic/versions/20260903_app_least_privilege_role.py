"""Create the least-privilege application role, so the connection identity can
stop bypassing row-level security.

Revision ID: 20260903_app_lp_role
Revises: 20260902_rls_guc_guard
Create Date: 2026-09-03

Why this exists (C-27, part 2 of 2)
-----------------------------------
The application connects as the Azure PostgreSQL administrator login
(``qgpadmin``), which holds ``rolbypassrls``. PostgreSQL skips row-level security
entirely for such a role, so every ``tenant_isolation`` policy on the estate is
inert for the application. This is not a policy defect — the policies are correct.
It is a connection-identity defect.

This migration creates the role the application should connect as instead. It does
**not** change any connection string, and applying it changes nothing about how
the running system behaves. Switching the application over is a separate,
human-authorised step with a hard ordering requirement documented in
docs/governance/rls-least-privilege-rollout.md. Creating the role early means the
grants can be reviewed, verified and drift-checked long before anything depends on
them.

What the role can and cannot do
-------------------------------
``qgp_app`` gets exactly what the request path needs:

* ``CONNECT`` on this database and ``USAGE`` on schema ``public``
* ``SELECT, INSERT, UPDATE, DELETE`` on every table in ``public``
* ``USAGE, SELECT`` on every sequence in ``public`` (``nextval`` for SERIAL keys)
* the same, by default, on tables and sequences created by future migrations

It explicitly does not get ``BYPASSRLS``, ``SUPERUSER``, ``CREATEDB``,
``CREATEROLE``, ``REPLICATION``, ``TRUNCATE``, ``REFERENCES``, ``TRIGGER``, or
``CREATE`` on the schema. ``TRUNCATE`` is withheld because it is not RLS-aware:
PostgreSQL has no per-row TRUNCATE check, so a role holding it can empty a
tenant-scoped table across every tenant. Nothing in ``src/`` issues TRUNCATE.

It is created ``NOLOGIN`` and with no password. A migration in version control is
the wrong place for a credential, and a role with LOGIN and a NULL password cannot
authenticate under SCRAM anyway, so this is not a usable identity until an
operator runs the ``ALTER ROLE`` in the runbook against a secret from Key Vault.
Creating it locked is the safe default: the grants can be inspected without a
credential existing anywhere.

Why migrations keep the privileged role
---------------------------------------
Migrations continue to run as the existing administrator credential, unchanged.
This is not laziness:

* ``20260901_case_tenant_nn`` already *refuses to run* on a role without
  ``rolsuper``/``rolbypassrls``, because ``COUNT(*) WHERE tenant_id IS NULL``
  silently returns 0 under FORCE RLS while the ``SET NOT NULL`` heap scan still
  aborts. Data-repair migrations must see every row.
* The chain issues ``CREATE EXTENSION`` (``pg_trgm``) and ``CREATE ROLE``, which
  need privileges no application role should ever hold.
* DDL against a FORCE-RLS table from a non-bypass role is its own hazard: a
  backfill inside ``ALTER TABLE`` sees only rows matching the current GUC.

``qgp_migrations`` (``NOLOGIN BYPASSRLS``, created by
``20260222_add_row_level_security``) already exists for this purpose and is left
as it is. Giving it LOGIN and a password would create a second privileged
credential to rotate and audit while the administrator credential the deploy
workflow already uses keeps working, and it would change the deployment path in
the same change as the RLS switch-on. Those are better separated.

Idempotency and permission failures
-----------------------------------
``CREATE ROLE`` needs ``CREATEROLE`` or superuser. On Azure Flexible Server the
administrator login has this via ``azure_pg_admin``; a developer database owned by
a non-superuser may not. Following ``20260222_add_row_level_security``, the role
creation tolerates a permission failure with a NOTICE rather than blocking the
whole chain — but unlike that migration, the grants are **not** wrapped in a
blanket exception handler, and ``upgrade`` re-reads the catalogue and raises if the
role exists without the privileges it needs. A half-granted role that reports
success is how the earlier RLS expansion lost two tables.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_app_lp_role"
down_revision: Union[str, Sequence[str], None] = "20260902_rls_guc_guard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

APP_ROLE = "qgp_app"

# Table privileges the request path needs, and no more. Compared against
# information_schema.role_table_grants during verification.
REQUIRED_TABLE_PRIVILEGES: tuple[str, ...] = ("SELECT", "INSERT", "UPDATE", "DELETE")

# Privileges that must never be held on a tenant-scoped table. TRUNCATE has no
# per-row RLS check, so it would let the app role empty a table across all
# tenants regardless of tenant_isolation.
FORBIDDEN_TABLE_PRIVILEGES: tuple[str, ...] = ("TRUNCATE", "REFERENCES", "TRIGGER")


def _role_exists(bind: sa.engine.Connection) -> bool:
    return bool(bind.execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE}).scalar())


def _create_role(bind: sa.engine.Connection) -> bool:
    """Create ``qgp_app`` locked down. Returns False when we lack the privilege."""
    if _role_exists(bind):
        logger.info("%s: role %s already exists, leaving its attributes alone", revision, APP_ROLE)
        return True

    # NOLOGIN and no password: this is not a usable credential until an operator
    # runs the ALTER ROLE in the runbook. Every negative attribute is stated
    # explicitly rather than relying on CREATE ROLE defaults, so the intent is
    # readable in the catalogue and in review.
    op.execute(
        sa.text(
            f"DO $$ BEGIN "
            f"  CREATE ROLE {APP_ROLE} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            f"    NOREPLICATION NOBYPASSRLS INHERIT; "
            f"  RAISE NOTICE 'created least-privilege role {APP_ROLE} (NOLOGIN, no password)'; "
            f"EXCEPTION WHEN insufficient_privilege THEN "
            f"  RAISE NOTICE 'cannot create {APP_ROLE}: this connection lacks CREATEROLE. "
            f"Create it manually per the rollout runbook.'; "
            f"END $$"
        )
    )
    return _role_exists(bind)


def _grant(bind: sa.engine.Connection) -> None:
    """Grant the runtime privileges, plus defaults for future migrations' objects."""
    database = bind.execute(sa.text("SELECT current_database()")).scalar()
    privileges = ", ".join(REQUIRED_TABLE_PRIVILEGES)

    op.execute(sa.text(f'GRANT CONNECT ON DATABASE "{database}" TO {APP_ROLE}'))
    op.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
    op.execute(sa.text(f"GRANT {privileges} ON ALL TABLES IN SCHEMA public TO {APP_ROLE}"))
    op.execute(sa.text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}"))

    # Objects created by *future* migrations. ALTER DEFAULT PRIVILEGES is scoped to
    # the creating role, so this only covers objects created by whoever is running
    # migrations now. If the migration identity ever changes, these defaults stop
    # applying and new tables arrive ungranted — which is why the readiness script
    # re-checks every table rather than trusting this.
    creator = bind.execute(sa.text("SELECT current_user")).scalar()
    op.execute(
        sa.text(
            f'ALTER DEFAULT PRIVILEGES FOR ROLE "{creator}" IN SCHEMA public '
            f"GRANT {privileges} ON TABLES TO {APP_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f'ALTER DEFAULT PRIVILEGES FOR ROLE "{creator}" IN SCHEMA public '
            f"GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}"
        )
    )
    # Let the migration/admin identity assume this role via SET ROLE. This grants
    # qgp_app nothing — membership flows the other way — but it is what allows the
    # readiness preflight and the integration tests to exercise the policies as the
    # application role before any password for it exists anywhere. Without it, the
    # only way to test the role is to create a credential, which is precisely what
    # we are trying to defer until the cutover is authorised.
    op.execute(sa.text(f'GRANT {APP_ROLE} TO "{creator}"'))

    logger.info("%s: granted %s on public to %s (default privileges as %s)", revision, privileges, APP_ROLE, creator)


def _assert_role_is_least_privilege(bind: sa.engine.Connection) -> None:
    """Raise unless the role exists, cannot bypass RLS, and can reach every table."""
    attributes = (
        bind.execute(
            sa.text(
                "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication, rolcanlogin "
                "FROM pg_roles WHERE rolname = :r"
            ),
            {"r": APP_ROLE},
        )
        .mappings()
        .first()
    )
    if attributes is None:
        raise RuntimeError(f"{revision}: role {APP_ROLE} does not exist after creation")

    escalations = [
        name
        for name in ("rolsuper", "rolbypassrls", "rolcreatedb", "rolcreaterole", "rolreplication")
        if attributes[name]
    ]
    if escalations:
        raise RuntimeError(
            f"{revision}: role {APP_ROLE} holds {', '.join(escalations)}. "
            f"An application role with any of these defeats the purpose of this migration. "
            f"Revoke them before re-running."
        )

    # Every base table in public must be reachable, or the app 500s on that table
    # the moment it connects as this role. A missing grant here is the single most
    # likely cause of a failed cutover.
    missing = (
        bind.execute(
            sa.text("""
            SELECT t.table_name
            FROM information_schema.tables AS t
            WHERE t.table_schema = 'public'
              AND t.table_type = 'BASE TABLE'
              AND EXISTS (
                    SELECT 1 FROM unnest(CAST(:required AS text[])) AS need(priv)
                    WHERE NOT EXISTS (
                        SELECT 1 FROM information_schema.role_table_grants AS g
                        WHERE g.table_schema = 'public'
                          AND g.table_name = t.table_name
                          AND g.grantee = :role
                          AND g.privilege_type = need.priv
                    )
              )
            ORDER BY t.table_name
            """),
            {"required": list(REQUIRED_TABLE_PRIVILEGES), "role": APP_ROLE},
        )
        .scalars()
        .all()
    )
    if missing:
        raise RuntimeError(
            f"{revision}: {APP_ROLE} is missing one or more of {', '.join(REQUIRED_TABLE_PRIVILEGES)} on "
            f"{len(missing)} table(s): {', '.join(missing[:20])}" + (" …" if len(missing) > 20 else "")
        )

    overreach = (
        bind.execute(
            sa.text("""
            SELECT DISTINCT privilege_type
            FROM information_schema.role_table_grants
            WHERE table_schema = 'public'
              AND grantee = :role
              AND privilege_type = ANY(CAST(:forbidden AS text[]))
            """),
            {"role": APP_ROLE, "forbidden": list(FORBIDDEN_TABLE_PRIVILEGES)},
        )
        .scalars()
        .all()
    )
    if overreach:
        raise RuntimeError(
            f"{revision}: {APP_ROLE} holds {', '.join(sorted(overreach))} on tables in public. "
            f"TRUNCATE in particular has no per-row RLS check and would cross tenant boundaries."
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        logger.info("Skipping %s: roles and RLS are PostgreSQL-only", revision)
        return

    if not _create_role(bind):
        # No role and no privilege to make one. Do not fail the chain — a developer
        # database is still perfectly usable — but do not pretend it worked.
        logger.warning(
            "%s: %s could not be created and does not exist. The application cannot be "
            "switched to a least-privilege role on this database until it is created manually.",
            revision,
            APP_ROLE,
        )
        return

    _grant(bind)
    _assert_role_is_least_privilege(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        logger.info("Skipping %s downgrade: roles and RLS are PostgreSQL-only", revision)
        return

    if not _role_exists(bind):
        logger.info("%s downgrade: %s does not exist, nothing to do", revision, APP_ROLE)
        return

    database = bind.execute(sa.text("SELECT current_database()")).scalar()
    creator = bind.execute(sa.text("SELECT current_user")).scalar()
    privileges = ", ".join(REQUIRED_TABLE_PRIVILEGES)

    # Default privileges must be revoked with the same FOR ROLE clause that granted
    # them, or they linger and re-grant on the next CREATE TABLE.
    op.execute(
        sa.text(
            f'ALTER DEFAULT PRIVILEGES FOR ROLE "{creator}" IN SCHEMA public '
            f"REVOKE {privileges} ON TABLES FROM {APP_ROLE}"
        )
    )
    op.execute(
        sa.text(
            f'ALTER DEFAULT PRIVILEGES FOR ROLE "{creator}" IN SCHEMA public '
            f"REVOKE USAGE, SELECT ON SEQUENCES FROM {APP_ROLE}"
        )
    )
    op.execute(sa.text(f"REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE {privileges} ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}"))
    op.execute(sa.text(f'REVOKE CONNECT ON DATABASE "{database}" FROM {APP_ROLE}'))
    op.execute(sa.text(f'REVOKE {APP_ROLE} FROM "{creator}"'))

    # The role itself is deliberately left in place. DROP ROLE fails while any
    # object depends on it, and on a database where the application is already
    # connected as qgp_app, dropping it mid-rollback would take the app down
    # harder than the migration it is reverting. Removing the role is a runbook
    # step, not a downgrade side effect.
    logger.info(
        "%s downgrade: revoked %s's privileges. The role itself was left in place deliberately.",
        revision,
        APP_ROLE,
    )
