#!/usr/bin/env python3
"""CI entrypoint for Library F-3 / L-49 anti-dupe gate.

Delegates to ``scripts/governance/library/anti_dupe_gate.py`` so the SoT lives
under scripts/governance (conveyor F-3 conflict surface) while Schema Constraint
Validation can invoke a stable ``scripts/validate_*.py`` path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GATE_PATH = _REPO_ROOT / "scripts" / "governance" / "library" / "anti_dupe_gate.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("qgp_library_anti_dupe_gate", _GATE_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit(f"CRITICAL: cannot load gate module from {_GATE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_gate()
audit = _mod.audit
main = _mod.main

if __name__ == "__main__":
    raise SystemExit(main())
