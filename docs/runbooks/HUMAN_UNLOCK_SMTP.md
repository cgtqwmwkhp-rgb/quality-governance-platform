# Human unlock — SMTP (operator runbook)

**Status (2026-07-13):** SMTP wired on staging + prod (`SMTP_USER=qgp-notifications@…`, `FROM_EMAIL=HSEQ@plantexpand.com`). IT confirmed M365 SMTP AUTH + Send As works. App 535 was client-side: App Settings had been pinned to a **versioned** KV secret URI; refs are now **versionless** and apps restarted. `EmailService` + `wire_smtp.sh` strip credentials / use versionless refs.

**PagerDuty:** Removed from product scope (EA-05 Cancelled). Ops alerting remains Azure Monitor email action groups — see [alerting-integration.md](alerting-integration.md).

Do **not** invent credentials. Do **not** set `EMAIL_ENABLED=true` without `SMTP_USER` + `SMTP_PASSWORD` (reports `misconfigured`).

## Prerequisites

1. M365 mailbox (or SMTP-capable mailbox) + app password / SMTP AUTH.
2. Azure CLI logged in with rights to Key Vault secrets + App Service config on `rg-qgp-staging`.

## One-shot wire (staging then prod)

```bash
cd /Users/davidharris/quality-governance-platform
chmod +x scripts/ops/wire_smtp.sh

export SMTP_USER='noreply@your-domain'
export SMTP_PASSWORD='***'          # never commit
export FROM_EMAIL='noreply@your-domain'
export FROM_NAME='QGP Notifications'

./scripts/ops/wire_smtp.sh staging
./scripts/ops/wire_smtp.sh prod
```

Script writes KV secrets (`SMTP-USER`, `SMTP-PASSWORD`, `FROM-EMAIL`, `FROM-NAME`), sets App Settings on:

| Env | Apps (resource group `rg-qgp-staging`) |
|-----|----------------------------------------|
| staging | `qgp-staging-plantexpand`, `qgp-staging-plantexpand-worker` |
| prod | `app-qgp-prod`, `app-qgp-prod-worker` |

Beat sites are not wired (they do not send mail).

## Success criteria

```bash
curl -sS https://qgp-staging-plantexpand.azurewebsites.net/readyz | tee /tmp/stg-readyz.json | \
  python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("email_configured"), (d.get("email") or {}).get("status"))'
# expect: True configured

python scripts/smoke/check_email_config.py --from-readyz /tmp/stg-readyz.json
# exit 0

# Same for prod:
curl -sS https://app-qgp-prod.azurewebsites.net/readyz | tee /tmp/prd-readyz.json | \
  python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("email_configured"), (d.get("email") or {}).get("status"))'
```

Then prove **one real enqueue → SUCCESS** (workflow notification / Celery `send_email`) and confirm worker logs `status=sent` — see [CELERY_WORKER_BEAT_DEPLOY.md](CELERY_WORKER_BEAT_DEPLOY.md).

## After LIVE proof

Tell the Preferred conveyor / agent to rescore WCS canvases for S4/S11/S12 on SMTP evidence only. Do not credit scores before curl evidence.
