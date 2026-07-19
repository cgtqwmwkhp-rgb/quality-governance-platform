# Change Ledger (CL-FIX-IMS-BARCHART3)

## File allowlist (exclusive)
- `frontend/src/pages/IMSDashboard.tsx`
- `scripts/governance/pr_body_fix_ims_barchart3.md`

## 1) Summary
- **Feature / Change name:** Remove unused BarChart3 import breaking FE lint/tsc after #1167
- **User goal:** Unblock Frontend Tests / SWA build on tip and open PRs
- **In scope:** Delete unused import
- **Out of scope:** IMS shell behaviour
- **Feature flag / kill switch:** N/A

## 2) Impact Map
- **Frontend:** IMSDashboard.tsx import only
- **Backend:** None

## 3) Compatibility & Data Safety
- No behaviour change
- **Compatibility strategy:** FE-only
- **Breaking changes:** None
- Rollback: revert

## 4) Acceptance Criteria (AC)
- [x] AC-01: BarChart3 unused import removed
- [x] AC-02: No IMS runtime change
- [x] AC-03: Unblocks eslint --max-warnings 0 / tsc

## 5) Testing Evidence
- [x] Local import removed
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: `/ims` still loads section shell
- [x] CUJ-02: FE lint no unused BarChart3

## 7) Observability & Ops
- None

## 8) Release Plan
1. Squash-merge ASAP to unblock conveyor
2. Sync open PRs to new tip

## 9) Rollback Plan
1. Revert squash
- **Rollback steps:** revert PR
- **Owner:** Platform

## 10) Evidence Pack (links)
- CI after merge

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready
