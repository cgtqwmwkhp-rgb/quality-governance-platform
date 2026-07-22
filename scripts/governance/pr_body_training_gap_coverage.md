# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Training Manager Gap Board — Coverage (All staff) + chase integrity
- **User goal:** Managers can switch to an explicit **All staff** coverage roster (including 100% OK people) while keeping Overdue/All open as chase queues; email actions are honest about who notify will skip; analytics due bars respect Training-group scope.
- **In scope:** AC-G1..AC-G6
- **Out of scope:** due_soon notify backend; manager team-scoped API; portal catalog plumbing (PR2)
- **Feature flag / kill switch:** N/A — additive UI horizon

## 2) Impact Map
- **Frontend:** `trainingMatrixBoardHelpers.ts`, `TrainingMatrixPanels.tsx`, helper unit tests
- **Backend / APIs / DB / workflows:** None

## 3) Compatibility & Data Safety
- Behavioural FE-only; default remains Overdue chase queue
- No schema/API changes

## 4) Acceptance Criteria (AC)
- [x] AC-G1: Overdue still lists only people with ≥1 overdue row
- [x] AC-G2: All staff lists every person in role-scoped compliance set, including 0 overdue / 100%
- [x] AC-G3: Table chip states count + active horizon + role scope
- [x] AC-G4: Email action shows X/Y preview; only notifies gap-status recipients
- [x] AC-G5: Analytics due bars use scoped horizon counts
- [x] AC-G6: Unit tests lock chase vs Coverage membership + notify preview

## 5) Testing Evidence
- [x] Unit: `trainingMatrixBoardHelpers.test.ts` (33 passed)

## 6) Critical Journeys (CUJ)
- [x] CUJ-01: Manager opens Overdue → chase list; switches All staff → full roster with % sort
- [x] CUJ-02: Email on Next 30 / Coverage previews skips for non-gap people

## 7) Observability & Ops
- No change

## 8) Release Plan
- Staging smoke Gap Board horizons; prod tip==LIVE check

## 9) Rollback Plan
- Revert commit/deploy

## 10) Evidence Pack
- CI linked on PR

---

# Gate Checklist
- [x] Gate 0–1
- [ ] Gate 2 CI green
- [ ] Gate 3 Staging
- [x] Gate 5 Prod verification plan
