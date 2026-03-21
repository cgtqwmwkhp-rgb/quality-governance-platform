# Architecture (D22)

High-level architecture of the Quality Governance Platform: components, layering, decisions, dependencies, stack, API shape, and request lifecycle.

## System architecture (ASCII)

```
                                    +------------------+
                                    |   Users / SSO    |
                                    +--------+---------+
                                             |
                                             v
+------------------+              +----------------------+              +-------------------+
|  Frontend SPA    |   HTTPS      |  API Gateway /     |   HTTPS      |  FastAPI Backend |
|  (React + Vite)  +------------->|  TLS Termination   +------------->|  (Python 3.11)   |
+------------------+              |  (e.g. Azure FW,   |              +---------+---------+
        |                         |   App Gateway)     |                        |
        |                         +--------------------+                        |
        |                                                                        |
        | Web Vitals / telemetry (JSON)                                          |
        v                                                                        v
+------------------+                                                    +--------+---------+
|  Static hosting  |                                                    |  Domain services|
|  (e.g. Azure SWA)|                                                    |  + API routes     |
+------------------+                                                    +--------+---------+
                                                                                 |
                    +------------------------------------------------------------+
                    |
        +-----------+-----------+---------------+---------------+----------------+
        |           |           |               |               |                |
        v           v           v               v               v                v
+---------------+ +-------+ +----------+ +-------------+ +-----------+ +------------------+
|  PostgreSQL   | | Redis | | Azure    | | PAMS DB     | |  Celery   | |  OpenTelemetry   |
|  (primary)    | | cache | | Blob     | | (read-only  | |  workers  | |  export to       |
|               | | /broker| | storage | |  external)  | |  + broker | |  Azure Monitor   |
+---------------+ +-------+ +----------+ +-------------+ +-----------+ +------------------+
```

## Layer architecture

| Layer | Responsibility | Primary location |
|-------|----------------|------------------|
| **Presentation** | SPA routing, UI, i18n, client validation, telemetry beacons | `frontend/src` |
| **API** | HTTP routing, auth dependencies, request validation, OpenAPI | `src/api` |
| **Domain** | Business rules, services, aggregates, audit helpers | `src/domain` |
| **Infrastructure** | DB session, Redis, Azure, PAMS, monitoring, middleware | `src/infrastructure` |

Flow: React calls versioned REST endpoints under `/api/v1`; FastAPI routes delegate to domain services; services persist via SQLAlchemy/async sessions and integrate infrastructure adapters (cache, blob, external DB).

## Key architectural decisions (ADRs)

Decisions are recorded as lightweight ADRs under `docs/adr/`. The following nine capture the current baseline (create or update the files if not yet present):

| ADR | Topic | Path |
|-----|--------|------|
| ADR-001 | FastAPI + async SQLAlchemy for the API and persistence | `docs/adr/001-fastapi-async-sqlalchemy.md` |
| ADR-002 | React SPA with Vite and Tailwind for the presentation tier | `docs/adr/002-react-vite-tailwind.md` |
| ADR-003 | PostgreSQL as system of record; Alembic for migrations | `docs/adr/003-postgresql-alembic.md` |
| ADR-004 | Redis for cache, rate limiting, and Celery broker/backing store | `docs/adr/004-redis-cache-and-tasks.md` |
| ADR-005 | Azure Blob for document and artifact storage | `docs/adr/005-azure-blob-storage.md` |
| ADR-006 | Multi-tenant isolation and permission model | `docs/adr/006-tenant-isolation-and-rbac.md` |
| ADR-007 | OpenTelemetry + Azure Monitor / Application Insights | `docs/adr/007-otel-azure-monitor.md` |
| ADR-008 | PAMS integration as optional read-only external data source | `docs/adr/008-pams-external-database.md` |
| ADR-009 | REST API versioning (`/api/v1`) and OpenAPI as contract | `docs/adr/009-api-versioning-openapi.md` |

## Module dependency graph (high level)

```
frontend (React)
    --> HTTP/JSON --> src.api.routes.*
                            |
                            v
                    src.domain.services.*
                            |
              +-------------+-------------+
              |             |             |
              v             v             v
    src.infrastructure.database   src.infrastructure.cache   src.infrastructure.monitoring
              |             |             |
              v             v             v
         PostgreSQL       Redis      Azure Monitor / logs
```

Celery workers consume tasks published via the broker (Redis) and reuse domain/infrastructure code paths where packaged for worker execution.

## Technology stack (representative versions)

| Area | Technology | Version / notes |
|------|------------|-----------------|
| Runtime | Python | 3.11+ (see repository tooling) |
| API | FastAPI, Uvicorn, Starlette | `requirements.txt` pins/ranges |
| Validation | Pydantic v2 | `>=2.5,<3` |
| ORM | SQLAlchemy | 2.0.x |
| Migrations | Alembic | 1.13.x |
| DB drivers | asyncpg, psycopg2-binary | Per `requirements.txt` |
| Cache / queue | Redis, Celery | Per `requirements.txt` |
| Storage | Azure Blob SDK | `azure-storage-blob` |
| Observability | OpenTelemetry API/SDK, Azure exporter | Per `requirements.txt` |
| Frontend | React, react-router-dom | `frontend/package.json` (^18.2, ^6.20) |
| Build | Vite, TypeScript | ^5.0, ^5.9 |
| Styling | Tailwind CSS | ^3.3 |
| i18n | i18next, react-i18next, browser language detector | ^23 / ^14 / ^8 |
| Client HTTP | axios | ^1.7 |

## API architecture

- **Style**: REST over HTTPS with resource-oriented routes grouped under **`/api/v1`** (see `src/main.py` router include).
- **Contract**: OpenAPI 3 served at `/openapi.json`; interactive docs at `/docs` and `/redoc` when enabled.
- **Cross-cutting**: Middleware for request IDs, security headers, gzip, rate limiting, idempotency, CORS, and structured request logging.
- **Errors**: Unified error envelope via global exception handlers (`src/api/middleware/error_handler.py`).

## Data flow (request lifecycle)

1. **Client** issues an authenticated request (typically `Authorization: Bearer …`) to `/api/v1/...`.
2. **Edge / gateway** terminates TLS and forwards to the app service or container host.
3. **FastAPI** runs middleware (state, security headers, logging, rate limit, idempotency) then matches a route in `src/api/routes`.
4. **Dependencies** resolve `DbSession`, `CurrentUser`, and other providers; JWT or equivalent identity is validated.
5. **Route handler** validates request bodies with Pydantic schemas and calls a **domain service**.
6. **Service** applies business rules, writes/reads through SQLAlchemy, may **invalidate Redis cache** or **enqueue Celery** work, and may emit **metrics** via OpenTelemetry helpers.
7. **Response** is serialized to JSON; observability spans and structured logs correlate via request ID.
8. **Async work** (Celery) updates state, sends notifications, or processes files; results observed via logs, metrics, and dashboards defined in [`docs/observability/alerting-rules.md`](observability/alerting-rules.md).
