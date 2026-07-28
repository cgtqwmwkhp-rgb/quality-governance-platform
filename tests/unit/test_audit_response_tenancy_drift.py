"""Why `alembic check` stays green while this model declaration has no migration.

Declaring ``audit_responses.tenant_id`` as ``nullable=False`` with a foreign key
and shipping no migration is deliberate for this step: the database column stays
nullable and the 315 unattributed rows are left alone. It does mean the model and
the migrations disagree, and the drift gate is green only because CI sets
``ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1``, under which
``alembic/env.py::_filter_upgrade_ops`` discards exactly the two operation kinds
this creates — the nullability ``AlterColumnOp`` and the ``CreateForeignKeyOp``.

That dependency is invisible in the diff, so it is recorded here. If the filter
is ever narrowed, this fails and says that this step now needs its migration —
which is the correct response, rather than widening the filter again.

What this does not do is run Alembic: it has no database, and the repo's own
``alembic/`` package shadows the installed one inside the test run. The real
verification is CI's Alembic Migration Drift Check job.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PY = REPO_ROOT / "alembic/env.py"
CI_YML = REPO_ROOT / ".github/workflows/ci.yml"

# Stand-ins for the Alembic operation classes, so the extracted filter can be
# executed on its real branching logic without importing Alembic.
_OP_NAMES = (
    "ModifyTableOps",
    "AlterColumnOp",
    "AddColumnOp",
    "DropColumnOp",
    "CreateForeignKeyOp",
    "CreateIndexOp",
    "DropIndexOp",
    "DropConstraintOp",
    "CreateTableOp",
)


def _fake_ops_namespace() -> SimpleNamespace:
    classes = {}
    for name in _OP_NAMES:
        if name == "ModifyTableOps":

            def __init__(self, table_name, ops):  # noqa: ANN001, ANN202, N807
                self.table_name = table_name
                self.ops = ops

            classes[name] = type(name, (), {"__init__": __init__})
        else:
            classes[name] = type(name, (), {"constraint_type": None})
    return SimpleNamespace(**classes)


def _load_filter(ops_namespace: SimpleNamespace):
    """Execute ``_filter_upgrade_ops`` from env.py without importing env.py.

    Importing it would require an Alembic migration context.
    """
    source = ENV_PY.read_text(encoding="utf-8")
    function = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "_filter_upgrade_ops"
    )
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict = {"alembic_ops": ops_namespace}
    exec(compile(module, str(ENV_PY), "exec"), namespace)
    return namespace["_filter_upgrade_ops"]


def test_the_drift_this_model_change_creates_is_stripped_by_the_ci_filter() -> None:
    ops = _fake_ops_namespace()
    filter_upgrade_ops = _load_filter(ops)

    nullability_change = ops.AlterColumnOp()
    new_foreign_key = ops.CreateForeignKeyOp()

    assert filter_upgrade_ops([nullability_change, new_foreign_key]) == []
    assert filter_upgrade_ops([ops.ModifyTableOps("audit_responses", [nullability_change, new_foreign_key])]) == []


def test_the_filter_still_reports_drift_it_is_not_meant_to_hide() -> None:
    """Otherwise the assertion above would pass for an empty-filter reason."""
    ops = _fake_ops_namespace()
    filter_upgrade_ops = _load_filter(ops)

    missing_table = ops.CreateTableOp()
    kept = filter_upgrade_ops([ops.AlterColumnOp(), missing_table])

    assert kept == [missing_table]


def test_ci_is_what_enables_the_filter() -> None:
    """The filter is opt-in, so the gate's greenness depends on this being set."""
    assert 'ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT: "1"' in CI_YML.read_text(encoding="utf-8")
