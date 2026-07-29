"""Query the full model metadata without poisoning this pytest process.

``scripts/ops/run025/_models.load_metadata()`` deliberately imports the same model
modules ``alembic/env.py`` does, because a schema-parity tool that only looks at
part of the schema is worse than none. That import set cannot be brought into a
process that later configures SQLAlchemy mappers: two different classes named
``Role`` end up registered on the same declarative base, so ``configure_mappers()``
raises ``InvalidRequestError: Multiple classes found for path "Role"`` — and it
raises it for *every* mapper in the registry, not just the ambiguous one.

That whole-registry blast radius is the reason for the indirection rather than the
particular defect causing it. A second instance of the same class of problem was
fixed on 2026-07-29: ``src/domain/models/rta_analysis.py`` declared a relationship
against ``Incident.rtas`` that ``Incident`` did not have, and it took 253 unrelated
unit tests down when these tests first imported it in-process. Deleting that model
did not make the import safe, because the ``Role`` ambiguity is independent of it.

Alembic gets away with the import because it never configures mappers. Tests get
to keep both the full metadata and a clean registry by asking a child process.
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
def model_native_enum_types() -> dict[str, dict]:
    """``{postgres type name: {"labels": [...], "columns": [...]}}`` for native enums.

    ``values_callable`` is applied before SQLAlchemy fills ``enums``, so these are
    the strings that reach the database, not the Python member names.
    """
    return _run(_ENUM_SCRIPT)
