# Runbook: Database Recovery

**Owner**: Platform Engineering
**Last Updated**: 2026-03-07
**Review Cycle**: Quarterly

---

## 1. Trigger Conditions

- `/readyz` returning 503 with `"database": "disconnected"`
- Application logs showing `asyncpg.PostgresError` or connection pool exhaustion
- Azure Database for PostgreSQL service health alert
- Data corruption detected (audit trail hash-chain verification failure)
- Accidental data deletion or incorrect migration

## 2. Severity Assessment

| Scenario | Severity | Data Risk |
|----------|----------|-----------|
| Connection timeout (transient) | SEV-3 | None — pool auto-recovers |
| Connection pool exhaustion | SEV-2 | None — requires app restart |
| Database server unreachable | SEV-1 | None if transient; high if persistent |
| Data corruption | SEV-1 | HIGH — stop writes immediately |
| Accidental data deletion | SEV-1 | HIGH — restore from backup |

## 3. Diagnostic Steps

### 3.1 Connectivity
- Check Azure Database for PostgreSQL status in Azure Portal
- Verify network security group rules allow App Service → DB traffic
- Check connection pool metrics: `db.pool_size`, `db.pool_checkedout`, `db.pool_overflow`

### 3.2 Performance
- Check `db.query_duration_ms` in Azure Monitor
- Look for long-running queries: `SELECT * FROM pg_stat_activity WHERE state = 'active' AND duration > interval '30 seconds'`
- Check for lock contention: `SELECT * FROM pg_locks WHERE NOT granted`

### 3.3 Data Integrity
- Run audit trail verification: `GET /api/v1/audit-trail/verify`
- Check for orphaned records: foreign key constraint validation
- Compare record counts with expected baselines

## 4. Recovery Procedures

### 4.1 Connection Pool Exhaustion
1. Restart the application (forces pool recreation)
2. If recurring, check for connection leaks in application code
3. Consider increasing `pool_size` (currently 10) or `max_overflow` (currently 20)

### 4.2 Database Server Unreachable
1. Check Azure service health for PostgreSQL
2. If regional outage: activate geo-redundant replica (if configured)
3. If maintenance: wait for completion; application will auto-recover via `pool_pre_ping`
4. If persistent: contact Azure Support (SEV-A ticket)

### 4.3 Point-in-Time Recovery (Data Loss/Corruption)
1. **Stop writes**: Set UAT_MODE=READ_ONLY in production environment variables as a temporary protection control
2. **Identify recovery point**: Determine the last known good timestamp
3. **Azure PITR**: Azure Portal → PostgreSQL → Point-in-Time Restore
   - Select target timestamp (up to 35 days back)
   - Restore to new server instance
4. **Validate restored data**: Connect to restored instance; verify data integrity
5. **Swap connection**: Update DATABASE_URL in Key Vault to point to restored instance
6. **Restart application**: Deploy restart to pick up new connection string
7. **Re-enable writes**: Restore UAT_MODE=READ_WRITE for normal production operation

### 4.4 Migration Rollback
1. Identify the problematic migration from `alembic history`
2. Check if the migration has a `downgrade()` function
3. If reversible: `alembic downgrade -1`
4. If not reversible: PITR recovery (section 4.3)

## 5. Pre-Production Backup Verification

Production deployment workflow (`deploy-production.yml`) triggers a database backup before every deployment. Verify backup exists:

1. Azure Portal → PostgreSQL → Backups
2. Confirm most recent backup is within deployment window
3. Verify backup completion status (not in-progress)

## 6. Post-Recovery

1. Verify `/readyz` returns 200 with `"database": "connected"`
2. Run smoke tests against recovered database
3. Check audit trail integrity
4. Document incident: timeline, data loss scope (if any), recovery time
5. Review backup retention policy (currently: Azure default 7-35 days)
