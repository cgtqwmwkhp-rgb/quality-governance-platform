# QGP Production Conveyor Policy

Multi-lane merge bot for `cgtqwmwkhp-rgb/quality-governance-platform`.
Source of truth for progress: WCS canvas `qgp-wcs-action-plan.canvas.tsx`.

## Goals

- Keep merge lanes productive without fighting: coordinate tip promote, value, and Dependabot.
- Avoid conflicts: rebase/update PR branches onto latest `main` before merge.
- Continue the queue when a lane frees: merge the next green PR that matches priority.
- Never promote production without staging SHA match + security green + Redis/Celery readiness.

## Merge order (priority queue) — WCS value lane

Promoted / closed (do not re-queue): #549 (ZAP), #552 (staging REDIS-URL), #551 (Trivy HIGH), #550 (PWA SOS), #548 (JWT revoke BE / import / Redis fail-fast).

Completed value (do not re-queue): **#574** tenant filter, **#575** logout revoke.

Current priority:

1. **Promote tip if lag** — if staging `build_sha` lags signed `main`, wait for Deploy Staging cutover (or diagnose) before merging more app PRs
2. **Value P0s from action plan** — next product value from `qgp-wcs-action-plan` (e.g. live Notifications UI / email enqueue); one app change at a time with staging gate
3. **Remaining hard Dependabot only with code fix** — `#290` `#558` `#287` `#274` `#573`; one at a time; never conflict-merge; push code fix to PR branch when CI/red
4. **#355 human decision** — Gemini SDK + audit metadata; do not auto-merge; await explicit human go

Stale queue items removed: **#555** / **#556** (no longer head-of-queue).

## Lane rules (hard)

1. **Coordinated lanes.** Do not merge if:
   - another PR merge is in progress on the same runtime surface
   - main CI is running for a just-merged SHA
   - Deploy Staging / Deploy Production is in progress
2. **Green only.** Squash-merge only when:
   - `mergeable == MERGEABLE`
   - all **required** checks are success
   - branch is not behind `main` (update/rebase first if behind)
3. **No conflict merges.** If GitHub reports conflicts, rebase onto `main`, push, wait for CI — never force-merge.
4. **Staging gate between app deploys.** After merging an app/runtime change, wait until staging `/api/v1/meta/version` `build_sha` advances (or Deploy Staging completes with Build+Deploy not skipped) before merging the next app PR. Pure docs/CI/signoff PRs may merge back-to-back if no deploy is in flight.
5. **Fix red PRs in place.** Push fixes to the PR branch; do not open duplicate PRs for the same fix.
6. **Never** force-push `main`, skip hooks, or amend others' commits.
7. **Production promote** only when:
   - staging `build_sha` matches signed main SHA
   - Security Scan / Trivy green
   - Redis + Celery configured for prod (Key Vault)
   - `docs/evidence/release_signoff.json` updated to that SHA

## Heartbeat cadence

- Every **5 minutes** while the conveyor is armed.
- Each tick: status → fix blockers on head-of-queue PR → merge if lane free → refresh WCS action-plan canvas when queue state changes.
- Advisory only: do not hammer GitHub API (single `gh` list/status per tick; no tight retry loops).

## Stop conditions

- User says stop / pause conveyor
- Production successfully verified on target SHA
- Unrecoverable auth or permissions failure (report and wait)
