"""Every ``record_audit_event`` call site must be signature-compatible.

A mismatched keyword here is not a lint nit: the call raises ``TypeError`` at
runtime and takes the whole request down with it, so the user sees an HTTP 500
on an operation that appeared to succeed in review. Seven route call sites
omitted the required ``event_type`` and passed an unknown ``details=``, which
broke form template and contract writes in production.

mypy does not catch it because these modules are not under strict checking, so
this test is the guard.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from src.domain.services.audit_service import record_audit_event

SRC = Path(__file__).resolve().parents[2] / "src"
FUNC = "record_audit_event"


def _call_sites() -> list[tuple[Path, ast.Call]]:
    sites: list[tuple[Path, ast.Call]] = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name == FUNC:
                sites.append((path, node))
    return sites


def _ids() -> list[str]:
    return [f"{p.relative_to(SRC)}:{c.lineno}" for p, c in _call_sites()]


def test_there_are_call_sites_to_check() -> None:
    """Guard against the scan silently matching nothing and passing vacuously."""
    assert len(_call_sites()) > 20


@pytest.mark.parametrize("path,call", _call_sites(), ids=_ids())
def test_call_site_matches_the_signature(path: Path, call: ast.Call) -> None:
    sig = inspect.signature(record_audit_event)
    kwargs = {kw.arg for kw in call.keywords if kw.arg is not None}

    unknown = kwargs - set(sig.parameters)
    assert not unknown, (
        f"{path.relative_to(SRC)}:{call.lineno} passes {sorted(unknown)}, which "
        f"{FUNC}() does not accept. This raises TypeError at runtime."
    )

    required = {
        name
        for name, p in sig.parameters.items()
        if p.default is inspect.Parameter.empty
        and p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    supplied = kwargs | {name for name, _ in zip(sig.parameters, call.args, strict=False)}
    missing = required - supplied
    assert not missing, (
        f"{path.relative_to(SRC)}:{call.lineno} omits required {sorted(missing)}. " f"This raises TypeError at runtime."
    )


@pytest.mark.parametrize("path,call", _call_sites(), ids=_ids())
def test_call_site_passes_a_tenant(path: Path, call: ast.Call) -> None:
    """Without a tenant the bridge logs a warning and persists nothing.

    That is the second half of PX-155 and the quieter one: the request succeeds,
    the caller sees no error, and no audit row is ever written. Sites that have
    not yet been threaded are listed below so the number can only go down.
    """
    unthreaded = {
        "api/routes/actions.py",
        "api/routes/complaints.py",
        "api/routes/incidents.py",
        "api/routes/near_miss.py",
        "api/routes/policies.py",
        "api/routes/rtas.py",
        "api/routes/vehicle_checklists.py",
        "domain/services/action_assignment_service.py",
        "domain/services/audit_service.py",
        "domain/services/capa_service.py",
        "domain/services/competence_gap_service.py",
        "domain/services/near_miss_service.py",
        "domain/services/rta_service.py",
    }
    rel = str(path.relative_to(SRC))
    if rel in unthreaded:
        pytest.xfail(f"{rel} has not been threaded with tenant_id yet (PX-155)")

    kwargs = {kw.arg for kw in call.keywords if kw.arg is not None}
    assert "tenant_id" in kwargs, (
        f"{rel}:{call.lineno} does not pass tenant_id, so record_audit_event() "
        f"will log a warning and persist no audit row."
    )
