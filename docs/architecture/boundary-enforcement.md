# Architectural Boundary Enforcement

How the Quality Governance Platform enforces layer-based import boundaries at CI time.

---

## Why Layer Boundaries

The platform follows **Domain-Driven Design (DDD) with Clean Architecture**. The domain layer contains shared entities, value objects, and business rules that multiple services and API routes depend on. Layer-based boundaries are the correct enforcement choice here because:

- The **domain model is shared** across features — slicing by feature would fragment entities (e.g., `Incident`, `Tenant`, `User`) that intentionally span multiple use cases.
- Clean Architecture's dependency rule — **dependencies point inward** — maps directly to layer-based import restrictions.
- Feature-based boundaries would add overhead without benefit in a service that exposes a single bounded context with a unified domain model.

---

## Layer Dependency Diagram

```
  ┌──────────┐
  │   api    │   ← HTTP/WebSocket interface (FastAPI routers)
  └────┬─────┘
       │ imports
       ▼
  ┌──────────┐
  │ services │   ← Application / use-case layer
  └────┬─────┘
       │ imports
       ▼
  ┌──────────┐         ┌──────────────────┐
  │  domain  │ ◄───────│  infrastructure  │
  └──────────┘         └──────────────────┘
       ▲                    │
       └────────────────────┘
         infrastructure implements
         domain interfaces (ports)
```

**Allowed direction:** `api → services → domain ← infrastructure`

**Forbidden direction:** Inner layers must never import from outer layers (domain must not reach into api; services must not reach into api).

---

## Import Rules

Enforced by [`scripts/check_import_boundaries.py`](../../scripts/check_import_boundaries.py):

| # | Source Layer | Forbidden Import | Allowlist | Rationale |
|---|-------------|-----------------|-----------|-----------|
| 1 | `src/domain` | `src.api` | — | Domain must never depend on the transport/presentation layer |
| 2 | `src/domain` | `src.infrastructure` | `resilience`, `cache`, `monitoring`, `storage`, `websocket`, `tasks` | Domain should not depend on infrastructure; allowlisted modules provide cross-cutting concerns that the domain consumes via thin interfaces |
| 3 | `src/core` | `src.api` | — | Core utilities must remain transport-agnostic |
| 4 | `src/core` | `src.infrastructure` | — | Core must not couple to infrastructure implementations |
| 5 | `src/services` | `src.api` | — | Service layer must not depend on API/transport layer; keeps use cases reusable across different interfaces |

### Infrastructure Allowlist for Domain

Rule 2 permits `src/domain` to import from specific `src.infrastructure` sub-packages:

| Allowed Module | Justification |
|----------------|---------------|
| `src.infrastructure.resilience` | Circuit breaker and retry decorators applied to domain operations |
| `src.infrastructure.cache` | Caching interfaces consumed by domain services |
| `src.infrastructure.monitoring` | Metrics and tracing hooks for domain events |
| `src.infrastructure.storage` | Storage abstractions for domain artifacts |
| `src.infrastructure.websocket` | Real-time notification interfaces |
| `src.infrastructure.tasks` | Background task dispatch used by domain workflows |

These allowlisted modules expose **thin interfaces or decorators** that the domain layer consumes without coupling to concrete infrastructure (e.g., specific cache backends or message brokers).

---

## CI Enforcement

The boundary check runs as the **`import-boundary-check`** job in the CI pipeline:

1. The script walks all `.py` files under `src/domain`, `src/core`, and `src/services`.
2. It parses each file's AST to extract `import` and `from ... import` statements.
3. Each import is checked against the rules table above.
4. If any violation is found, the job exits with code **1** and prints every offending import with file path and rule context.
5. On success, the job prints `OK: All import boundaries respected` and exits **0**.

This runs on **every pull request**, preventing boundary violations from reaching `main`.

---

## Related Documents

- [`scripts/check_import_boundaries.py`](../../scripts/check_import_boundaries.py) — enforcement script
- [`docs/architecture/adr/`](adr/) — architecture decision records
- [`docs/architecture/resilience-patterns.md`](resilience-patterns.md) — resilience patterns (allowlisted infrastructure)
