"""Query the full model metadata without poisoning this pytest process.

``scripts/ops/run025/_models.load_metadata()`` deliberately imports the same model
modules ``alembic/env.py`` does, because a schema-parity tool that only looks at
part of the schema is worse than none. One of those modules cannot be imported
into a process that later configures SQLAlchemy mappers:
``src/domain/models/rta_analysis.py`` declares
``RootCauseAnalysis.incident = relationship("Incident", back_populates="rtas")``,
but ``Incident`` has no ``rtas`` attribute — its table was dropped back in
``20260105_220237`` (``drop_root_cause_analyses_table``) and the model was left
behind. Importing it makes ``configure_mappers()`` raise for *every* mapper in the
registry, which took 253 unrelated unit tests down with it when these tests first
imported it in-process.

Alembic gets away with it because it never configures mappers, and the app gets
away with it because ``src/domain/models/__init__.py`` does not re-export the
module. Tests get to keep both by asking a child process.

The dead model is reported as a follow-up rather than deleted here; removing a
model is not this change's business.
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
