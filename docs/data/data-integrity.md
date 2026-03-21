# Data Integrity & Consistency (D24)

This guide describes platform patterns for concurrency, idempotency, referential integrity, transactions, asynchronous work, validation, and tamper-evident auditing.

---

## Optimistic locking

- **Investigation** domain rows are stored in **`investigation_runs`**.  
- The **`InvestigationRun`** model includes a **`version`** integer column (default `1`) intended for **optimistic locking** on concurrent updates.  
- **Service / API contract**: updates should accept an **expected version** (or equivalent `If-Match` semantics), compare it to the persisted row, reject stale writes (**409 Conflict**), and **increment** `version` on successful commits.  
- Align route handlers and Pydantic update schemas with this pattern wherever collaborative editing is required.

---

## Idempotency

- **`IdempotencyMiddleware`** (`src/api/middleware/idempotency.py`) intercepts **POST**, **PUT**, and **PATCH** when the client sends **`Idempotency-Key`**.  
- Responses are cached in **Redis** with a **24-hour TTL** (`86400` seconds).  
- Request bodies are hashed (**SHA-256**); the same key with a **different payload** returns **409** (`IDEMPOTENCY_CONFLICT`).  
- If Redis is unavailable, requests proceed **without** caching (degraded but available behaviour).

---

## Referential integrity

- **PostgreSQL foreign keys** enforce parent/child relationships for core entities (examples: `incident_actions.incident_id` → `incidents.id`, `audit_findings.run_id` → `audit_runs.id`).  
- **`ON DELETE CASCADE`** is used where child rows must not outlive the parent (many action and template-child tables).  
- **`ON DELETE SET NULL`** is used where the child row should survive but clear the link (nullable FKs).  
- Prefer explicit policies in migrations so behaviour is visible in code review.

---

## Unique constraints

- **Reference numbers**: models using **ReferenceNumberMixin** enforce unique `reference_number` per table.  
- **User identity**: `users.email` is unique.  
- **Compound / business uniqueness**: enforced where declared (e.g. junction tables with composite primary keys, `evidence_assets` storage keys, optional `complaints.external_ref`).  
- Add **partial unique indexes** in PostgreSQL when only a subset of rows must be unique (e.g. “one open run per template” patterns).

---

## Transaction boundaries

- Use **`async with session.begin():`** (or the project’s equivalent `async with db.begin()`) for **multi-step** operations that must commit or roll back atomically.  
- Avoid long transactions across external HTTP calls; commit database work first, then call external systems, or use outbox/saga patterns where needed.

---

## Eventual consistency

- **Celery** (`src/infrastructure/tasks/celery_app.py`) runs **asynchronous** tasks (email, notifications, reports, cleanup, retention).  
- Tasks use **retries** with backoff; failures after `task_max_retries` should be routed to **monitoring** and, where configured, a **dead-letter queue (DLQ)** or failed-job store for manual replay.  
- Treat worker success as **eventually consistent** with the API: UI and APIs should tolerate short lag and expose job/status endpoints where users need certainty.

---

## Data validation

- **Pydantic** schemas under `src/api/schemas/` validate API inputs (types, lengths, enums).  
- **SQLAlchemy** columns enforce nullability, lengths, and enum/storage types at persistence.  
- Prefer **one source of truth** for enums (shared constants or enums imported into both ORM and Pydantic) to avoid drift.

---

## Audit trail (hash chain)

- **`AuditLogService`** (`src/domain/services/audit_log_service.py`) appends **immutable** `AuditLogEntry` rows with a **cryptographic hash chain** (each entry hashes the previous entry’s hash and payload fields).  
- **`AuditLogEntry.compute_hash`** ties **sequence**, **previous hash**, entity identifiers, action, user, timestamp, and optional value snapshots.  
- **Verification API**: `POST` **`/verify`** on the audit-trail router (`src/api/routes/audit_trail.py`) recomputes hashes for a sequence range and records a **`AuditLogVerification`** result.  
- Use this endpoint for **tamper detection** and compliance evidence; store verification results for audit packs.

---

## Related documents

- [Data model guide](./data-model-guide.md)  
- [Migration guide](./migration-guide.md)  
- [Data classification policy](../privacy/data-classification.md)
