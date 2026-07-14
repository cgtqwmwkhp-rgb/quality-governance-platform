# Change Ledger (CL-AM-BRIDGE)

## 1) Summary

- **Feature / Change name:** AM-BRIDGE — Safety Asset detail competency panel
- **User goal (1–2 lines):** Bridge each Safety Asset detail view to the competency requirements and workforce capability recorded for its asset type, while clearly distinguishing that type from the physical asset instance.
- **In scope:** Safety Asset detail competency panel; existing workforce read API consumption; component tests; en/cy translations; this Change Ledger.
- **Out of scope:** `CompetencyDashboard`; workforce API/backend changes; asset import, notifications, or unrelated Asset Management pages.
- **Feature flag / kill switch:** N/A — additive read-only detail panel.

## 2) Impact Map (what changed)

- **Frontend (routes/screens/components):** `SafetyAssetDetail` loads and presents type-level competency requirements and active competency holders for the asset type.
- **Backend (handlers/services):** None.
- **APIs (endpoints changed/added):** None — reuses `/api/v1/competency-requirements/?asset_type_id=…` and `/api/v1/wdp-analytics/engineer-matrix`.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None — uses existing `workforceApi` types.
- **Database (migrations/entities/indexes):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive UI only.
- **Tolerant reader / strict writer applied?** Yes — independent request failures render explicit unavailable states; no data is represented as zero.
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy (DB):** N/A — revert PR only.

## 4) Acceptance Criteria (AC)

- [x] AC-01: Asset detail displays competency requirements filtered by the asset's type.
- [x] AC-02: Panel explicitly labels requirements and workforce competency holders as type-linked, and clarifies that they are not assigned to the physical instance.
- [x] AC-03: Active holders render only from the existing engineer matrix; empty and unavailable states are honest.
- [x] AC-04: No backend endpoint added; existing typed workforce read client is reused.
- [x] AC-05: Component tests cover populated and unavailable panel states; en/cy translations are present.
- [x] AC-06: Exclusive allowlist respected; `CompetencyDashboard`, AM-IMPORT, and AM-NOTIFY are untouched.

## 5) Testing Evidence (link to runs)

- [x] Lint — `npm run lint` (local)
- [x] Typecheck / build — `npm run build` (local)
- [x] Unit tests — `npx vitest run src/pages/__tests__/SafetyAssetDetail.test.tsx` (local)
- [ ] i18n gate — blocked by 13 pre-existing missing `workforce.calendar.*` en keys; AM-BRIDGE en/cy keys are present
- [x] Integration tests — N/A (existing read endpoints)
- [x] Contract tests — N/A (existing workforce client contract)
- [x] E2E Smoke — N/A (component-level additive UI)

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Safety Asset instance shows requirements for its `asset_type_id`.
- [x] CUJ-02: Active competency holders display only when the existing matrix supplies them.
- [x] CUJ-03: Requirement/matrix failures stay visible as unavailable instead of fabricated empty or zero results.

## 7) Observability & Ops

- **Logs:** No change.
- **Metrics:** No change.
- **Alerts:** No change.
- **Runbook updates:** N/A.

## 8) Release Plan (Local → Staging → Canary → Prod)

- **Staging verification:** Open a Safety Asset detail with a configured type requirement and verify the type/physical-instance distinction and matrix holder state.
- **Canary plan:** N/A.
- **Prod post-deploy checks:** Confirm unavailable states appear if a workforce read API is unavailable.

## 9) Rollback Plan (Mandatory)

- **Rollback trigger:** Asset detail rendering regression or workforce response compatibility issue.
- **Rollback steps:** Revert PR.
- **Owner:** Asset Management / Workforce tracks.

## 10) Evidence Pack (links)

- CI run(s): linked after PR creation.
- Staging deploy evidence: pending.
- Canary evidence: N/A.

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete.
- [x] **Gate 1:** Reuses WF-CLIENT typed read endpoints; no backend/API surface added.
- [ ] **Gate 2:** CI green (lint/type/build/tests).
- [ ] **Gate 3:** Staging verification complete (evidence linked).
- [x] **Gate 4:** Rollback plan verified.
- [ ] **Gate 5:** Evidence pack linked / LIVE honesty noted.

## Exclusive allowlist (this PR)

- `frontend/src/pages/SafetyAssetDetail.tsx`
- `frontend/src/pages/__tests__/SafetyAssetDetail.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_am_bridge.md`

**Zero overlap with `CompetencyDashboard`, AM-IMPORT, and AM-NOTIFY.** The panel presents type-level competency facts only; the platform has no physical-instance competency assignment data.
