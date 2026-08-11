# Change Ledger (CL-FR-NAV-FLEET-CERT-IA)

> Base: `origin/main` @ `eaff34e5` (FR-ASSIST-CORE-01 merged).
> Frontend Layout IA only — no route/RBAC/API/schema change.
> Product decision: reverse FR-NAV-FLEET-ASSETS-01 nested group; Certificate shelf moves under Compliance.

## 1) Summary

- **Feature / Change name:** FR-NAV-FLEET-CERT-IA — Fleet & Assets first-level hub; Certificate shelf under Compliance
- **User goal:** Operators reach Van Checklists and Asset Register as a standalone section; Certificate shelf sits with Compliance Schedule for the same operator job.
- **Problem:** Fleet items were nested under Safety & Cases (reads as a subsection). Certificate shelf lived under Assurance next to audits, away from schedule/expiry work.
- **In scope:**
  - `Layout.tsx` — new `fleet-assets` hub; remove van/assets from Safety; move `/assurance/certificates` into Compliance & Sustainability
  - `Layout.test.tsx` — hub membership + within-hub assertions (Fleet not under Safety; cert not under Assurance)
  - `en.json` / `cy.json` — `nav.fleet_assets`
- **Out of scope:**
  - Compliance Schedule domain filter chips (FR-CS-DOMAIN-03 — follow-up)
  - Catalogue LOLER/PSSR/PAT activations (FR-CS-CATALOGUE-04)
  - Merging Certificate shelf page into the schedule surface
  - Route renames (cert URL stays `/assurance/certificates`)
  - UX Coverage Gate HOLD — ignored
- **Feature flag / kill switch:** None.

## 2) Impact Map

- **Frontend:** `frontend/src/components/Layout.tsx`
- **Tests:** `frontend/src/components/__tests__/Layout.test.tsx`
- **i18n:** `nav.fleet_assets` en/cy
- **Backend / APIs / Database / Config:** None

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive hub + nav move; deep links unchanged.
- **Breaking changes:** None intentional (bookmarks to cert URL still work).
- **Migration / Rollback:** Revert merge; redeploy prior tip. No schema.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Fleet nav IA | Nested group under Safety | First-level Fleet & Assets hub |
| Certificate shelf nav | Under Assurance | Under Compliance & Sustainability |
| Routes / RBAC | Unchanged | Unchanged |

## 4) Acceptance Criteria

- [x] **AC-01:** First-level hub `fleet-assets` exposes Van Checklists + Asset Register
- [x] **AC-02:** Safety & Cases no longer lists van/assets (no `nav-group-fleet-assets`)
- [x] **AC-03:** Certificate shelf link appears under Compliance hub, not Assurance
- [x] **AC-04:** Paths remain `/vehicle-checklists`, `/safety-assets`, `/assurance/certificates`
- [x] **AC-05:** Layout unit tests cover AC-01–AC-03
- [x] **AC-06:** No test skipped/loosened

## 5) Testing Evidence

- [x] `vitest run src/components/__tests__/Layout.test.tsx` — **24 passed**
- [ ] Full CI — after PR open
- [ ] Tip LIVE — after merge

## 6) Critical Journeys

- [x] **CUJ-01:** Expand Fleet & Assets → open Van Checklists / Asset Register
- [x] **CUJ-02:** Expand Compliance → open Certificate shelf next to Compliance Schedule
- [x] **CUJ-03:** Expand Safety → only case registers (no fleet subsection)

## 7) Observability & Ops

- No new metrics. Nav-only change.

## 8) Release Plan

1. Merge after CI green (admin-merge authorised; Assist FIND-02 deferred).
2. Main CI → STG → PROD with `release_sha` = tip.
3. Spot-check: Fleet hub present; Certificate shelf under Compliance; Safety has no fleet group.

## 9) Rollback Plan

- **Trigger:** Missing Fleet hub, cert lost from nav, or Safety children wrong.
- **Steps:** Revert merge commit; redeploy prior tip. No DB unwind.
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack

- Unit: Layout 24 passed
- Change Ledger: this body
- IA review canvas: nav-fleet-compliance-ia (domain filters deferred)

---

# Gate Checklist

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Additive nav (no schema)
- [x] **Gate 2:** Tests observed green for Layout suite
- [x] **Gate 3:** Rollback = revert deploy
- [ ] **Gate 4:** CI green on PR
- [ ] **Gate 5:** Tip LIVE verified
