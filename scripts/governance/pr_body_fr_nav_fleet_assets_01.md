# Change Ledger (CL-FR-NAV-FLEET-ASSETS-01)

> Base: `origin/main` @ `3a06dbee` (P0b harden + FR-DEDUP-04 ops LIVE).
> Frontend Layout IA only — no route/RBAC/API/schema change.

## 1) Summary

- **Feature / Change name:** FR-NAV-FLEET-ASSETS-01 — nest Van Checklists + Asset Register under “Fleet & assets” inside Safety & Cases
- **User goal (1–2 lines):** Operators find van checks and the safety asset register as one nested group under Safety, without inventing a new first-level hub.
- **Problem:** Both items sat as flat siblings under Safety & Cases; the intended “Assets regroup” polish (combine related fleet/asset views) was marked Mostly done but the nested group was never shipped. SSOT **KILL** “Assets as new hub” forbids a top-level hub.
- **In scope:**
  - `Layout.tsx` — optional `group` on hub items; Safety children for `/vehicle-checklists` + `/safety-assets` share `group: 'fleet-assets'` with section label
  - `Layout.test.tsx` — assert group label + both links remain under Safety hub (not a hub button)
  - `en.json` / `cy.json` — `nav.fleet_assets_group`
- **Out of scope / deliberately not done:**
  - No new top-level hub (KILL preserved)
  - No route merges, page merges, or API changes
  - No renames of existing page titles beyond nav grouping
  - UX Coverage Gate HOLD — ignored
- **Feature flag / kill switch:** None.

## 2) Impact Map (what changed)

- **Frontend:** `frontend/src/components/Layout.tsx` — nest van + asset register under Safety section label.
- **Tests:** `frontend/src/components/__tests__/Layout.test.tsx`
- **i18n:** `nav.fleet_assets_group` en/cy
- **Backend / APIs / Database / Config:** None.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive nav chrome only; deep links unchanged.
- **Breaking changes:** None.
- **Migration / Rollback:** Revert merge; redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Safety nav IA | Flat siblings for van + assets | Nested “Fleet & assets” group under Safety hub |
| First-level hubs | No Fleet hub | Still no Fleet hub (KILL preserved) |
| Routes / RBAC | Unchanged | Unchanged |

## 4) Acceptance Criteria (AC)

- [x] **AC-01:** Expanding Safety & Cases shows a “Fleet & assets” group label (`data-testid=nav-group-fleet-assets`).
- [x] **AC-02:** Van Checklists and Asset Register remain links under that group (paths unchanged).
- [x] **AC-03:** There is no first-level hub button named Fleet & assets.
- [x] **AC-04:** `Layout.test.tsx` covers AC-01–AC-03; existing hub structure tests still pass.
- [x] **AC-05:** Change Ledger present for PR body validation.

## 5) Testing Evidence

- [x] Unit — `npx vitest run src/components/__tests__/Layout.test.tsx` → **23 passed**
- [ ] Full CI — after PR open
- [ ] STG/PROD LIVE — conveyor tip-chase after merge

## 6) Critical Journeys (CUJ)

- [x] **CUJ-01:** User expands Safety → sees Fleet & assets → opens Van Checklists / Asset Register.
- [x] **CUJ-02:** Sidebar first-level hubs unchanged (no new hub).

## 7) Observability & Ops

- No change.

## 8) Release Plan

- Allowlist ahead of FR-NOTIF-ADMIN-02 → Main CI → STG → PROD tip-chase with explicit `release_sha` → verify tip LIVE.

## 9) Rollback Plan

- Revert squash on `main`; redeploy prior tip.
