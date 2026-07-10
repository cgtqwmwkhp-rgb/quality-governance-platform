# Change Ledger (CL-ops-celery-healthz-ci)

## Summary
Overnight ops harden: honest Celery worker/beat `/healthz` (PID-alive, not forever-ok), fail-closed inspect smoke without full-app imports (fixes staging CI `sqlalchemy` miss), remove `--allow-missing`.

## Impact Map
- Ops scripts: `scripts/celery/start_worker.sh`, `scripts/celery/start_beat.sh`, `scripts/celery/smoke_inspect_ping.py`
- CI: `.github/workflows/deploy-staging.yml` (pip install celery client before smoke)
- Docs: `docs/runbooks/CELERY_WORKER_BEAT_DEPLOY.md`
- No API/DB/frontend contract changes. Does **not** invent SMTP/Twilio/VAPID credentials.

## Compatibility
Additive ops/CI honesty; App Service health probes still use `/healthz`.

## Acceptance Criteria
- [x] AC-01: Worker/beat healthz returns 503 when Celery PID is dead.
- [x] AC-02: `smoke_inspect_ping.py` does not import `src.infrastructure` (no SQLAlchemy on runner).
- [x] AC-03: Staging Celery smoke has no `--allow-missing` / continue-on-error.
- [x] AC-04: Smoke installs `celery[redis]` before inspect.
- [x] AC-05: SMTP/Twilio/VAPID remain `not_configured` when unset.

## Testing Evidence
- [x] Local inspect ping against shared Redis: two workers pong after plan scale B1→B2.
- [x] Staging+prod worker/beat App Service state Running; staging worker recovered from STOPPED.
- [ ] PR CI green.
- [ ] Staging deploy Celery smoke green after merge.

## Critical Journeys
- [x] CUJ-01: Staging post-deploy Celery inspect ping fails closed and can run on bare runner deps.
- [x] CUJ-02: App Service liveness reflects real Celery process health.

## Observability
Worker/beat `/healthz` JSON includes `role` + `celery` alive/dead; staging smoke remains a hard gate.

## Release Plan
Merge → staging deploy → verify dual pong + honest healthz → release signoff → production promote (workers already Running; keep Running).

## Rollback Plan
- Revert this PR and redeploy prior image digest to worker/beat.
- Owner: Platform team.

## Evidence Pack
Staging run 29125138639 (`No module named 'sqlalchemy'`), local dual-worker pong, plan SKU B2 scale.

## Gate Checklist
- [x] Gate 0: Scope and acceptance criteria defined.
- [x] Gate 1: Ops/CI compatibility reviewed.
- [ ] Gate 2: CI green.
- [ ] Gate 3: Staging verification after merge.
- [x] Gate 4: Canary not applicable.
- [x] Gate 5: Production verification plan ready.

Made with [Cursor](https://cursor.com)
