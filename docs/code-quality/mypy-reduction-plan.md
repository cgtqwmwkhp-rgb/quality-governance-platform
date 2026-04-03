# Mypy Type-Safety Reduction Plan (D21)

Progressive plan to eliminate `type: ignore` comments and `ignore_errors = true` overrides.

## Current State

| Metric | Value |
|--------|-------|
| `type: ignore` count (src/) | 186 |
| MAX_TYPE_IGNORES ceiling | 190 |
| `ignore_errors = true` modules | 65 |
| Target `type: ignore` count | < 100 |
| Target `ignore_errors` modules | 0 |

## Milestones

| Phase | Target | Ceiling | Modules Removed | Timeline |
|-------|--------|---------|-----------------|----------|
| Phase 1 (current) | 190 ignores, reduce ceiling from 200 | 190 | Ceiling reduced; module removal deferred to Phase 2 (type errors must be fixed first) | Sprint 1 |
| Phase 2 | 150 ignores, remove 10 more modules | 150 | Small route files and utility services | Sprint 2-3 |
| Phase 3 | 100 ignores, remove 20 more modules | 100 | Domain services and middleware | Sprint 4-6 |
| Phase 4 | < 50 ignores, all modules type-checked | 50 | Remaining modules | Sprint 7-10 |

## Approach

1. **Modules removed from `ignore_errors`** are promoted to full mypy checking. Any type errors must be fixed before the module is removed from the override list.
2. **`type: ignore` comments** are reduced by fixing the underlying type issues. Each reduction batch targets a specific error category (e.g., `arg-type`, `return-value`, `assignment`).
3. **Ceiling enforcement** via `scripts/validate_type_ignores.py` prevents regression.

## Phase 1 Target Modules

The following 5 modules are targeted for removal from `ignore_errors = true` after their type errors are fixed:

- `src.api.routes.health` — 1 annotation-unchecked note
- `src.api.routes.feature_flags` — 2 assignment errors (Column types)
- `src.api.routes.slo` — 1 implicit Optional error
- `src.api.routes.signatures` — 10 errors (arg-type, assignment, union-attr)
- `src.api.routes.notifications` — 2 errors (arg-type, attr-defined)

These require targeted type fixes before they can be removed from the override list.

## Governance

- Ceiling reductions require PR approval from a code owner.
- New `type: ignore` additions must include an error-code-specific annotation (e.g., `# type: ignore[arg-type]`) and a tracking tag (e.g., `# TYPE-IGNORE: GH-xxx`).
- The `validate_type_ignores.py` script runs in CI as part of the `code-quality` job.
