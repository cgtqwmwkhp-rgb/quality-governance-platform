# Change Ledger — Lane 1 email honesty + Celery smoke fail-closed

## Summary
- Document required SMTP App Settings / Key Vault secrets for `EmailService`
- Add honest `/readyz` `email_configured` (+ `email` object) — never fakes send
- Harden smoke: `scripts/smoke/check_email_config.py` fails when `EMAIL_ENABLED` but SMTP missing
- Drop `--allow-missing` from staging Celery inspect ping (staging worker returns pong)
- Pass through SMTP env to worker/beat in `deploy_celery_apps.sh` when present

## Change Ledger
| Field | Value |
| --- | --- |
| Change type | Ops honesty + CI hardening |
| Risk | Low — additive readiness fields; smoke fail-closed only when EMAIL_ENABLED set |
| Blast radius | Readiness JSON, staging deploy smoke, Celery deploy settings |
| Owner | Platform / ops |

## Impact Map
- `src/infrastructure/email/email_status.py` — readiness helper
- `src/main.py`, `src/api/routes/health.py` — `/readyz` fields
- `scripts/smoke/check_email_config.py` — fail-closed config smoke
- `.github/workflows/deploy-staging.yml` — drop allow-missing; email smoke
- `docs/runbooks/CELERY_WORKER_BEAT_DEPLOY.md`, `docs/ADMIN_GUIDE.md`, `.env.example`
- `scripts/infra/deploy_celery_apps.sh` — optional SMTP passthrough

## Compatibility
- Additive JSON only; missing SMTP does **not** flip readiness to 503
- No fake email send path

## Acceptance Criteria
- [x] AC-01: `/readyz` includes `email_configured` / `email.status`
- [x] AC-02: Smoke exits 1 when EMAIL_ENABLED without SMTP
- [x] AC-03: Staging Celery ping smoke is fail-closed (no `--allow-missing`)
- [x] AC-04: Docs list required SMTP settings; KV currently has none

## Test plan
- [x] `pytest tests/unit/test_email_status.py -q`
- [x] Integration health assertions for email fields
- [ ] CI green on PR
- [ ] Staging: curl `/readyz` shows email fields; Celery ping still pongs

## Rollback
Revert PR / redeploy previous SHA. Celery smoke can temporarily re-add `--allow-missing` only if workers are deprovisioned.
