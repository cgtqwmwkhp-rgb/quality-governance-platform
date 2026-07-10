# Celery Worker + Beat Deploy Plan (W-01)

**Status**: Infra + deploy wiring landed; runtime workers activate after App Service sites are provisioned.  
**Related**: [`IMPORT_CELERY_DLQ_OPS.md`](./IMPORT_CELERY_DLQ_OPS.md), `infra/main.bicep`, `scripts/infra/provision-celery-workers.sh`

## Why

API App Service sets `CELERY_BROKER_URL` / `REDIS_URL` but historically only ran `uvicorn`. Enqueued email/webhook/push/import tasks never drained. This package adds:

| Artifact | Role |
|----------|------|
| `scripts/celery/start_worker.sh` | Worker entrypoint (+ honest `/healthz` tied to Celery PID) |
| `scripts/celery/start_beat.sh` | Beat entrypoint (+ honest `/healthz` tied to beat PID) |
| `infra/main.bicep` | `${prefix}-worker` / `${prefix}-beat` sites on API plan |
| `scripts/infra/provision-celery-workers.sh` | Create sites against an existing API plan |
| `scripts/infra/deploy_celery_apps.sh` | Deploy same image digest + Celery startup |
| `scripts/celery/smoke_inspect_ping.py` | Fail-closed `inspect ping` smoke |
| Deploy staging/production steps | Call deploy script when sites exist |

## One-time provision

```bash
# Staging example (names must match your AZURE_WEBAPP_NAME secret)
ENV=staging \
API_WEBAPP="$AZURE_WEBAPP_NAME" \
RG=rg-qgp-staging \
  ./scripts/infra/provision-celery-workers.sh
```

Creates `${API_WEBAPP}-worker` and `${API_WEBAPP}-beat` on the same App Service plan.

## Ongoing deploy

On each staging/production deploy, after the API container is updated:

1. `deploy_celery_apps.sh` updates worker/beat image to the same digest (no-op if sites missing).
2. Startup files: `bash scripts/celery/start_worker.sh` / `bash scripts/celery/start_beat.sh`.
3. Staging smoke installs `celery[redis]` and runs `smoke_inspect_ping.py` fail-closed (lightweight client; no full-app import; pong required).
4. Worker/beat `/healthz` returns 200 only while the Celery process PID is alive (503 if it dies).

## Verify

```bash
export REDIS_URL=... CELERY_BROKER_URL=... CELERY_RESULT_BACKEND=...
python scripts/celery/smoke_inspect_ping.py
# expect JSON with workers: { "<hostname>": {"ok": "pong"} }
curl -sS https://<worker-host>/healthz   # {"status":"ok","role":"worker","celery":"alive"}
```

Local:

```bash
docker compose --profile celery up --build celery-worker celery-beat
```

## Cutover checklist

1. [ ] Provision worker + beat sites (script or `az deployment group` with `infra/main.bicep`)
2. [ ] Confirm Key Vault `REDIS-URL` reachable from new sites (managed identity / app settings)
3. [ ] Merge + deploy; confirm worker `/healthz` 200
4. [x] `inspect ping` returns pong (CI smoke is fail-closed; `--allow-missing` removed)
5. [ ] Enqueue test email/notification; confirm queue drain (**requires SMTP** — see below)
6. [ ] Update `docs/analytics/event-catalog.md` Celery instruments from Deferred → Live

## Outbound email (SMTP) — required for real sends

`EmailService` reads App Settings / env (Key Vault references preferred):

| Setting | Required | Notes |
|---------|----------|-------|
| `EMAIL_ENABLED` | Yes (for ops intent + smoke) | `true`/`1` when outbound email is expected |
| `SMTP_HOST` | Yes | Default `smtp.office365.com` |
| `SMTP_PORT` | Yes | Default `587` |
| `SMTP_USER` | Yes | Mailbox / app user |
| `SMTP_PASSWORD` | Yes | Secret — store in Key Vault, ref from App Settings |
| `FROM_EMAIL` | Recommended | Envelope From |
| `FROM_NAME` | Optional | Display name |

Wire the same settings on **API + worker** (beat does not send mail).

Honesty checks (do **not** fake send):

- `/readyz` and `/api/v1/health/readyz` expose `email_configured` + `email.status`
- `python scripts/smoke/check_email_config.py` exits **1** when `EMAIL_ENABLED` is set but SMTP credentials are missing

As of Lane 1 cutover, **neither** `kv-qgp-staging` nor `kv-qgp-prod` contained `SMTP-*` secrets — create them before claiming email LIVE.

## Outbound SMS (Twilio) — optional

| Setting | Required for send | Notes |
|---------|-------------------|-------|
| `TWILIO_ACCOUNT_SID` | Yes | Account SID — Key Vault preferred |
| `TWILIO_AUTH_TOKEN` | Yes | Secret — never invent; leave unset until real |
| `TWILIO_FROM_NUMBER` | Yes | E.164 sender |
| `SMS_ENABLED` | No | Optional explicit enable/disable |

`/readyz` exposes `sms_configured`, `sms.status`, and a `channels` summary (`email` / `sms` / `push`). Missing Twilio must not invent credentials or flip readiness HTTP status.

