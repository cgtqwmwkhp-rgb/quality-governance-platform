# Type Safety Evolution Tracker (D21)

## Current State

| Metric | Value | Trend |
|--------|-------|-------|
| mypy `ignore_errors` modules | 12 (down from 64) | Reducing |
| `MAX_TYPE_IGNORES` ceiling | 203 | Ratchet down |
| mypy override blocks | 8 | Consolidated |
| Modules promoted to full checking | 52 | Increasing |
| mypy strict mode | Enabled | — |

## Promotion History

| Date | Action | Modules | ignore_errors Count |
|------|--------|---------|---------------------|
| 2026-03-01 | Baseline | — | 64 |
| 2026-03-07 | First consolidation | — | 30 override blocks |
| 2026-03-21 | Major promotion wave | 44 modules promoted | 20 |
| 2026-04-04 | Second promotion wave | 8 modules promoted | 12 |

## Remaining `ignore_errors` Modules (12)

Each module below has known cross-module type errors. They are on `ignore_errors` because fixing them requires coordinated changes across multiple files (typically route + service + model layers).

| Module | Category | Reason | Estimated Effort |
|--------|----------|--------|-----------------|
| `src.api.routes.actions` | Route | Complex multi-model query building | Medium |
| `src.api.routes.audits` | Route | Audit run + finding + response model mismatches | Medium |
| `src.api.routes.document_control` | Route | `db: DbSession = None` FastAPI pattern | Low |
| `src.api.routes.iso27001` | Route | `db: DbSession = None` FastAPI pattern | Low |
| `src.api.routes.planet_mark` | Route | Carbon calculation model types | Medium |
| `src.api.routes.signatures` | Route | `db: DbSession = None` FastAPI pattern | Low |
| `src.api.routes.xml_import` | Route | `db: DbSession = None` FastAPI pattern | Low |
| `src.domain.services.form_config_service` | Service | Dynamic form schema type complexity | High |
| `src.domain.services.risk_service` | Service | Risk scoring model type unions | Medium |
| `src.domain.services.search_service` | Service | Full-text search query builder types | Medium |
| `src.infrastructure.tasks.pams_sync_tasks` | Infra | External API response typing | Medium |
| `src.services.risk_scoring` | Service | Mathematical scoring algorithm types | Medium |

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
