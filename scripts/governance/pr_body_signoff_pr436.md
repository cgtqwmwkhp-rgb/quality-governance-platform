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
- [ ] N/A

## 7) Observability & Ops
- N/A

## 8) Release Plan (Local -> Staging -> Prod)
- Production already promoted via workflow_dispatch; this PR records evidence.

## 9) Rollback Plan (Mandatory)
- Revert this commit if evidence incorrect; no runtime impact.

## 10) Evidence Pack (links)
- CI: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24001598038
- Staging: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24001683143
- Production: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24001788027

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock
- [x] **Gate 2:** Signoff PR CI (expected green on doc-only)
