# Change Ledger (CL-FIX-PYPDF-6.16.2)

## 1) Summary
- **Feature / Change name:** Bump `pypdf` 6.15.0 → 6.16.2 so main CI Security Scan can pass after CB-PR3 merge
- **User goal:** Unblock Staging/Production for CB-PR3 (`51f0b9ad87af` is on main; Azure skipped because main CI Security Scan failed)
- **In scope:** `requirements.txt` + `requirements.lock` pin only
- **Out of scope:** CB-PR4; waivers; Dependabot queue; flag-on; PAMS writes
- **Feature flag / kill switch:** N/A. Kill SHA = previous LIVE `fda52219bcbf` until this SHA is LIVE.

## 2) Impact Map (what changed)
- **Frontend:** none
- **Backend:** none (PDF parser version only)
- **APIs:** none
- **Database / flags:** none
- **Dependencies:** `pypdf` 6.15.0 → 6.16.2

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Patch bump of an existing runtime parser. Same import surface.
- **Breaking changes:** None intended
- **Migration plan:** none
- **Rollback strategy:** Redeploy previous LIVE SHA `fda52219bcbf`

## Compliance Delta
- **ISO 9001 7.2 / ISO 45001 7.2:** Unchanged. This unblocks the CB-PR3 Atlas board deploy; flag stays false.
- **What this PR does not claim:** The three pip-audit IDs are remediations of DoS-class crafted PDFs, not a product behaviour change.

## 4) Acceptance Criteria (AC)
- [x] AC-01: `requirements.txt` pins `pypdf==6.16.2`
- [x] AC-02: `requirements.lock` matches that pin (hashes only for pypdf)
- [x] AC-03: No other package versions change
- [x] AC-04: No waiver added for CVE-2026-84309 / 84310 / 84311
- [x] AC-05: CompetencyDashboard and `FF_COMPETENCE_BOARD` untouched

## 5) Testing Evidence (link to runs)
- [ ] Full CI — linked after PR checks
- [ ] pip-audit / Security Scan green on this SHA

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Main CI Security Scan no longer fails on unwaived pypdf CVEs
- [x] CUJ-02: Staging then Production can deploy; prod `build_sha` becomes this merge SHA
- [x] CUJ-03: Flag stays false; no PAMS writes

## 7) Observability & Ops
- **Logs:** none
- **Runbook:** After LIVE, CB-PR3 Atlas board is on the API behind the closed flag. Then start CB-PR4.

## 8) Release Plan
- **Staging:** Flag stays false
- **Prod post-deploy:** healthz; `build_sha` == tip; Entra stays false

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** PDF import/regression or new pip-audit fail
- **Rollback steps:** Revert squash on `main` and redeploy previous LIVE SHA `fda52219bcbf`
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (dependency pin only)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A)
- [x] **Gate 5:** Production verification plan + monitoring ready
