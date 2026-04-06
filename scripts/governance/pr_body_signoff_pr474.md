# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Release signoff artifact sync for PR #473 production wave
- **User goal:** Record deployment run IDs and live `build_sha` in `docs/evidence/release_signoff.json` per governed release practice.
- **In scope:** JSON only
- **Out of scope:** Application code

## 2) Impact Map
- **Frontend:** None
- **Backend:** None
- **APIs:** None
- **Database:** None
- **Workflows:** None
- **Docs:** `docs/evidence/release_signoff.json`

## 3) Compatibility & Data Safety
- **Compatibility:** Additive documentation
- **Breaking changes:** None
- **Rollback:** Revert commit

## 4) Acceptance Criteria
- [x] AC-01: `release_sha` matches promoted merge `5b5a358fe253742cb63aab3ec438f5ba626479ae`
- [x] AC-02: CI / staging / production run IDs recorded
- [x] AC-03: Live prod `build_sha` cited from HTTP verification

## 5) Testing Evidence
- [x] Lint N/A
- [x] Live prod GET `/api/v1/meta/version` 200, `build_sha` matches

## 6) Critical Journeys (CUJ)
- [x] CUJ-01: Governed release chain completed for PR #473 before this doc update
- [x] CUJ-02: Evidence file reflects same `build_sha` as live version endpoint

## 7) Observability
- No change

## 8) Release Plan
- Merge to main; no redeploy required for runtime

## 9) Rollback Plan
- **Rollback steps:** Revert this commit on main
- **Owner:** Platform team

## 10) Evidence Pack
- CI: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24041282827
- Staging deploy run: 24041492831
- Production deploy run: 24041721093
- Live version: `https://app-qgp-prod.azurewebsites.net/api/v1/meta/version` → `build_sha` `5b5a358fe253742cb63aab3ec438f5ba626479ae` (verified 2026-04-06T17:16:17Z)

---

# Gate Checklist
- [x] **Gate 0:** Scope + AC + rollback defined
- [x] **Gate 1:** N/A (docs)
- [x] **Gate 2:** Parent PR #473 CI green before prod
- [x] **Gate 3:** E2E covered on #473 merge CI
- [x] **Gate 4:** Staging + prod deploy success on #473
- [x] **Gate 5:** Live prod version check
