#!/usr/bin/env python3
"""Ratchet audit-trail write coverage (board w1-px155 / PX-155).

Why this exists
---------------
The platform has an immutable ``AuditLogEntry`` hash chain and a
``record_audit_event`` bridge, but the board claim "audit trail covers every
module" was never measured. Historically many ``record_audit_event()`` call
sites omitted ``tenant_id`` and silently no-oped, and ``AuditLogService.log_auth``
had zero callers so login never wrote a trail row (middleware deliberately
skips ``/api/v1/auth/login`` to avoid logging passwords).

#1311 repaired signature mismatches; later PRs made ``tenant_id`` required and
fail-closed. This script is the durable census that lets the board close or
honestly scope the remaining whole-module claim with numbers.

What it measures
----------------
* Every ``record_audit_event(...)`` call in ``src/`` — wired (passes a
  non-None ``tenant_id``) vs silent (omits it or passes ``None``).
* Every ``AuditLogService.log_auth(...)`` / ``.log_auth(...)`` call in ``src/``.
* Product-module coverage derived from ``docs/product/module-briefs.md`` API
  surfaces: a module is covered when any of its route files, or the matching
  ``*_service.py``, contains a wired ``record_audit_event`` or an
  ``AuditLogService`` write helper (``log``, ``log_create``, ``log_update``,
  ``log_delete``, ``log_auth``, ``log_admin``).

What the ratchet enforces
-------------------------
* Wired ``record_audit_event`` count must not fall.
* Silent ``record_audit_event`` count must not rise.
* ``log_auth`` caller count must not fall.
* Covered product-module count must not fall.
* The set of covered module names must not shrink.

Refreshing
----------
    python3 scripts/validate_audit_trail_coverage_ratchet.py --write-baseline
    python3 scripts/validate_audit_trail_coverage_ratchet.py --markdown \\
      docs/governance/audit_trail_coverage_inventory.md
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
MODULE_BRIEFS = REPO_ROOT / "docs" / "product" / "module-briefs.md"
DEFAULT_BASELINE = REPO_ROOT / "docs" / "governance" / "audit_trail_coverage_baseline.json"
DEFAULT_MARKDOWN = REPO_ROOT / "docs" / "governance" / "audit_trail_coverage_inventory.md"

RECORD_AUDIT = "record_audit_event"
LOG_AUTH = "log_auth"
AUDIT_WRITE_METHODS = frozenset({"log", "log_create", "log_update", "log_delete", "log_auth", "log_admin"})


class RatchetFailure(Exception):
    """A coverage condition that must block the merge."""


@dataclass(frozen=True)
class CallSite:
    rel_path: str
    lineno: int
    kind: str  # record_audit_event | log_auth | audit_log_write
    method: str
    wired: bool
    reason: str


@dataclass(frozen=True)
class ProductModule:
    number: int
    name: str
    route_stems: tuple[str, ...]


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _kw_map(call: ast.Call) -> dict[str, ast.AST]:
    return {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}


def _tenant_is_wired(call: ast.Call) -> tuple[bool, str]:
    """A site is wired when it passes tenant_id and that value is not literal None."""
    kwargs = _kw_map(call)
    if "tenant_id" not in kwargs:
        return False, "omits tenant_id"
    value = kwargs["tenant_id"]
    if isinstance(value, ast.Constant) and value.value is None:
        return False, "passes tenant_id=None"
    if isinstance(value, ast.Name) and value.id == "None":
        return False, "passes tenant_id=None"
    return True, "passes tenant_id"


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def discover_call_sites(src_root: Path = SRC_ROOT) -> list[CallSite]:
    """AST-scan ``src/`` for audit write helpers."""
    sites: list[CallSite] = []
    for path in _iter_python_files(src_root):
        rel = _rel(path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except SyntaxError as exc:
            raise RatchetFailure(f"cannot parse {rel}: {exc}") from exc

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name is None:
                continue

            if name == RECORD_AUDIT:
                wired, reason = _tenant_is_wired(node)
                sites.append(
                    CallSite(
                        rel_path=rel,
                        lineno=node.lineno,
                        kind="record_audit_event",
                        method=RECORD_AUDIT,
                        wired=wired,
                        reason=reason,
                    )
                )
            elif name == LOG_AUTH:
                sites.append(
                    CallSite(
                        rel_path=rel,
                        lineno=node.lineno,
                        kind="log_auth",
                        method=LOG_AUTH,
                        wired=True,
                        reason="log_auth call",
                    )
                )
            elif name in AUDIT_WRITE_METHODS:
                # Only count Attribute calls on something that looks like AuditLogService
                # usage: AuditLogService(db).log(...) or service.log_auth(...).
                # Bare ``log(...)`` is too ambiguous; require Attribute form.
                if not isinstance(node.func, ast.Attribute):
                    continue
                # Heuristic: receiver name contains audit / service, or method is
                # log_auth / log_admin / log_create (unambiguous).
                recv = node.func.value
                recv_name = ""
                if isinstance(recv, ast.Name):
                    recv_name = recv.id.lower()
                elif isinstance(recv, ast.Call) and isinstance(recv.func, ast.Name):
                    recv_name = recv.func.id.lower()
                unambiguous = name in {"log_auth", "log_admin", "log_create", "log_update", "log_delete"}
                looks_like_audit = "audit" in recv_name or recv_name in {"service", "svc", "als"}
                if not (unambiguous or looks_like_audit):
                    continue
                if name == LOG_AUTH:
                    # already recorded above via attr name == log_auth
                    continue
                sites.append(
                    CallSite(
                        rel_path=rel,
                        lineno=node.lineno,
                        kind="audit_log_write",
                        method=name,
                        wired=True,
                        reason=f"AuditLogService.{name}",
                    )
                )
    return sites


def parse_product_modules(briefs_path: Path = MODULE_BRIEFS) -> list[ProductModule]:
    """Read module name + route stems from the product module briefs."""
    if not briefs_path.is_file():
        raise RatchetFailure(f"module briefs not found at {briefs_path}")
    text = briefs_path.read_text(encoding="utf-8")
    modules: list[ProductModule] = []
    pattern = re.compile(
        r"### (\d+)\. (.+)\n([\s\S]*?)(?=\n---|\n### |\Z)",
    )
    for match in pattern.finditer(text):
        number = int(match.group(1))
        name = match.group(2).strip()
        body = match.group(3)
        routes = re.findall(r"`src/api/routes/([^`]+)`", body)
        stems = tuple(Path(r).stem for r in routes)
        if not stems:
            continue
        modules.append(ProductModule(number=number, name=name, route_stems=stems))
    if len(modules) < 20:
        raise RatchetFailure(f"expected ≥20 product modules from {briefs_path}, found {len(modules)}")
    return modules


def _file_stems_with_writers(sites: list[CallSite]) -> set[str]:
    """Map writer files to stems usable against module route stems."""
    stems: set[str] = set()
    for site in sites:
        if site.kind == "record_audit_event" and not site.wired:
            continue
        path = Path(site.rel_path)
        stem = path.stem
        stems.add(stem)
        # capa_service.py covers capa; incident_service.py covers incidents
        if stem.endswith("_service"):
            base = stem[: -len("_service")]
            stems.add(base)
            # plural route stems
            stems.add(base + "s")
            if base.endswith("y"):
                stems.add(base[:-1] + "ies")
        if stem == "auth":
            stems.add("auth")
            stems.add("users")
    return stems


def classify_modules(modules: list[ProductModule], sites: list[CallSite]) -> tuple[list[str], list[str]]:
    writer_stems = _file_stems_with_writers(sites)
    covered: list[str] = []
    uncovered: list[str] = []
    for mod in modules:
        if any(stem in writer_stems for stem in mod.route_stems):
            covered.append(mod.name)
        else:
            uncovered.append(mod.name)
    return covered, uncovered


def inventory_audit_coverage(
    src_root: Path = SRC_ROOT,
    briefs_path: Path = MODULE_BRIEFS,
) -> dict[str, Any]:
    sites = discover_call_sites(src_root)
    modules = parse_product_modules(briefs_path)

    record_sites = [s for s in sites if s.kind == "record_audit_event"]
    wired = [s for s in record_sites if s.wired]
    silent = [s for s in record_sites if not s.wired]
    log_auth_sites = [s for s in sites if s.kind == "log_auth"]
    other_writes = [s for s in sites if s.kind == "audit_log_write"]

    covered, uncovered = classify_modules(modules, sites)

    def _site_dict(s: CallSite) -> dict[str, Any]:
        return {
            "path": s.rel_path,
            "lineno": s.lineno,
            "kind": s.kind,
            "method": s.method,
            "wired": s.wired,
            "reason": s.reason,
        }

    return {
        "record_audit_event_total": len(record_sites),
        "wired_record_audit_event_count": len(wired),
        "silent_record_audit_event_count": len(silent),
        "log_auth_caller_count": len(log_auth_sites),
        "other_audit_log_write_count": len(other_writes),
        "product_module_count": len(modules),
        "covered_module_count": len(covered),
        "uncovered_module_count": len(uncovered),
        "covered_modules": covered,
        "uncovered_modules": uncovered,
        "wired_sites": [_site_dict(s) for s in wired],
        "silent_sites": [_site_dict(s) for s in silent],
        "log_auth_sites": [_site_dict(s) for s in log_auth_sites],
        "other_audit_log_write_sites": [_site_dict(s) for s in other_writes],
    }


def build_baseline(current: dict[str, Any]) -> dict[str, Any]:
    return {
        "_comment": (
            "Inventory lock for audit-trail write coverage (board w1-px155 / PX-155). "
            "Generated by scripts/validate_audit_trail_coverage_ratchet.py --write-baseline. "
            "Floors fail when they fall; max_silent fails when it rises; covered_modules "
            "must not shrink."
        ),
        "min_wired_record_audit_event_count": current["wired_record_audit_event_count"],
        "max_silent_record_audit_event_count": current["silent_record_audit_event_count"],
        "min_log_auth_caller_count": current["log_auth_caller_count"],
        "min_covered_module_count": current["covered_module_count"],
        "covered_modules": list(current["covered_modules"]),
        "record_audit_event_total": current["record_audit_event_total"],
        "product_module_count": current["product_module_count"],
        "uncovered_module_count": current["uncovered_module_count"],
    }


def check_ratchet(current: dict[str, Any], baseline: dict[str, Any]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []

    min_wired = int(baseline["min_wired_record_audit_event_count"])
    max_silent = int(baseline["max_silent_record_audit_event_count"])
    min_log_auth = int(baseline["min_log_auth_caller_count"])
    min_covered = int(baseline["min_covered_module_count"])
    baseline_covered = set(baseline.get("covered_modules") or [])

    wired_now = int(current["wired_record_audit_event_count"])
    silent_now = int(current["silent_record_audit_event_count"])
    log_auth_now = int(current["log_auth_caller_count"])
    covered_now = int(current["covered_module_count"])
    current_covered = set(current.get("covered_modules") or [])

    if wired_now < min_wired:
        failures.append(
            f"wired record_audit_event count fell from floor {min_wired} to {wired_now}. "
            "Do not remove tenant_id from audit call sites without replacing coverage."
        )
    if silent_now > max_silent:
        failures.append(
            f"silent record_audit_event count rose from ceiling {max_silent} to {silent_now}. "
            "New call sites must pass a resolvable tenant_id."
        )
    if log_auth_now < min_log_auth:
        failures.append(
            f"log_auth caller count fell from floor {min_log_auth} to {log_auth_now}. "
            "Auth login/logout/token-exchange must keep writing AuditLogEntry rows."
        )
    if covered_now < min_covered:
        failures.append(f"covered product-module count fell from floor {min_covered} to {covered_now}.")

    lost = sorted(baseline_covered - current_covered)
    if lost:
        failures.append(f"{len(lost)} previously covered module(s) lost audit writers: {', '.join(lost)}.")

    if wired_now > min_wired:
        warnings.append(
            f"wired count rose from {min_wired} to {wired_now} — refresh baseline with "
            "--write-baseline so the ratchet tightens."
        )
    if silent_now < max_silent:
        warnings.append(f"silent count fell from {max_silent} to {silent_now} — refresh baseline.")
    if log_auth_now > min_log_auth:
        warnings.append(f"log_auth callers rose from {min_log_auth} to {log_auth_now} — refresh baseline.")
    if covered_now > min_covered:
        warnings.append(f"covered modules rose from {min_covered} to {covered_now} — refresh baseline.")
    gained = sorted(current_covered - baseline_covered)
    if gained and covered_now >= min_covered:
        warnings.append(
            f"{len(gained)} module(s) newly covered: {', '.join(gained)}. " "Include them in the next baseline refresh."
        )

    return failures, warnings


def render_markdown(current: dict[str, Any], baseline: Optional[dict[str, Any]] = None) -> str:
    lines = [
        "# Audit-trail coverage inventory (w1-px155 / PX-155)",
        "",
        "Generated by `scripts/validate_audit_trail_coverage_ratchet.py`.",
        "This is the durable census for the board claim that the audit trail",
        "covers every module. It measures writers that persist `AuditLogEntry`",
        "rows — not middleware request logs, and not observability metrics.",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| `record_audit_event` call sites | {current['record_audit_event_total']} |",
        f"| Wired (passes non-None `tenant_id`) | {current['wired_record_audit_event_count']} |",
        f"| Silent (omit / `None` tenant — no row) | {current['silent_record_audit_event_count']} |",
        f"| `log_auth` callers | {current['log_auth_caller_count']} |",
        f"| Other `AuditLogService` write helpers | {current['other_audit_log_write_count']} |",
        f"| Product modules (from module briefs) | {current['product_module_count']} |",
        f"| Modules with ≥1 audit writer | {current['covered_module_count']} |",
        f"| Modules with no audit writer | {current['uncovered_module_count']} |",
        "",
    ]
    if baseline:
        lines += [
            "## Committed ratchet",
            "",
            "| Floor / ceiling | Value |",
            "| --- | ---: |",
            f"| `min_wired_record_audit_event_count` | {baseline['min_wired_record_audit_event_count']} |",
            f"| `max_silent_record_audit_event_count` | {baseline['max_silent_record_audit_event_count']} |",
            f"| `min_log_auth_caller_count` | {baseline['min_log_auth_caller_count']} |",
            f"| `min_covered_module_count` | {baseline['min_covered_module_count']} |",
            "",
            "CI fails if wired/`log_auth`/covered floors fall, silent count rises,",
            "or a previously covered module loses its writers",
            "(`docs/governance/audit_trail_coverage_baseline.json`).",
            "",
        ]

    lines += [
        "## Covered modules",
        "",
    ]
    for name in current["covered_modules"]:
        lines.append(f"- {name}")
    lines += [
        "",
        "## Uncovered modules (follow-up backlog)",
        "",
        "These product modules have no `record_audit_event` / `AuditLogService`",
        "write call under their route stem or matching `*_service.py`. Middleware",
        "may still log mutating HTTP requests for some of them; that is not the",
        "hash-chained Admin Audit Trail this board item tracks.",
        "",
    ]
    if current["uncovered_modules"]:
        for name in current["uncovered_modules"]:
            lines.append(f"- {name}")
    else:
        lines.append("_None._")

    lines += [
        "",
        "## Silent `record_audit_event` sites",
        "",
    ]
    if current["silent_sites"]:
        for site in current["silent_sites"]:
            lines.append(f"- `{site['path']}:{site['lineno']}` — {site['reason']}")
    else:
        lines.append("_None._ Every `record_audit_event` call site passes a non-None `tenant_id`.")

    lines += [
        "",
        "## `log_auth` callers",
        "",
    ]
    if current["log_auth_sites"]:
        for site in current["log_auth_sites"]:
            lines.append(f"- `{site['path']}:{site['lineno']}`")
    else:
        lines.append("_None._ Login/logout never write an `AuditLogEntry` " "(middleware skips `/api/v1/auth/login`).")

    lines += [
        "",
        "## Honesty note for board closure",
        "",
        'Closing **w1-px155** as "every module" would be false while uncovered',
        "modules remain. This inventory scopes the claim: silent call-site no-ops",
        "are gated at zero (or a measured ceiling), auth login is wired via",
        "`log_auth`, and the uncovered module list is the explicit follow-up",
        "backlog — not an unverified whole-platform assertion.",
        "",
    ]
    return "\n".join(lines) + "\n"


def _print_report(current: dict[str, Any]) -> None:
    print("=== Audit-trail coverage ratchet (w1-px155) ===")
    print(f"record_audit_event total: {current['record_audit_event_total']}")
    print(f"  wired:  {current['wired_record_audit_event_count']}")
    print(f"  silent: {current['silent_record_audit_event_count']}")
    print(f"log_auth callers: {current['log_auth_caller_count']}")
    print(
        f"modules covered/uncovered: "
        f"{current['covered_module_count']}/{current['uncovered_module_count']} "
        f"(of {current['product_module_count']})"
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--inventory-json",
        type=Path,
        default=None,
        help="Optional path to write the live inventory JSON.",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        nargs="?",
        const=DEFAULT_MARKDOWN,
        default=None,
        help="Write the Markdown inventory (default path if flag given with no value).",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Rewrite the baseline from this run.",
    )
    parser.add_argument(
        "--from-inventory",
        type=Path,
        default=None,
        help="Use a precomputed inventory JSON instead of scanning (tests).",
    )
    args = parser.parse_args(argv)

    try:
        if args.from_inventory is not None:
            if not args.from_inventory.is_file():
                raise RatchetFailure(f"inventory not found at {args.from_inventory}")
            current = json.loads(args.from_inventory.read_text(encoding="utf-8"))
        else:
            current = inventory_audit_coverage()
    except RatchetFailure as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    _print_report(current)

    if args.inventory_json is not None:
        args.inventory_json.parent.mkdir(parents=True, exist_ok=True)
        args.inventory_json.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"[OK] inventory written to {args.inventory_json}")

    if args.write_baseline:
        payload = build_baseline(current)
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"[OK] baseline written to {args.baseline}")
        if args.markdown is not None:
            args.markdown.parent.mkdir(parents=True, exist_ok=True)
            args.markdown.write_text(render_markdown(current, payload), encoding="utf-8")
            print(f"[OK] markdown written to {args.markdown}")
        return 0

    if not args.baseline.is_file():
        print(
            f"[FAIL] no baseline at {args.baseline}; generate one with --write-baseline",
            file=sys.stderr,
        )
        return 1

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    for key in (
        "min_wired_record_audit_event_count",
        "max_silent_record_audit_event_count",
        "min_log_auth_caller_count",
        "min_covered_module_count",
        "covered_modules",
    ):
        if key not in baseline:
            print(f"[FAIL] baseline missing required key {key!r}", file=sys.stderr)
            return 1

    failures, warnings = check_ratchet(current, baseline)
    for msg in warnings:
        print(f"[WARN] {msg}")
    if failures:
        for msg in failures:
            print(f"[FAIL] {msg}", file=sys.stderr)
        return 1

    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(current, baseline), encoding="utf-8")
        print(f"[OK] markdown written to {args.markdown}")

    print("[OK] audit-trail coverage within baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
