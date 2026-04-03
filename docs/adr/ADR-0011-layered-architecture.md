# ADR-0011: Layered Architecture Enforcement

**Status**: Accepted
**Date**: 2026-04-03
**Deciders**: Platform Engineering Team

## Context

QGP uses a layered architecture with five layers: `api`, `core`, `domain`, `infrastructure`, and `services`. Without automated enforcement, architectural boundaries are violated through transitive imports, leading to tight coupling.

## Decision

We enforce import boundaries via `scripts/check_import_boundaries.py` running in CI (`import-boundary-check` job, blocking in `all-checks`).

### Layer Rules

| Source Layer | Cannot Import From | Exceptions |
|---|---|---|
| `src/domain` | `src.api` | None |
| `src/domain` | `src.infrastructure` | `src.infrastructure.resilience` |
| `src/core` | `src.api` | None |
| `src/core` | `src.infrastructure` | None |
| `src/services` | `src.api` | None |
| `src/infrastructure` | `src.api` | `src.infrastructure.tasks` (Celery tasks need API schemas) |
| `src/infrastructure` | `src.services` | None |

### Dependency Direction

```
api → services → domain ← infrastructure
         ↓           ↑
        core ─────────┘
```

Outer layers (api, infrastructure) depend on inner layers (domain, core). Inner layers never depend outward.

## Alternatives Considered

1. **`import-linter` package**: More comprehensive (transitive analysis, contract declarations) but adds a dependency. Current AST-based script is lightweight and sufficient.
2. **No enforcement**: Rejected — boundary violations were accumulating (100+ found in initial scan).
3. **Monorepo with separate packages**: Over-engineering for current team size.

## Consequences

- Import violations are caught in CI before merge
- New developers get immediate feedback on architectural violations
- Script must be updated when new layers are added
