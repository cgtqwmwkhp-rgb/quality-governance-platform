# Schema Versioning & Migrations (D12)

This guide describes how database schema changes are managed with **Alembic**, **async SQLAlchemy**, and **PostgreSQL**, and how to keep migrations safe in development and CI.

---

## Alembic setup

| Item | Location / behaviour |
|------|----------------------|
| **Config** | `alembic.ini` — `script_location = alembic` |
| **Environment** | `alembic/env.py` — imports all models (`from src.domain.models import *`) and `Base.metadata` for autogenerate; overrides `sqlalchemy.url` from application settings |
| **Async PostgreSQL** | Online migrations use `async_engine_from_config` + `connection.run_sync(do_run_migrations)` so revisions run against **asyncpg**-compatible URLs |
| **Offline mode** | `run_migrations_offline()` emits SQL without a live connection (useful for review or SQL packaging) |
| **Revision chain** | Each file in `alembic/versions/` sets `revision` and `down_revision` (or merge metadata) to form a single linear or branched history resolved to **one head** before deploy |

---

## Migration naming convention

**Target convention:** `YYYYMMDD_description.py` (date prefix + short slug), for example:

`20260321_add_investigation_version_index.py`

**Note:** The repository `alembic.ini` may also define a `file_template` that includes a timestamp and revision id. When generating new revisions, prefer the **YYYYMMDD_description** pattern for human scanability; keep `revision` identifiers unique (Alembic may use a hash or custom id inside the file).

---

## Writing migrations

1. **Prefer explicit DDL** where autogenerate misses intent (constraints, renames, data backfills). Use `op.create_table`, `op.add_column`, `op.create_index`, `op.create_foreign_key`, etc., or `op.execute()` for raw SQL when necessary.  
2. **`op.execute()`**  
   - Use for statements that have no first-class Alembic operation.  
   - **Split** multiple PostgreSQL statements into separate `op.execute()` calls (or use a transaction-safe script) to avoid driver/parser edge cases.  
3. **Asyncpg / multiple statements**  
   - Putting several commands in a single `op.execute()` string can fail or behave unexpectedly with **asyncpg**; prefer one statement per execute or use Alembic’s built-in operations.  
4. **Reversibility**  
   - Implement `downgrade()` for every `upgrade()` unless the change is intentionally irreversible (document why).  
   - Test **upgrade → downgrade → upgrade** locally before opening a PR.  
5. **Data migrations**  
   - Backfill in batches for large tables; avoid long locks in production windows.  
6. **Naming**  
   - Use explicit constraint and index names (`op.create_unique_constraint("uq_...", ...)` ) to simplify later drops.

---

## CI checks

Recommended pipeline sequence against a disposable PostgreSQL database:

1. `alembic upgrade head`  
2. `alembic downgrade -1`  
3. `alembic upgrade head`  

This catches broken `down_revision` links, non-reversible steps, and incompatible DDL early. Optionally add application smoke tests or ORM metadata comparison after step 1.

---

## Migration squash strategy

When **20+** incremental migrations accumulate (especially noisy autogenerate drafts):

1. **Freeze** production on the current head.  
2. Generate a **baseline** migration that represents the full schema (or squash intermediate steps into one revision).  
3. **Archive** old revision files per org policy (keep them in git history).  
4. Document the squash point and require fresh clones to `alembic upgrade head` from the new baseline only.  

Squashing is disruptive for long-lived branches; coordinate with all teams and backup/restore procedures.

---

## Common pitfalls

| Pitfall | Mitigation |
|---------|------------|
| **Multiple statements in one `op.execute()` with asyncpg** | One statement per call; or use Alembic operations |
| **Multiple heads** | Run `alembic heads`; merge with a merge revision so only **one head** exists before deploy |
| **Broken `down_revision` chain** | Visualise with `alembic history`; fix parent revision id |
| **Autogenerate noise** | Review diffs; do not commit unintended drops/renames |
| **Missing model import** | Ensure new models are imported in `alembic/env.py` (via package `__init__`) so metadata is complete |
| **Dropping columns with data** | Export/archive data first; use multi-phase deploy (add new → backfill → switch → drop old) |

---

## Emergency rollback

1. **Stop** application traffic to the affected instance (or fail over) if the migration may have left the schema inconsistent.  
2. Run **`alembic downgrade -1`** (or to a known good revision) from the same code version that matches that migration’s `downgrade()` implementation.  
3. **Verify data integrity**: spot-check critical tables, foreign keys, and application health endpoints.  
4. **Restore from backup** if downgrade is unsafe or data corruption is suspected.  
5. **Post-incident**: add a corrective migration and extend CI with the triple-step checks above.

---

## Related documents

- [Data model guide](./data-model-guide.md)  
- [Data integrity](./data-integrity.md)
