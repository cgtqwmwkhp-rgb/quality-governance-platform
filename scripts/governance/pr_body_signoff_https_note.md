# Change Ledger (CL-001)

## 1) Summary
- **Change name:** Update release_signoff governance_note for production httpsOnly=true
- **In scope:** `docs/evidence/release_signoff.json` one field
- **Out of scope:** App code, infra templates

## 2) Impact Map
- **Evidence only:** `docs/evidence/release_signoff.json`

## 3) Compatibility & Data Safety
- **Breaking changes:** None

## 4) Acceptance Criteria (AC)
- [x] AC-01: governance_note matches `az webapp show` httpsOnly=true
- [x] AC-02: JSON remains valid
- [x] AC-03: No change to release_sha / run IDs

## 5) Testing Evidence
- [x] Azure CLI: `az webapp show --name app-qgp-prod --resource-group rg-qgp-staging --query httpsOnly` → true

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: N/A docs-only
- [x] CUJ-02: N/A docs-only

## 7) Observability & Ops
- N/A

## 8) Release Plan
- Merge to main; no redeploy required for runtime

## 9) Rollback Plan
- **Rollback steps:** Revert commit restoring prior governance_note text
- **Owner:** Platform

## 10) Evidence Pack
- Azure CLI output; live curl unchanged

---

# Gate Checklist
- [x] **Gate 0:** Change Ledger complete
- [x] **Gate 1:** N/A
- [x] **Gate 2:** make pr-ready on branch
- [x] **Gate 3:** N/A
- [x] **Gate 4:** N/A
- [x] **Gate 5:** Post-merge prod still 027ed34c on /meta/version
