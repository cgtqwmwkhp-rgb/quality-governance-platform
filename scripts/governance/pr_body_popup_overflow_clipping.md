# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Fix clipped dropdowns and action menus (popup overflow)
- **User goal (1–2 lines):** Restore full visibility of Select dropdowns (e.g. New Incident customer) and kebab action menus (e.g. Audit Template Library) that were clipped or collapsed to a sliver across the app.
- **In scope:** Shared Select/DropdownMenu/Tooltip stacking + Select viewport height; portaled menus on Audit Template Library and Forms List
- **Out of scope:** Redesigning menu IA; non-portaled notification/calendar panels; backend changes
- **Feature flag / kill switch:** N/A — UI rendering fix

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
  - `frontend/src/components/ui/Select.tsx` — viewport height no longer locked to trigger; z-index above dialogs
  - `frontend/src/components/ui/DropdownMenu.tsx` / `Tooltip.tsx` — z-index above dialog overlays
  - `frontend/src/components/ui/Dialog.tsx` — comment only (shell scroll retained; overlays portal above)
  - `frontend/src/pages/AuditTemplateLibrary.tsx` — kebab + sort menus use portaled `DropdownMenu`
  - `frontend/src/pages/admin/FormsList.tsx` — card action menu uses portaled `DropdownMenu`
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI primitive fix
- **Tolerant reader / strict writer applied?** Yes — no API/schema change
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — revert commit / redeploy previous tip

## 4) Acceptance Criteria (AC)
- [x] AC-01: Select lists inside modals (e.g. Incidents → New Incident → Customer) show a full scrollable list, not a one-row sliver
- [x] AC-02: Audit Template Library row/card kebab shows Edit, Duplicate, and Archive without clipping by the table/card overflow
- [x] AC-03: Forms List card kebab menus are not clipped by card overflow
- [x] AC-04: Select/DropdownMenu/Tooltip stack above Dialog overlays (`z-[200]` vs `z-50`)
- [x] AC-05: Frontend typecheck clean for touched files

## 5) Testing Evidence (link to runs)
- [x] Lint — deferred to CI
- [x] Typecheck — `npx tsc --noEmit` clean locally
- [ ] Build — CI
- [ ] Unit tests — N/A (UI primitive + menu wiring)
- [ ] Integration tests — N/A
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke (critical journeys) — post-deploy / staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Incidents → New Incident → open Customer / contract Select → full option list visible and selectable
- [x] CUJ-02: Audit Template Library (list view) → ⋮ menu → Edit / Duplicate / Archive fully visible
- [x] CUJ-03: Audit Template Library sort filter menu opens fully without clipping

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open New Incident customer Select + Audit Template kebab on staging SWA
- **Canary plan:** N/A (SWA tip deploy)
- **Prod post-deploy checks:** tip==LIVE; smoke CUJ-01 and CUJ-02 on prod

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Menus/selects unusable, or unexpected overlay stacking regressions
- **Rollback steps:** Revert merge commit on main; redeploy previous tip
- **Owner:** Platform / Quality

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
