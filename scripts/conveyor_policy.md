# QGP Production Conveyor Policy

Single-lane merge bot for `cgtqwmwkhp-rgb/quality-governance-platform`.
Source of truth for progress: WCS canvas `qgp-wcs-15-stage-audit.canvas.tsx`.

## Goals

- Keep a free lane: at most one merge-to-main in flight.
- Avoid conflicts: rebase/update PR branches onto latest `main` before merge.
- Continue the queue when the lane frees: merge the next green PR automatically.
- Never promote production without staging SHA match + security green + Redis/Celery readiness.

## Merge order (priority queue) — post-promote

Promoted / closed (do not re-queue): #549 (ZAP), #552 (staging REDIS-URL), #551 (Trivy HIGH), #550 (PWA SOS).

Current priority:

1. **#555** — release signoff for signed main SHA (`6cc641e6` or current tip)
2. **#556** — prod auto-rollback RG alignment (app deploy; wait staging SHA after merge)
3. Any other open PRs — oldest first, only if green and mergeable (skip CONFLICTING; rebase first)
4. Dependabot — only after human/app PRs above; one at a time; never conflict-merge

## Lane rules (hard)

1. **One lane.** Do not merge if:
   - another PR merge is in progress
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
- Each tick: status → fix blockers on head-of-queue PR → merge if lane free → update WCS canvas.

## Stop conditions

- User says stop / pause conveyor
- Production successfully verified on target SHA
- Unrecoverable auth or permissions failure (report and wait)
