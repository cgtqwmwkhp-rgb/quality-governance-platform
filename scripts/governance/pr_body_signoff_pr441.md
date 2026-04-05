# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Release sign-off evidence refresh for production at 027ed34c (PR #441)
- **User goal:** Align `docs/evidence/release_signoff.json` with live production `build_sha`, CI, staging, and production workflow run IDs.
- **In scope:** Governance JSON only
- **Out of scope:** Application code, infra changes, Trivy remediation

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** None
- **APIs:** None
- **Workflows:** None
- **Config:** None
- **Evidence:** `docs/evidence/release_signoff.json`

## 3) Compatibility & Data Safety
- **Compatibility:** Documentation artifact only
- **Breaking changes:** None

## 4) Acceptance Criteria (AC)
- [x] AC-01: `release_sha` equals live `GET /api/v1/meta/version` `build_sha` (027ed34c)
- [x] AC-02: `ci_run`, `staging_deploy_run_id`, `production_deploy_run_id` populated with verified GitHub run IDs
- [x] AC-03: Security Scan Trivy failure at same SHA referenced with run URL/id

## 5) Testing Evidence (link to runs)
- [x] Lint: docs/JSON valid (manual)
- [x] CI: merge-blocking CI green on main at 027ed34c — https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24003668176
- [x] Production verified: curl `/api/v1/meta/version` and `az webapp show` (evidence in governance_note)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: N/A (governance-only PR)
- [x] CUJ-02: N/A — production already live at target SHA before this PR

## 7) Observability & Ops
- **Logs:** N/A
- **Metrics:** N/A
- **Runbook:** `docs/runbooks/rollback-drills.md` referenced in signoff

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging:** Already completed for app — run 24003756424 (recorded)
- **Prod:** Already completed — run 24003860248 (recorded)
- **This PR:** Updates sign-off on `main` after the fact; optional SWA/API redeploy if org requires doc parity (not required for runtime)

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Incorrect run IDs or SHA in signoff
- **Rollback steps:** Revert this commit on `main`; restore prior `release_signoff.json`
- **Owner:** Platform governance lead

## 10) Evidence Pack (links)
- CI: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24003668176
- Security Scan: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24003668173
- Staging: workflow run id 24003756424
- Production: workflow run id 24003860248

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** N/A
- [x] **Gate 2:** `make pr-ready` on branch
- [x] **Gate 3:** Staging evidence recorded (historical)
- [x] **Gate 4:** N/A
- [x] **Gate 5:** Production verification recorded (historical + curl)
