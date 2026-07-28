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


def model_metadata_summary() -> dict[str, list[str]]:
    """Table names, and which of them require or permit a NULL ``tenant_id``."""
    completed = subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(REPO_ROOT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        raise AssertionError(f"metadata subprocess failed:\nstdout={completed.stdout}\nstderr={completed.stderr}")
    return json.loads(completed.stdout)
