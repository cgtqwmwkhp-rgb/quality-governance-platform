"""Report what the models declare, from a subprocess, as JSON.

Not a test module. Run as a script; prints one JSON object on stdout.

Why this is not just an import
------------------------------
The Run026 suites need the full declared schema, which means importing the model
modules ``alembic/env.py`` side-effect-imports — ``rca_tools``, ``kri``,
``workflow_rules`` and thirteen others. Those imports cannot be done inside a
shared pytest session. They register two different classes named ``Role`` on the
same declarative base, so any relationship naming ``"Role"`` becomes ambiguous and
``Base.registry`` cannot configure at all. That is present on ``main``, is not
caused by anything in Run026, and is not this module's to fix or to hide;
``scripts/ops/run025/_models.py`` documents another instance of the same class of
problem (``audit_template.py`` registering a second ``AuditTemplate``).

The consequence is what matters here: ``Base.registry`` is poisoned for the rest
of the process, and the next test that instantiates *any* mapped class anywhere
gets ``InvalidRequestError``. Importing these modules in-process cost 50 unrelated
unit tests before this indirection existed.

A second defect of the same shape was in this list until 2026-07-29:
``rta_analysis.RootCauseAnalysis`` declared a relationship against ``Incident.rtas``
that ``Incident`` did not have. That model has been deleted, which removes one
cause but not the need for the subprocess — the ``Role`` ambiguity alone still
poisons the registry, measured after the deletion rather than assumed.

So the import happens in a subprocess that exits immediately afterwards. The
suites get the full declared schema and the pytest session keeps a clean
registry. The alternative — enumerating only the models the package ``__init__``
re-exports — would silently drop ``capa_items``,
``legacy_key_risk_indicators``, ``sla_configurations`` and ``workflow_rules``,
which are four of the eight tables the Run026 census is about.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Attribution columns ``AuditTrailMixin`` declares.
ATTRIBUTION_COLUMNS: tuple[str, ...] = ("created_by_id", "updated_by_id")


def collect() -> dict[str, Any]:
    """In-process collection. Only safe in a throwaway interpreter."""
    sys.path.insert(0, str(REPO_ROOT))

    from scripts.ops.run025._models import load_metadata

    metadata = load_metadata()

    from src.domain.models.base import AuditTrailMixin
    from src.infrastructure.database import Base

    mixin_tables = sorted(
        mapper.class_.__tablename__ for mapper in Base.registry.mappers if issubclass(mapper.class_, AuditTrailMixin)
    )

    tables: dict[str, Any] = {}
    for name, table in metadata.tables.items():
        tables[name] = {
            "columns": sorted(table.c.keys()),
            "nullable": {column.name: bool(column.nullable) for column in table.c},
            "attribution_references": {
                column_name: sorted(str(fk.target_fullname) for fk in table.c[column_name].foreign_keys)
                for column_name in ATTRIBUTION_COLUMNS
                if column_name in table.c
            },
        }

    return {
        "tables": tables,
        "mixin_tables": mixin_tables,
        "mixin_declares": [column for column in ATTRIBUTION_COLUMNS if hasattr(AuditTrailMixin, column)],
    }


def probe() -> dict[str, Any]:
    """Run :func:`collect` in a subprocess and return its report."""
    environment = {
        **os.environ,
        # The probe reflects declarations only; it must not need, or touch, a
        # database. A SQLite URL keeps settings construction from depending on
        # whatever DSN the calling suite happens to be pointed at.
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "SECRET_KEY": os.environ.get("SECRET_KEY", "run026-model-probe-secret-key-not-used"),
    }
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve())],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "the model probe subprocess failed, so the declared schema is unknown.\n"
            f"stdout:\n{result.stdout[-4000:]}\nstderr:\n{result.stderr[-4000:]}"
        )
    return json.loads(result.stdout)


if __name__ == "__main__":
    print(json.dumps(collect()))
