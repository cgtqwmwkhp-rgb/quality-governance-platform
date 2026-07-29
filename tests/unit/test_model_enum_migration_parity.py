"""Every native enum label a model declares must be provisioned by a migration.

``CAPASource.VEHICLE_DEFECT`` sat in ``src/domain/models/capa.py`` for the whole
life of the vehicle module without any migration adding ``vehicle_defect`` to the
PostgreSQL ``capasource`` type. PostgreSQL rejects a literal that is not a label
of the target enum while it parses the statement, before it looks at a single
row, so the drift produced a 500 on an empty table from
``GET /api/v1/executive-dashboard/vehicle-governance`` and made
``vehicle_capa_pipeline`` unable to insert at all.

Nothing caught it. ``alembic check`` compares columns, not enum labels;
``scripts/ops/run025/verify_model_schema_parity.py`` compared column presence and
nullability only. Both now cover enums, but both need a database — this test is
the one that runs on every pull request with nothing but the source tree, and it
fails at the moment a member is added to a Python enum without a migration.

How a label counts as provisioned
---------------------------------
Only migration files that name the type are searched, and within them a label
counts when it is either a positional argument of an ``Enum(..., name=<type>)``
call or the quoted value of an ``ALTER TYPE <type> ADD VALUE``. Migrations that
template the label — ``20260302_02_extend_capa_source_enum.py`` loops a tuple
through an f-string — are detected by the ``'{...}'`` placeholder and fall back
to that one file's string constants, so the escape hatch cannot silently widen
to files that do not use it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.unit._tenant_scope_support import model_native_enum_types

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = REPO_ROOT / "alembic/versions"

_ENUM_CALLS = ("Enum", "ENUM")


def _add_value_re(type_name: str) -> re.Pattern[str]:
    return re.compile(
        rf"ALTER\s+TYPE\s+{re.escape(type_name)}\s+ADD\s+VALUE\s+(?:IF\s+NOT\s+EXISTS\s+)?'([^']+)'",
        re.IGNORECASE,
    )


def _docstring_nodes(tree: ast.AST) -> set[int]:
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    return {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, holders)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }


def _sql_strings(tree: ast.AST) -> list[str]:
    """Every non-docstring string literal, with f-string substitutions as ``{}``.

    ``20260302_02_extend_capa_source_enum.py`` builds its statement as
    ``f"ALTER TYPE capasource ADD VALUE IF NOT EXISTS '{val}'"``, which the parser
    sees as a ``JoinedStr`` of fragments — searching plain constants alone would
    never find the statement at all. Docstrings are excluded because prose that
    quotes a label is not a statement that binds one, and every migration here
    describes its own change in prose.
    """
    docstrings = _docstring_nodes(tree)
    out: list[str] = []
    for node in ast.walk(tree):
        if id(node) in docstrings:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            out.append(
                "".join(
                    part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else "{}"
                    for part in node.values
                )
            )
    return out


def _module_string_sequences(tree: ast.AST) -> dict[str, list[str]]:
    """Module-level ``NAME = ("a", "b")`` bindings, for ``Enum(*NAME, name=...)``."""
    out: dict[str, list[str]] = {}
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, (ast.Tuple, ast.List)):
            continue
        values = [e.value for e in node.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if len(values) != len(node.value.elts):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                out[target.id] = values
    return out


def _labels_from_enum_calls(tree: ast.AST, type_name: str) -> set[str]:
    """Positional labels of ``Enum("a", "b", name="<type_name>")`` calls."""
    sequences = _module_string_sequences(tree)
    labels: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name not in _ENUM_CALLS:
            continue
        named = [
            kw.value.value
            for kw in node.keywords
            if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str)
        ]
        if type_name not in named:
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                labels.add(arg.value)
            elif isinstance(arg, ast.Starred) and isinstance(arg.value, ast.Name):
                labels.update(sequences.get(arg.value.id, []))
    return labels


def _provisioned_labels(type_name: str) -> set[str]:
    add_value = _add_value_re(type_name)
    templated = re.compile(
        rf"ALTER\s+TYPE\s+{re.escape(type_name)}\s+ADD\s+VALUE\s+(?:IF\s+NOT\s+EXISTS\s+)?'\{{\}}'",
        re.IGNORECASE,
    )

    labels: set[str] = set()
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if type_name not in source:
            continue
        tree = ast.parse(source)
        statements = _sql_strings(tree)

        labels |= _labels_from_enum_calls(tree, type_name)
        for statement in statements:
            labels.update(add_value.findall(statement))
        if any(templated.search(statement) for statement in statements):
            labels.update(statements)
    return labels


@pytest.mark.parametrize("type_name", sorted(model_native_enum_types()))
def test_every_declared_enum_label_is_added_by_a_migration(type_name):
    declared = model_native_enum_types()[type_name]
    missing = [label for label in declared["labels"] if label not in _provisioned_labels(type_name)]
    assert not missing, (
        f"{type_name}: {missing} declared on {', '.join(declared['columns'])} but never added to the "
        f"PostgreSQL type by any migration. Filtering or inserting these values raises "
        f"InvalidTextRepresentationError before any row is read, so the endpoint 500s even on an "
        f"empty table. Add an idempotent ALTER TYPE ... ADD VALUE IF NOT EXISTS migration."
    )


def test_vehicle_defect_is_the_capa_source_regression_case():
    """Pin the specific label whose absence broke vehicle governance.

    The parametrised test above would still pass if ``VEHICLE_DEFECT`` were
    quietly dropped from ``CAPASource`` to make the drift go away, which would
    re-break the pipeline in a different direction.
    """
    capasource = model_native_enum_types()["capasource"]
    assert "vehicle_defect" in capasource["labels"]
    assert "vehicle_defect" in _provisioned_labels("capasource")


def test_enum_add_value_migrations_do_not_bind_the_label_they_add():
    """A new enum value cannot be used in the transaction that added it.

    ``alembic/env.py`` sets no ``transaction_per_migration``, so ``alembic upgrade
    head`` runs the whole chain in one transaction — which is what CI does from an
    empty database. A migration that both adds a label and compares a column to it
    fails with "unsafe use of new value". ``20260720_capa_src_chk`` avoids this by
    casting the column to text.
    """
    enum_columns = {
        column.split(".", 1)[1] for entry in model_native_enum_types().values() for column in entry["columns"]
    }
    offenders = []
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        statements = _sql_strings(ast.parse(path.read_text(encoding="utf-8")))
        added = {
            label
            for statement in statements
            for label in re.findall(r"ADD\s+VALUE\s+(?:IF\s+NOT\s+EXISTS\s+)?'([^']+)'", statement, re.IGNORECASE)
        }
        if not added:
            continue
        for statement in statements:
            upper = statement.upper()
            if "AS TEXT" in upper or "::TEXT" in upper:
                continue
            if not any(re.search(rf"\b{re.escape(column)}\b", statement) for column in enum_columns):
                continue
            for label in sorted(added):
                if f"'{label}'" in statement:
                    offenders.append(f"{path.name}: binds '{label}' to an enum column in the migration that adds it")
    assert not offenders, offenders
