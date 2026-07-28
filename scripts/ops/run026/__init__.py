"""Run026 ops-park scripts: attribution columns and the schema census.

Read-only, like every script under ``scripts/ops/``. Safety primitives are
reused from ``scripts.ops.run021._common``.

These scripts differ from the Run025 pair in one respect that is the whole
reason they exist: they take the database side of every census from
``information_schema`` / ``pg_catalog`` and they do **not** skip
``_ALEMBIC_CHECK_EXCLUDED_TABLES``. See
``scripts/ops/run026/audit_attribution_schema.py`` for why that matters.
"""
