"""Query the full model metadata without poisoning this pytest process.

``scripts/ops/run025/_models.load_metadata()`` deliberately imports the same model
modules ``alembic/env.py`` does, because a schema-parity tool that only looks at
part of the schema is worse than none. Twice, that import set could not be brought
into a process that later configured SQLAlchemy mappers, and both times the cost
was the whole registry rather than the offending mapper:

* ``src/domain/models/rta_analysis.py`` declared a relationship against
  ``Incident.rtas``, which ``Incident`` did not have. It took 253 unrelated unit
  tests down when these tests first imported it in-process. Deleted 2026-07-29.
* two classes named ``Role`` sat on the same declarative base, making every
  ``relationship("Role")`` ambiguous and raising
  ``InvalidRequestError: Multiple classes found for path "Role"``. The ABAC one is
  now ``ABACRole``.

``configure_mappers()`` therefore succeeds on the full import set today, which
``tests/unit/test_model_registry_class_names.py`` asserts through this module so it
cannot quietly stop being true.

The child process is kept even so. It is not compensation for those two defects but
for the shape of them: any future mapper misconfiguration would again fail every
mapper in the registry rather than its own, and this import set deliberately
includes modules the application itself never imports, so pulling it into the
pytest process would change the registry that every later test in the session runs
against. Alembic gets away with the import because it never configures mappers.
Tests get to keep both the full metadata and a clean registry by asking a child.
"""

from __future__ import annotations

import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_SCRIPT = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from scripts.ops.run025._models import load_metadata, tenant_required_tables

metadata = load_metadata()
print(json.dumps({
    "tables": sorted(metadata.tables),
    "tenant_required": tenant_required_tables(),
    "tenant_nullable": sorted(
        name for name, table in metadata.tables.items()
        if "tenant_id" in table.c and table.c["tenant_id"].nullable
    ),
}))
"""


_ENUM_SCRIPT = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import sqlalchemy as sa
from scripts.ops.run025._models import load_metadata

types = {}
for table_name, table in load_metadata().tables.items():
    for column in table.c:
        column_type = column.type
        if isinstance(column_type, sa.Enum) and column_type.native_enum and column_type.name:
            entry = types.setdefault(column_type.name, {"labels": list(column_type.enums), "columns": []})
            entry["columns"].append(f"{table_name}.{column.name}")
print(json.dumps(types))
"""


_CLASS_NAME_SCRIPT = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from scripts.ops.run025._models import load_metadata

load_metadata()
from src.infrastructure.database import Base

names = {}
for mapper in Base.registry.mappers:
    cls = mapper.class_
    names.setdefault(cls.__name__, []).append(f"{cls.__module__}.{cls.__name__} -> {cls.__tablename__}")
print(json.dumps(names))
"""


_CONFIGURE_SCRIPT = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from scripts.ops.run025._models import load_metadata

load_metadata()
import sqlalchemy.orm

try:
    sqlalchemy.orm.configure_mappers()
except Exception as exc:
    print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
else:
    print(json.dumps({"ok": True, "error": None}))
"""


# Every model module on disk, not only the ones ``alembic/env.py`` reaches. A
# collision needs both classes in one registry to hurt, so a module nothing
# imports carries the same defect in a dormant state -- which is what
# ``audit_template.py`` was until it was deleted for C-70. ``pkgutil`` is the
# right instrument precisely because it does not care what imports what.
#
# Import failures are collected rather than raised: a module that cannot be
# imported contributes no classes, so silently swallowing the error would make
# the duplicate-name sweep quietly narrower than it claims to be.
_ON_DISK_MODEL_SWEEP_SCRIPT = r"""
import importlib, json, pkgutil, sys
sys.path.insert(0, sys.argv[1])
import src.domain.models as package

unimportable = {}
for module in pkgutil.iter_modules(package.__path__):
    name = f"src.domain.models.{module.name}"
    try:
        importlib.import_module(name)
    except Exception as exc:
        unimportable[name] = f"{type(exc).__name__}: {exc}"

from src.infrastructure.database import Base

names = {}
for mapper in Base.registry.mappers:
    cls = mapper.class_
    names.setdefault(cls.__name__, []).append(f"{cls.__module__}.{cls.__name__} -> {cls.__tablename__}")

import sqlalchemy.orm

try:
    sqlalchemy.orm.configure_mappers()
except Exception as exc:
    configured = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
else:
    configured = {"ok": True, "error": None}

print(json.dumps({"names": names, "unimportable": unimportable, "configured": configured}))
"""


def _run(script: str) -> dict:
    completed = subprocess.run(
        [sys.executable, "-c", script, str(REPO_ROOT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        raise AssertionError(f"metadata subprocess failed:\nstdout={completed.stdout}\nstderr={completed.stderr}")
    return json.loads(completed.stdout)


def model_metadata_summary() -> dict[str, list[str]]:
    """Table names, and which of them require or permit a NULL ``tenant_id``."""
    return _run(_SCRIPT)


@lru_cache(maxsize=1)
def model_configure_mappers_result() -> dict:
    """``{"ok": bool, "error": str | None}`` from configuring the full model set.

    Deliberately reports the failure rather than raising it, so a test can name the
    cause in its assertion message instead of surfacing a subprocess crash.
    """
    return _run(_CONFIGURE_SCRIPT)


@lru_cache(maxsize=1)
def model_mapped_class_names() -> dict[str, list[str]]:
    """``{class name: ["module.Class -> table", ...]}`` for every mapped class.

    Reads ``registry.mappers`` rather than configuring them, so it reports the
    registry's contents even while some unrelated mapper is misconfigured.
    """
    return _run(_CLASS_NAME_SCRIPT)


@lru_cache(maxsize=1)
def on_disk_model_sweep() -> dict:
    """Mapped class names, import failures and mapper state for every model file.

    ``{"names": {class name: ["module.Class -> table", ...]},
       "unimportable": {module: "Error: message"},
       "configured": {"ok": bool, "error": str | None}}``

    Strictly wider than :func:`model_mapped_class_names`, which sees only the
    modules ``alembic/env.py`` imports. The child process matters more here than
    anywhere else in this module: this sweep deliberately imports model files the
    application never does, so doing it in-process would put classes in the
    registry that the rest of the session is entitled to assume are absent.
    """
    return _run(_ON_DISK_MODEL_SWEEP_SCRIPT)


@lru_cache(maxsize=1)
def model_native_enum_types() -> dict[str, dict]:
    """``{postgres type name: {"labels": [...], "columns": [...]}}`` for native enums.

    ``values_callable`` is applied before SQLAlchemy fills ``enums``, so these are
    the strings that reach the database, not the Python member names.
    """
    return _run(_ENUM_SCRIPT)
