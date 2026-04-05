# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Release sign-off evidence — PR #439 promoted to production
- **User goal (1-2 lines):** Record CI, staging, production run IDs and live verification outcomes for governance and auto-deploy lineage checks.
- **In scope:** `docs/evidence/release_signoff.json`, execution record appendix with URLs and curl outcomes
- **Out of scope:** Application code, infra changes
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** None
- **APIs:** None
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Documentation / governance artifact only
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A

## 4) Acceptance Criteria (AC)
- [x] AC-01: `release_sha` matches production live `build_sha` from `/api/v1/meta/version`
- [x] AC-02: Staging and production workflow run URLs recorded
- [x] AC-03: Post-deploy smoke outcomes documented

## 5) Testing Evidence (link to runs)
- [x] Lint — N/A (JSON + markdown)
- [x] Typecheck — N/A
- [x] Build — N/A
- [x] Unit tests — N/A
- [x] Integration tests — N/A
- [x] Contract tests — N/A
- [x] E2E Smoke — Manual: healthz, readyz, meta/version on production host

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Production availability — healthz / readyz / version identity
- [x] CUJ-02: Governance lineage — signoff SHA aligns to promoted merge

## 7) Observability & Ops
- **Logs:** N/A
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24002714695
- **Canary plan:** N/A (slot swap per existing workflow)
- **Prod post-deploy checks:** https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24002867809; curl healthz/readyz/version

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** N/A for docs-only PR; app rollback via existing production rollback workflow if needed
- **Rollback steps:** See `docs/runbooks/rollback-drills.md`
- **Owner:** Platform

## 10) Evidence Pack (links)
- CI run(s): https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24002621167
- Staging deploy evidence: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24002714695
- Production deploy evidence: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24002867809

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — N/A
- [x] **Gate 2:** CI green (lint/type/build/tests) — docs-only; `make pr-ready` on branch
- [x] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — completed before this PR
