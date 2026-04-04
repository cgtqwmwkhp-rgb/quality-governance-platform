# Type Safety Evolution Tracker (D21)

## Current State

| Metric | Value | Trend |
|--------|-------|-------|
| mypy `ignore_errors` modules | 12 (down from 64) | Reducing |
| `MAX_TYPE_IGNORES` ceiling | 203 | Ratchet down |
| mypy override blocks | 8 | Consolidated |
| Modules promoted to full checking | 52 | Increasing |
| mypy strict mode | Enabled | — |
| Coverage threshold | `fail_under = 70` (raised from 65) | Increasing |

## Promotion History

| Date | Action | Modules | ignore_errors Count |
|------|--------|---------|---------------------|
| 2026-03-01 | Baseline | — | 64 |
| 2026-03-07 | First consolidation | — | 30 override blocks |
| 2026-03-21 | Major promotion wave | 44 modules promoted | 20 |
| 2026-04-04 | Second promotion wave | 8 modules promoted | 12 |

## Remaining `ignore_errors` Modules (12)

Each module below has cross-module type errors (assignment, operator, attr-defined). They require coordinated fixes across route + service + model layers. Individual-file mypy passes, but full-codebase checks surface cross-module conflicts.

Five targeted `disable_error_code` overrides remain for specific error categories where suppression is intentional (third-party stubs, FastAPI dependency injection patterns).

## Type-Ignore Ratchet

The `scripts/validate_type_ignores.py` script enforces a ceiling (`MAX_TYPE_IGNORES = 203`) that can only increase with explicit approval. Each new `type: ignore` must:
1. Use an error-code-specific annotation (e.g., `# type: ignore[arg-type]`)
2. Include an issue tag (e.g., `# TYPE-IGNORE: GH-123`)

## Roadmap

| Quarter | Target |
|---------|--------|
| Q2 2026 | Reduce `ignore_errors` to ≤ 8 modules (promote 4 `db: DbSession = None` routes) |
| Q3 2026 | Reduce `MAX_TYPE_IGNORES` to < 180 |
| Q4 2026 | Reduce `ignore_errors` to ≤ 5 modules |

## Quality Tools Enforced in CI

| Tool | Config | Enforcement |
|------|--------|-------------|
| black | `pyproject.toml` `[tool.black]` line-length=120 | Blocking in `code-quality` job |
| isort | `pyproject.toml` `[tool.isort]` profile=black | Blocking in `code-quality` job |
| flake8 | `.flake8` max-line-length=120 | Blocking in `code-quality` job |
| mypy | `pyproject.toml` `[tool.mypy]` strict | Blocking in `code-quality` job |
| type-ignore validator | `scripts/validate_type_ignores.py` | Blocking in `code-quality` job |
| radon complexity | CI `radon-complexity` job | Blocking in `all-checks` |

## Related Documents

- [`pyproject.toml`](../../pyproject.toml) — tool configuration
- [`scripts/validate_type_ignores.py`](../../scripts/validate_type_ignores.py) — ratchet enforcement
- [`.flake8`](../../.flake8) — flake8 configuration
