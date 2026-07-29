#!/usr/bin/env python3.11
"""Census of ``record_audit_event`` call sites and whether each passes tenant_id.

An AuditLogEntry can only be written when ``record_audit_event`` receives a
tenant_id; without one the bridge discards the event (see
``src/domain/services/audit_service.py``). This walks every call site with the
AST so the count is exact rather than grep-approximate, and reports any use of
``**kwargs`` — which would make the census incomplete, since tenant_id could
then arrive invisibly.

Usage: python3.11 scripts/analysis/audit_tenant_census.py [src_root]
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

TARGET = "record_audit_event"

DELETE_FLAVOURED = (
    "delete",
    "purge",
    "remove",
    "archive",
    "cascade",
    "destroy",
)


@dataclass(frozen=True)
class CallSite:
    path: str
    line: int
    action: str
    has_tenant: bool
    has_kwargs: bool

    @property
    def delete_flavoured(self) -> bool:
        return any(token in self.action.lower() for token in DELETE_FLAVOURED)


def _called_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _literal(node: ast.AST) -> str:
    """Render an argument for reporting without evaluating it."""
    if isinstance(node, ast.Constant):
        return str(node.value)
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001 — reporting only
        return "<expr>"


def _action_of(node: ast.Call) -> str:
    for kw in node.keywords:
        if kw.arg == "action":
            return _literal(kw.value)
    # Positional: db, event_type, entity_type, entity_id, action
    if len(node.args) >= 5:
        return _literal(node.args[4])
    return "<unknown>"


def collect(root: Path) -> list[CallSite]:
    sites: list[CallSite] = []
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover — surfaced, never swallowed
            print(f"SYNTAX ERROR {path}: {exc}", file=sys.stderr)
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _called_name(node) != TARGET:
                continue
            kw_names = {kw.arg for kw in node.keywords}
            sites.append(
                CallSite(
                    path=str(path),
                    line=node.lineno,
                    action=_action_of(node),
                    has_tenant="tenant_id" in kw_names,
                    has_kwargs=None in kw_names,
                )
            )
    return sites


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "src")
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    sites = collect(root)
    # A definition is itself a call-free node, but the module defining the
    # function may also call it; nothing to exclude here beyond that.
    missing = [s for s in sites if not s.has_tenant]
    deletes = [s for s in sites if s.delete_flavoured]
    kwargs_sites = [s for s in sites if s.has_kwargs]

    print(f"total call sites            : {len(sites)}")
    print(f"  pass tenant_id            : {len(sites) - len(missing)}")
    print(f"  omit tenant_id (discarded): {len(missing)}")
    print(f"delete-flavoured call sites : {len(deletes)}")
    print(f"  pass tenant_id            : {sum(1 for s in deletes if s.has_tenant)}")
    print(f"  omit tenant_id (discarded): {sum(1 for s in deletes if not s.has_tenant)}")
    print(f"sites using **kwargs        : {len(kwargs_sites)} (non-zero == census incomplete)")

    print("\n-- sites omitting tenant_id --")
    for site in missing:
        flag = "DELETE" if site.delete_flavoured else "      "
        print(f"{flag} {site.path}:{site.line} action={site.action}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
