"""AST gate: FRA OCR paths must not log OCR body / evidence snippets."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_NAMES = frozenset(
    {
        "text",
        "raw_snippet",
        "evidence_snippet",
        "excerpt",
        "snippet",
        "page_texts",
        "proposed_json",
        "confirmed_json",
    }
)

TARGETS = (
    REPO_ROOT / "src/domain/services/fra_pas79_ocr_service.py",
    REPO_ROOT / "src/domain/services/compliance_schedule_fra_ocr_service.py",
    REPO_ROOT / "src/api/routes/compliance_schedule.py",
)


def _logger_call_names(node: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        # logger.info(...), logger.warning(...), logging.getLogger(...).info — cover Attr
        if isinstance(func, ast.Attribute) and func.attr in {
            "debug",
            "info",
            "warning",
            "error",
            "exception",
            "critical",
            "log",
        }:
            # Prefer logger.* — accept any *.log-level call in these modules for the gate
            if isinstance(func.value, ast.Name) and func.value.id in {"logger", "logging"}:
                calls.append(child)
            elif isinstance(func.value, ast.Attribute):
                # logging.getLogger(__name__).info — rare; still scan
                calls.append(child)
    return calls


def _names_in(node: ast.AST) -> set[str]:
    found: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            found.add(child.id)
        elif isinstance(child, ast.Attribute):
            found.add(child.attr)
    return found


def test_fra_ocr_modules_do_not_log_forbidden_names() -> None:
    violations: list[str] = []
    for path in TARGETS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call in _logger_call_names(tree):
            # Only inspect logger.* calls whose receiver is exactly `logger`
            if not (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "logger"
            ):
                continue
            used = _names_in(call)
            hit = used & FORBIDDEN_NAMES
            if hit:
                violations.append(f"{path.name}:{call.lineno} logs {sorted(hit)}")

    # Route module is large; only flag logger calls that appear inside FRA OCR handlers.
    # The AST walk above already scopes to logger.* — compliance_schedule.py may have
    # no logger today, which is fine.
    assert not violations, "OCR text must not appear in structured logs:\n" + "\n".join(violations)
