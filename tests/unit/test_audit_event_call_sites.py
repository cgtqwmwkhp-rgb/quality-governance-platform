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
    """Every call site must supply a tenant, with no exemption list.

    That is the second half of PX-155 and the quieter one. 44 of the 71 sites
    omitted tenant_id, including ``permanent_delete`` and ``purge``, and the
    bridge answered by logging a warning and returning the unsaved event — so
    the request succeeded, the caller saw no error, and no audit row was ever
    written. ``tenant_id`` is now a required keyword-only parameter, which makes
    ``test_call_site_matches_the_signature`` above enforce the same thing; this
    test states the reason when it fails.
    """
    rel = str(path.relative_to(SRC))
    kwargs = {kw.arg for kw in call.keywords if kw.arg is not None}
    assert "tenant_id" in kwargs, (
        f"{rel}:{call.lineno} does not pass tenant_id, so record_audit_event() "
        f"will refuse the event and raise AuditNotRecordableError."
    )


@pytest.mark.parametrize("path,call", _call_sites(), ids=_ids())
def test_every_call_site_names_the_record(path: Path, call: ast.Call) -> None:
    """Every call site must say *which* record the event is about (C-5).

    Sampled entries carried the actor, the entity *type* and the timestamp, and a
    null ``entity_name`` — so the trail could say "this user updated an incident"
    but never which incident. For ISO 9001 / 45001 that is not a defensible
    record, and it is the difference between an audit trail that is populated and
    one that is evidence.

    ``entity_name`` is deliberately *optional* in the signature: it is metadata,
    and per the fail-closed contract added by #1413 a missing name must never
    refuse the mutation being audited the way a missing tenant does. A required
    parameter would turn an omission into a TypeError, i.e. an HTTP 500 on a
    business operation, which trades this defect for a worse one. So the
    signature cannot enforce this and this census does instead.

    Where an event genuinely has no single subject — a list endpoint, a bulk
    purge — the call site passes ``NO_SINGLE_ENTITY`` or a phrase naming the set.
    That is a deliberate answer and is visibly different from a null, which is
    what "we forgot" looks like.
    """
    rel = str(path.relative_to(SRC))
    kwargs = {kw.arg for kw in call.keywords if kw.arg is not None}
    assert "entity_name" in kwargs, (
        f"{rel}:{call.lineno} does not pass entity_name, so the audit entry will "
        f"name the entity type but not the record. Pass the record's reference "
        f"number or title, or NO_SINGLE_ENTITY if the event covers a set."
    )


@pytest.mark.parametrize("path,call", _call_sites(), ids=_ids())
def test_no_call_site_passes_an_empty_entity_name(path: Path, call: ast.Call) -> None:
    """A literal empty or whitespace name satisfies the census above but says nothing.

    Only catches constants; an expression that evaluates to ``""`` at runtime is
    normalised to ``None`` by the bridge rather than stored as a blank.
    """
    rel = str(path.relative_to(SRC))
    for kw in call.keywords:
        if kw.arg != "entity_name":
            continue
        if isinstance(kw.value, ast.Constant):
            value = kw.value.value
            assert value is not None, f"{rel}:{call.lineno} passes entity_name=None explicitly."
            assert isinstance(value, str) and value.strip(), (
                f"{rel}:{call.lineno} passes a blank entity_name, which records nothing. "
                f"Use NO_SINGLE_ENTITY if the event has no single subject record."
            )
