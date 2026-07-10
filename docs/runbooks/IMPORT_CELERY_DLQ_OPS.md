# Import + Celery + DLQ Operations Runbook

**Module**: External audit import, Celery workers, dead-letter queue  
**IDs**: WCS-B05  
**Version**: 1.0  
**Last Updated**: 2026-07-10

---

## Overview

This runbook covers day-2 operations for:

1. **External audit import** jobs (Celery-backed)
2. **Celery** broker/worker health
3. **DLQ** (dead-letter queue) inspection, retry, and purge

Use it when imports stall, workers are quiet, or failed tasks accumulate.

Related policy: [`scripts/conveyor_policy.md`](../../scripts/conveyor_policy.md) (production promote requires Redis + Celery readiness).

---

## 1. Quick health checks

```bash
# Liveness
curl -sS "$APP_URL/healthz" | jq .

# Readiness (DB + Redis; push/VAPID is informational only)
curl -sS "$APP_URL/readyz" | jq .
curl -sS "$APP_URL/api/v1/health/readyz" | jq '.checks | {database,redis,push,vapid}'

# Deploy identity
curl -sS "$APP_URL/api/v1/meta/version" | jq .
```

**Expect**:

| Signal | Healthy | Action if bad |
|--------|---------|---------------|
| `/healthz` → 200 | Process up | Restart app service |
| `/readyz` → 200, `redis=connected` | Broker path OK | Fix `REDIS_URL` / Key Vault; do not promote |
| `build_sha` matches intended tip | Correct release | Wait for deploy cutover |

---

## 2. Celery worker ops

### Required env (production / staging with imports)

- `REDIS_URL`
- `CELERY_BROKER_URL` (must not be empty or localhost in prod)
- `CELERY_RESULT_BACKEND`

Startup validation lives in `src/core/config.py` (`_validate_redis_celery_requirements`).

### Confirm workers

```bash
# On the worker host / container
celery -A src.infrastructure.tasks.celery_app.celery_app inspect ping
celery -A src.infrastructure.tasks.celery_app.celery_app inspect active
celery -A src.infrastructure.tasks.celery_app.celery_app inspect reserved
```

### Common import task

- Module: `src/infrastructure/tasks/external_audit_import_tasks.py`
- API surface: `src/api/routes/external_audit_imports.py`

If an import stays `pending` / `running` with no progress:

1. Confirm Redis connectivity via `/readyz`
2. Confirm at least one worker responds to `inspect ping`
3. Check app + worker logs for the import job id
4. Check DLQ (section 3) for permanent failures after retries

---

## 3. Dead-letter queue (DLQ)

Failed Celery tasks (retries exhausted) are persisted by `src/infrastructure/tasks/dlq.py` into `FailedTask` and exposed via admin API.

### Depth thresholds (code)

| Depth | Severity | Signal |
|------:|----------|--------|
| ≥ 10 | Warning | `dlq.alert` metric severity=warning |
| ≥ 50 | Critical | `dlq.alert` metric severity=critical |

### List entries (superuser)

```bash
# Auth: platform admin / superuser bearer token
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$APP_URL/api/v1/admin/dlq?limit=50&retried=false" | jq .
```

### Retry one entry

```bash
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  "$APP_URL/api/v1/admin/dlq/$ENTRY_ID/retry" | jq .
```

Re-dispatch uses `celery_app.send_task(entry.task_name, args=...)`. Confirm the worker is up before retrying a burst.

### Automated replay

Periodic task: `src.infrastructure.tasks.dlq_replay.replay_failed_tasks`  
Marks each un-retried entry `retried=True` after dispatch (at most once per entry via this path).

### Purge

```bash
# Default: purge already-retried only
curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
  "$APP_URL/api/v1/admin/dlq?retried_only=true" | jq .

# Dangerous: purge all (including unretried)
curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
  "$APP_URL/api/v1/admin/dlq?retried_only=false" | jq .
```

---

## 4. Import incident playbook

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Import never leaves queued | No Celery worker / bad broker URL | Fix Key Vault Celery URLs; scale worker; re-queue |
| `/readyz` 503 `redis=not_configured` | Missing Redis in env | Set `REDIS_URL`; staging/prod require it when imports enabled |
| Tasks fail then vanish from active | Retries exhausted → DLQ | List DLQ; fix root cause; retry entry |
| Retry returns 409 | Entry already retried | Inspect logs; create a fresh job if needed |
| Retry returns 500 | Worker/broker down or bad args | Fix worker; check stored `args`/`kwargs` |

---

## 5. Staging evidence pack (minimum)

Before calling an import/Celery change “verified on staging”:

1. `GET /api/v1/meta/version` → expected `build_sha`
2. `GET /readyz` → 200 with `redis=connected`
3. Worker `inspect ping` → pong
4. Controlled import (or dry-run) completes or fails with an honest status
5. If failure: DLQ list shows the task; retry once after fix; confirm `retried=true`

Attach outputs (redacted) to the PR Evidence Pack / release notes.

---

## 6. Production promote gate (conveyor)

From conveyor policy — do **not** promote unless:

- Staging `build_sha` matches signed `main`
- Security Scan / Trivy green
- Redis + Celery configured for prod (Key Vault)
- `docs/evidence/release_signoff.json` updated to that SHA

After promote: re-run section 1 + a DLQ depth check (`retried=false` total near zero or explained).

---

## 7. Rollback

| Change type | Rollback |
|-------------|----------|
| Bad worker image | Redeploy previous known-good app/worker SHA |
| Bad broker URL | Restore prior Key Vault secret; restart workers |
| Bad retry storm | Stop automated replay; purge only after root-cause fix |

No DB schema change is required for normal DLQ ops; `FailedTask` rows are operational data.

---

## References

- `src/infrastructure/tasks/dlq.py` — failure persistence + depth alerts
- `src/infrastructure/tasks/dlq_replay.py` — automated replay
- `src/api/routes/dlq_admin.py` — list / retry / purge API
- `src/infrastructure/tasks/celery_app.py` — Celery app + Redis SSL normalization
- `src/infrastructure/tasks/external_audit_import_tasks.py` — import jobs
- `docs/runbooks/ETL_OPERATIONS_RUNBOOK.md` — ETL-specific import path
- `scripts/conveyor_policy.md` — merge / promote rules
