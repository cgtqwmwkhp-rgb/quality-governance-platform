# Architecture modularity — module boundaries

This document defines how top-level Python packages in `src/` relate to each other, what they may import, and where external systems (notably PAMS) are isolated.

---

## Module map

| Package | Responsibility | Allowed dependencies (imports) |
|--------|------------------|----------------------------------|
| **`src/api`** | HTTP surface: routers, request/response schemas, FastAPI dependencies, API middleware (errors, idempotency), OpenAPI exposure. Translates HTTP ↔ application use cases. | **`src/domain`**, **`src/services`**, **`src/infrastructure`**, **`src/core`** |
| **`src/core`** | Cross-cutting primitives: configuration (`settings`), shared middleware hooks (e.g. request ID), pagination types, small utilities with no business rules. | **Standard library and third-party packages only** — **no** `src.api`, `src.domain`, `src.infrastructure`, or `src.services` |
| **`src/domain`** | Business concepts: entities, value objects, domain services, invariants, and orchestration that express policy without I/O. | **`src/core`** only (for config-free shared types if needed). **Must not** import **`src/api`** or **`src/infrastructure`**. |
| **`src/infrastructure`** | Technical capabilities: primary DB (`database.py`), optional external DBs, Redis, Azure/monitoring, rate limiting middleware implementation, filesystem, email, etc. Adapts external tech to interfaces the app uses. | **`src/core`** (e.g. `settings`, logging). **Must not** import **`src/domain`** or **`src/api`**. |
| **`src/services`** | Application layer: coordinates domain logic with infrastructure (transactions, repositories, calls to external systems) for use cases the API invokes. | **`src/domain`**, **`src/infrastructure`**, **`src/core`**. **Must not** import **`src/api`**. |

`src/main.py` composes the app (wiring, middleware order, lifespan). It may import from **`api`**, **`core`**, and **`infrastructure`**; keep it thin and free of business rules.

---

## Dependency rules

1. **Domain is innermost**  
   `src/domain` **must not** import from **`src/api`** or **`src/infrastructure`**. Domain stays testable and free of framework and vendor SDKs.

2. **API sits at the edge**  
   `src/api` **depends on** **`src/domain`**, **`src/infrastructure`**, **`src/core`**, and **`src/services`** as needed to handle HTTP and to reach use cases.

3. **Infrastructure is outward-facing**  
   `src/infrastructure` does **not** depend on **`src/domain`** or **`src/api`**. It may use **`src/core`** (configuration, shared non-domain helpers). Treat “independent” as **independent of domain and HTTP** — not “no internal imports at all.”

4. **Services orchestrate**  
   `src/services` connects domain rules to persistence and integrations without exposing FastAPI types.

5. **Core stays small**  
   If `src/core` grows domain-ish logic, move that logic into `src/domain` or `src/services`.

---

## Import boundaries (summary)

| Layer | May import |
|-------|------------|
| **api** | `domain`, `services`, `infrastructure`, `core` |
| **services** | `domain`, `infrastructure`, `core` |
| **domain** | `core` only (sparingly) |
| **infrastructure** | `core` only (plus third-party / stdlib) |
| **core** | stdlib + third-party only |

Violations (e.g. `domain` importing SQLAlchemy session types from `infrastructure`) should be refactored behind interfaces or moved to `services`.

---

## Anti-corruption layer — PAMS

**PAMS** (legacy Azure MySQL read model) is isolated in **`src/infrastructure/pams_database.py`**.

- That module owns async engine/session setup, SSL, and table reflection for PAMS; it reads **`src.core.config.settings`** for URLs and CA paths only.
- **No PAMS driver or connection string handling** should appear in `src/api` or `src/domain`. Callers in higher layers use narrow functions or repository-style accessors exposed from infrastructure (or services that depend on those helpers).
- **Writes** to PAMS are not performed; the module docstring states read-only usage and that the primary QGP store is PostgreSQL.
- If PAMS schema or connectivity changes, update **one place** (`pams_database.py` and adjacent infra tests) rather than spreading MySQL-specific details across the codebase.

This is a classic **anti-corruption layer**: the rest of the app sees stable, app-owned abstractions; PAMS remains a bounded external model.

---

## Extension points

| Need | Add to |
|------|--------|
| New REST resource or route group | `src/api/routes/` and register in `src/api/__init__.py` |
| New HTTP-specific schema or error mapping | `src/api/schemas/`, `src/api/utils/`, `src/api/middleware/` |
| New business rule or entity | `src/domain/` |
| New use case spanning DB and rules | `src/services/` |
| New DB table, migration, external client, or middleware implementation | `src/infrastructure/` |
| Shared non-domain helper (logging, IDs, pagination types) | `src/core/` |

When adding a feature, prefer **domain + service + api route** over putting logic in routers or infrastructure.

---

## References

- Application wiring: `src/main.py`
- PAMS integration: `src/infrastructure/pams_database.py`
- API structure: `docs/api/style-guide.md`
