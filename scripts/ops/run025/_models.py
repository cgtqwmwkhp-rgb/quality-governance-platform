"""Load exactly the model metadata that ``alembic/env.py`` compares against.

Both Run025 scripts need ``Base.metadata``, and it matters that they see the same
set of tables Alembic does. Until C-70, sweeping ``src/domain/models`` with
``pkgutil`` did not: it pulled in ``audit_template.py``, which registered a second
class named ``AuditTemplate`` on the same declarative ``Base`` as ``audit.py`` and
added seven tables that no migration creates, producing seven "missing table"
findings that were an artefact of the import strategy rather than drift. That
module is deleted, and it was the only model file on disk outside this list, so the
two strategies currently agree. The list is still the right thing to follow: it is
the set Alembic compares, and it is the set that stays correct if a dead module
appears again.

So the import list is read out of ``alembic/env.py`` rather than restated here.
Restating it would go stale the first time someone adds a model module there, and
a schema-parity tool that silently stops looking at part of the schema is worse
than no tool.

``env.py`` cannot be imported — it runs migrations as an import side effect — so
the module list and the exclusion set are parsed out of its source.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_ENV = REPO_ROOT / "alembic" / "env.py"
TENANT_NOT_NULL_MIGRATION = REPO_ROOT / "alembic" / "versions" / "20260901_case_action_tenant_id_not_null.py"


def _env_ast() -> ast.Module:
    return ast.parse(ALEMBIC_ENV.read_text(encoding="utf-8"))


def migration_target_tables() -> tuple[str, ...]:
    """``TARGET_TABLES`` as declared by the tenant NOT NULL migration.

    Parsed rather than restated. The remediation scripts must act on exactly the
    tables the migration will refuse over — a script that cleans nine of ten
    leaves the deploy failing for a reason the operator has just been told is
    fixed.
    """
    tree = ast.parse(TENANT_NOT_NULL_MIGRATION.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "TARGET_TABLES" and node.value is not None:
                return tuple(ast.literal_eval(node.value))
    raise RuntimeError(f"could not find TARGET_TABLES in {TENANT_NOT_NULL_MIGRATION}")


def side_effect_model_modules() -> tuple[str, ...]:
    """Module names ``alembic/env.py`` imports for their metadata side effects."""
    for node in ast.walk(_env_ast()):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == "_metadata_mod":
            return tuple(ast.literal_eval(node.iter))
    raise RuntimeError(f"could not find the _metadata_mod import loop in {ALEMBIC_ENV}")


def alembic_check_excluded_tables() -> frozenset[str]:
    """``_ALEMBIC_CHECK_EXCLUDED_TABLES`` as declared in ``alembic/env.py``."""
    for node in ast.walk(_env_ast()):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_ALEMBIC_CHECK_EXCLUDED_TABLES":
                    return frozenset(ast.literal_eval(node.value.args[0]))
    raise RuntimeError(f"could not find _ALEMBIC_CHECK_EXCLUDED_TABLES in {ALEMBIC_ENV}")


def load_metadata() -> Any:
    """Import models the way ``alembic/env.py`` does and return ``Base.metadata``."""
    models_pkg = importlib.import_module("src.domain.models")
    for name in getattr(models_pkg, "__all__", []):
        getattr(models_pkg, name, None)
    for module in side_effect_model_modules():
        importlib.import_module(module)

    from src.infrastructure.database import Base

    return Base.metadata


def tenant_required_tables() -> list[str]:
    """Tables whose model declares ``tenant_id`` ``nullable=False``."""
    metadata = load_metadata()
    return sorted(
        name for name, table in metadata.tables.items() if "tenant_id" in table.c and not table.c["tenant_id"].nullable
    )
