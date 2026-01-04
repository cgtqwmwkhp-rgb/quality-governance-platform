# Database Migration Runbook

**Purpose**: Safe, repeatable database schema changes using Alembic  
**Audience**: DevOps, SRE, Release Engineers  
**Last Updated**: 2026-01-04

---

## Prerequisites

- Database backup completed and verified
- Application downtime window scheduled (if required)
- Migration tested in staging environment
- Rollback plan prepared

---

## Migration Workflow

### 1. Pre-Migration Checks

```bash
# Verify database connectivity
python3 -c "from src.infrastructure.database import engine; import asyncio; asyncio.run(engine.connect())"

# Check current migration version
alembic current

# Verify pending migrations
alembic history
```

**Expected Output**: Current version should match production state

---

### 2. Backup Database

```bash
# PostgreSQL backup
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME -F c -f backup_$(date +%Y%m%d_%H%M%S).dump

# Verify backup
pg_restore --list backup_*.dump | head -20
```

**Critical**: Do not proceed without verified backup

---

### 3. Apply Migrations

```bash
# Dry-run (show SQL without executing)
alembic upgrade head --sql > migration_$(date +%Y%m%d_%H%M%S).sql
cat migration_*.sql  # Review SQL

# Apply migrations
alembic upgrade head

# Verify new version
alembic current
```

**Expected Output**: 
```
INFO  [alembic.runtime.migration] Running upgrade <old> -> <new>
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
```

---

### 4. Post-Migration Validation

```bash
# Check database schema
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "\dt"

# Run application health check
curl http://localhost:8000/readyz

# Check application logs for errors
tail -f logs/app.log | grep -i error
```

**Expected Output**: 
- `/readyz` returns `{"status": "ready", "database": "connected"}`
- No database connection errors in logs

---

## Rollback Procedure

### Option 1: Alembic Downgrade (Preferred)

```bash
# Downgrade one version
alembic downgrade -1

# Downgrade to specific version
alembic downgrade <revision_id>

# Verify version
alembic current
```

### Option 2: Database Restore (Last Resort)

```bash
# Stop application
systemctl stop quality-governance-platform

# Restore database
pg_restore -h $DB_HOST -U $DB_USER -d $DB_NAME -c backup_*.dump

# Restart application
systemctl start quality-governance-platform

# Verify health
curl http://localhost:8000/healthz
```

---

## Common Issues

### Issue: Migration Fails Mid-Way

**Symptoms**: `alembic upgrade` exits with error

**Resolution**:
1. Check error message for SQL syntax or constraint violations
2. Manually fix database state if needed
3. Mark migration as applied: `alembic stamp <revision_id>`
4. Re-run upgrade

### Issue: Application Can't Connect After Migration

**Symptoms**: `/readyz` returns 500, logs show connection errors

**Resolution**:
1. Verify database is running: `pg_isready -h $DB_HOST`
2. Check connection string in `.env`
3. Verify database user permissions
4. Restart application

### Issue: Migration Takes Too Long

**Symptoms**: Migration hangs or times out

**Resolution**:
1. Check for locks: `SELECT * FROM pg_locks WHERE NOT granted;`
2. Kill blocking queries if safe
3. Consider breaking migration into smaller steps
4. Schedule during maintenance window

---

## Migration Checklist

**Before Migration**:
- [ ] Backup database and verify restore
- [ ] Test migration in staging
- [ ] Review generated SQL
- [ ] Schedule downtime if needed
- [ ] Notify stakeholders

**During Migration**:
- [ ] Stop application (if downtime required)
- [ ] Apply migrations
- [ ] Verify migration version
- [ ] Start application
- [ ] Run health checks

**After Migration**:
- [ ] Monitor application logs
- [ ] Monitor database performance
- [ ] Verify critical functionality
- [ ] Document any issues
- [ ] Notify stakeholders of completion

---

## Emergency Contacts

- **Database Team**: [Contact Info]
- **On-Call Engineer**: [Contact Info]
- **Escalation**: [Contact Info]

---

## References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL Backup Documentation](https://www.postgresql.org/docs/current/backup.html)
- [ADR-0001: Migration Discipline](../adrs/ADR-0001-migration-discipline-and-ci-strategy.md)
