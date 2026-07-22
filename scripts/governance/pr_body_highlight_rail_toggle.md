# Change Ledger (CL-HIGHLIGHT-RAIL-TOGGLE)

## 1) Summary
- **Feature / Change name:** Dashboard highlight rail — pause auto-scroll by default + user toggle
- **User goal (1–2 lines):** Stop the priority-chip marquee from being a nuisance; let users keep a calm static wrap and opt into auto-scroll if they want it.
- **In scope:** `HighlightRail` default-off marquee, play/pause toggle, localStorage preference, unit tests
- **Out of scope:** Changing which chips appear; redesigning My Day / Pulse layout
- **Feature flag / kill switch:** Client preference `qgp.dashboard.highlightRail.autoScroll` (localStorage)

## 2) Impact Map (what changed)
- **Frontend:** `HighlightRail.tsx` (+ tests)
- **Backend:** None
- **APIs:** None
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** localStorage preference only
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UX control; chips and deep-links unchanged
- **Tolerant reader / strict writer applied?** Yes — missing preference defaults to static (off)
- **Breaking changes:** None (marquee default flips to off — safer UX)
- **Migration plan:** None
- **Rollback strategy (DB):** N/A

## 4) Acceptance Criteria (AC)
- [x] AC-01: With >4 chips, rail defaults to static wrap (no marquee duplication)
- [x] AC-02: Toggle starts/stops auto-scroll; `aria-pressed` reflects state
- [x] AC-03: Preference persists in localStorage across reloads
- [x] AC-04: `prefers-reduced-motion: reduce` never marquees and hides the toggle
- [x] AC-05: Empty rail still shows honest "All clear"

## 5) Testing Evidence (link to runs)
- [x] FE unit: `HighlightRail.test.tsx`
- [ ] CI — after push

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Dashboard with many priority chips loads calm (no scrolling); Play enables marquee; Pause returns to static

## 7) Observability & Ops
- **Logs:** N/A
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open `/dashboard` with multiple highlight chips; confirm no auto-scroll; toggle Play then Pause
- **Canary plan:** N/A
- **Prod post-deploy checks:** tip==LIVE; highlight rail calm by default; toggle works

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Toggle broken / rail unusable
- **Rollback steps:** Revert merge commit and redeploy previous tip
- **Owner:** Frontend

## 10) Evidence Pack (links)
- CI run(s): Linked after green CI
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — FE-only preference
- [x] **Gate 2:** CI green (lint/type/build/tests) — verified locally; awaiting hosted CI
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
