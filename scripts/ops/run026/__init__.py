"""Run026 ops-park scripts: attribution columns, the schema census, which declared
tables a real database actually has, and the C-27 least-privilege connection
identity for row-level security.

Read-only, like every script under ``scripts/ops/``. Safety primitives are
reused from ``scripts.ops.run021._common`` rather than copied, so there is one
implementation of the ``--apply`` / ``--i-understand-prod`` contract. Nothing in
this package mutates data.

These scripts differ from the Run025 pair in one respect that is the whole
reason they exist: they take the database side of every census from
``information_schema`` / ``pg_catalog`` and they do **not** skip
``_ALEMBIC_CHECK_EXCLUDED_TABLES``. See
``scripts/ops/run026/audit_attribution_schema.py`` for why that matters.

``rls_role_readiness.py`` is the preflight for switching the application's
database role from one holding ``rolbypassrls`` to ``qgp_app``, which is what
makes the 21 existing RLS policies take effect at all.
"""
