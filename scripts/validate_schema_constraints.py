#!/usr/bin/env python3
"""Validate SQLAlchemy ORM models under ``src.domain.models``.

Imports the public model package, then for each mapped class with ``__tablename__``:

* **Critical:** at least one primary key column.
* **Advisory:** every non-PK foreign-key column should be indexed (column flag,
  ``unique``, or part of a table :class:`~sqlalchemy.schema.Index`).
* **Advisory:** ``String`` columns should declare a max length (no unbounded
  :class:`~sqlalchemy.String`).
* **Advisory:** table name should be ``snake_case`` (lowercase letters, digits,
  underscores only; leading letter).

Exit code ``1`` if any **critical** issue is found. Advisory issues are printed
but do not change the exit code.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _is_snake_case_table(name: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_]*", name))


def _fk_column_indexed(column: Any, table: Any) -> bool:
    if column.primary_key:
        return True
    if column.index or column.unique:
        return True
    for idx in table.indexes:
        if column in idx.columns:
            return True
    return False


def _is_unbounded_string(type_engine: Any) -> bool:
    """True if this is a plain String with no length (ignores Text and enums)."""
    from sqlalchemy import String
    from sqlalchemy.sql.type_api import TypeDecorator

    t = type_engine
    visited = 0
    while isinstance(t, TypeDecorator) and visited < 8:
        visited += 1
        if getattr(t, "length", None) is not None:
            return False
        inner = t.impl
        if isinstance(inner, type):
            return False
        t = inner
    return isinstance(t, String) and getattr(t, "length", None) is None


def _collect_models() -> list[type]:
    import inspect

    import src.domain.models as models_pkg

    out: list[type] = []
    names = getattr(models_pkg, "__all__", [])
    for name in names:
        obj = getattr(models_pkg, name, None)
        if not inspect.isclass(obj):
            continue
        tablename = getattr(obj, "__tablename__", None)
        if tablename is None:
            continue
        table = getattr(obj, "__table__", None)
        if table is None:
            continue
        out.append(obj)
    return out


def _audit_model(model_cls: type) -> tuple[list[str], list[str]]:
    critical: list[str] = []
    advisory: list[str] = []

    table = model_cls.__table__
    tablename = model_cls.__tablename__

    pks = list(table.primary_key.columns)
    if not pks:
        critical.append("no primary key columns")

    if not _is_snake_case_table(tablename):
        advisory.append(
            f"table name {tablename!r} should be snake_case "
            "(lowercase start, only a-z, 0-9, _)",
        )

    for col in table.columns:
        if col.foreign_keys and not _fk_column_indexed(col, table):
            advisory.append(
                f"column {col.name!r} has ForeignKey but no index "
                "(set index=True, unique=True, or add Index)",
            )
        if _is_unbounded_string(col.type):
            advisory.append(
                f"column {col.name!r} uses String() without a max length",
            )

    return critical, advisory


def main() -> int:
    # Import triggers model registration
    importlib.import_module("src.domain.models")

    models = _collect_models()
    any_critical = False

    for cls in sorted(models, key=lambda c: c.__name__):
        critical, advisory = _audit_model(cls)
        if not critical and not advisory:
            continue
        print(f"\n[{cls.__name__}] __tablename__={cls.__tablename__!r}")
        for msg in critical:
            print(f"  CRITICAL: {msg}")
        for msg in advisory:
            print(f"  advisory: {msg}")
        if critical:
            any_critical = True

    if any_critical:
        print("\nValidation finished with CRITICAL violations.", file=sys.stderr)
        return 1

    print(
        f"\nChecked {len(models)} mapped model(s): "
        "no critical violations (see advisory messages above if any).",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
