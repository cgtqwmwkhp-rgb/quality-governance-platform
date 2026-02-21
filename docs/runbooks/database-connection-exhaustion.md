# Runbook: Database Connection Exhaustion

## Alert
- **Source:** Azure Monitor / PostgreSQL metrics
- **Severity:** High
- **Symptom:** 503 responses, /readyz returns unhealthy

## Diagnosis

1. Check current connection count:
   ```sql
   SELECT count(*) FROM pg_stat_activity WHERE datname = 'qgp_production';
   ```

2. Check for long-running queries:
   ```sql
   SELECT pid, now() - pg_stat_activity.query_start AS duration, query
   FROM pg_stat_activity
   WHERE state = 'active' AND now() - pg_stat_activity.query_start > interval '5 minutes';
   ```

3. Check app pool settings in application logs

## Resolution

1. Kill long-running queries if safe:
   ```sql
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
   WHERE state = 'active' AND now() - query_start > interval '10 minutes';
   ```

2. Restart the application to reset the connection pool
3. If recurring, increase `pool_size` in database configuration

## Prevention
- Connection pool is configured with `pool_size=10, max_overflow=20`
- Monitor via `/readyz?verbose=true` database check
