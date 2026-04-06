# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Release signoff evidence update (PR #436 production promotion).
- **User goal (1-2 lines):** Align `docs/evidence/release_signoff.json` with deployed SHA `f73b4b2e6257b9b90a5d87ea21dc7c6d920bb317` and workflow run IDs.
- **In scope:** JSON evidence only.
- **Out of scope:** Application code.
- **Feature flag / kill switch:** None.

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** None
- **APIs:** None
- **Database:** None
- **Workflows:** None
- **Config:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Documentation artifact only.
- **Breaking changes:** None.
- **Rollback strategy (DB):** N/A

## 4) Acceptance Criteria (AC)
- [x] AC-01: `release_sha` matches squash-merge commit on `main` for PR #436.
- [x] AC-02: CI, staging, and production run URLs/IDs recorded.
- [x] AC-03: Security Scan Trivy failure on parallel workflow documented as advisory.

## 5) Testing Evidence (link to runs)
- [x] N/A (JSON only); main CI 24001598038 passed prior to promote.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Governance reviewer can open `docs/evidence/release_signoff.json` on this branch and confirm run IDs match GitHub Actions for SHA f73b4b2e.
- [x] CUJ-02: Platform operator can trace production promotion from `production_promotion` string to workflow_dispatch inputs (staging_verified, release_sha, force_deploy).

## 7) Observability & Ops
- **Logs:** N/A (documentation commit).
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** None.

## 8) Release Plan (Local -> Staging -> Prod)
- **Staging verification:** Completed before production dispatch (run 24001683143).
- **Canary plan:** N/A.
- **Prod post-deploy checks:** Already executed prior to this evidence PR; see production run 24001788027.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Incorrect evidence recorded in `release_signoff.json`.
- **Rollback steps:** Revert merge commit of this PR on `main` or submit a corrective signoff PR.
- **Owner:** Governance lead (David Harris).

## 10) Evidence Pack (links)
- CI: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24001598038
- Staging: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24001683143
- Production: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24001788027

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + Change Ledger complete
- [x] **Gate 1:** N/A (no API/contract change)
- [x] **Gate 2:** CI green on this PR
- [x] **Gate 3:** Staging verification evidence linked (run 24001683143)
- [x] **Gate 4:** Canary N/A
- [x] **Gate 5:** Production verification plan satisfied by pre-PR dispatch run 24001788027
