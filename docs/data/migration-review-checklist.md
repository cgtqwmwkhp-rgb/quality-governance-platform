# Migration Review Checklist (D12)

Checklist for reviewing Alembic database migration PRs.

## Pre-Merge Checklist

### Naming & Structure
- [ ] Migration filename follows `YYYYMMDD_descriptive_name.py` convention
- [ ] Revision ID is unique and not a duplicate
- [ ] `down_revision` chain is correct (no orphans or forks)
- [ ] Migration imports only from `alembic` and `sqlalchemy` (no app model imports for schema migrations)

### Schema Safety
- [ ] No `DROP TABLE` or `DROP COLUMN` without prior deprecation period
- [ ] `ALTER TABLE ADD COLUMN` uses `nullable=True` or provides a `server_default`
- [ ] Index creation uses `IF NOT EXISTS` where supported
- [ ] Large table alterations account for lock duration (< 30s on expected table size)
- [ ] No mixing of schema changes and data changes in the same migration

### Data Migrations
- [ ] Data migration is in a separate file from schema changes
- [ ] Batch processing used for large datasets (not single UPDATE for millions of rows)
- [ ] `downgrade()` is implemented and tested (or explicitly documented as irreversible)
- [ ] No hardcoded IDs or values that vary by environment

### Testing
- [ ] Migration tested on a fresh database (`alembic upgrade head` from scratch)
- [ ] Migration tested as an incremental upgrade from the previous revision
- [ ] Rollback tested (`alembic downgrade -1`)
- [ ] No data loss on upgrade + downgrade cycle

### Performance
- [ ] Estimated execution time documented for large tables
- [ ] Concurrent index creation (`CREATE INDEX CONCURRENTLY`) used where applicable
- [ ] Statement timeout considerations for long-running migrations

## Post-Merge Verification

- [ ] Migration applied successfully in staging
- [ ] Application health checks pass after migration
- [ ] No unexpected locks or query performance degradation
- [ ] Alembic `current` shows expected revision

## Related Documents

- [`alembic/versions/`](../../alembic/versions/) — migration files
- [`scripts/validate_migration_naming.py`](../../scripts/validate_migration_naming.py) — naming lint
- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) — `migration-naming-lint` job
