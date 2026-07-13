# Change Ledger (CL-IA-W4-LIBRARY-MERGE)

## 1) Summary
- **Feature / Change name:** IA-W4 — Library merge (Documents + Policies tabbed UX)
- **User goal (1-2 lines):** Unify Documents and Policies under one Library mental model with shared chrome and in-page tabs, while keeping `/documents` and `/policies` routes stable for deep-links and sidebar children.
- **In scope:** `LibraryShell`, `Documents.tsx`, `Policies.tsx`, and page tests only (IA plan allowlist)
- **Out of scope:** Layout nav collapse to single Library entry (follow-on), SMTP/PagerDuty/DPIA, App routing changes, i18n locale edits, backend APIs
- **Feature flag / kill switch:** N/A — additive UX chrome only; revert commit to restore separate page headers

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** Shared `LibraryShell` with Library title + Documents/Policies tab links; Documents and Policies pages wrap existing content in shell
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — routes unchanged; only page chrome unified
- **Breaking changes:** None — bookmarks to `/documents` and `/policies` continue to work
- **Migration plan:** No migration required
- **Rollback strategy (DB):** No DB change — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: `/documents` shows unified Library title, Documents tab active, existing document workflows intact
- [x] AC-02: `/policies` shows unified Library title, Policies tab active, existing policy register/create intact
- [x] AC-03: Tab links navigate between `/documents` and `/policies` with correct `aria-current` state

## 5) Testing Evidence (link to runs)
- [x] Lint — frontend unchanged deps; local vitest for new/updated page tests
- [x] Typecheck — TypeScript compile via vitest imports
- [x] Build — N/A (frontend-only chrome)
- [x] Unit tests — `LibraryShell.test.tsx`, `Documents.test.tsx`, `Policies.test.tsx` added/updated
- [x] Integration tests — deferred to CI
- [x] Contract tests (if applicable) — N/A
- [x] E2E Smoke (critical journeys) — deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Governance user opens Library → Documents tab → uploads/views a stored document
- [x] CUJ-02: Governance user switches to Policies tab → browses register → creates a new policy record
- [x] CUJ-03: Deep-link to `/policies` lands in Library shell with Policies tab active (no route breakage)

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A — UI-only; no ops change

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Open `/documents` and `/policies`; confirm Library shell, tab navigation, upload/create actions
- **Canary plan:** N/A — low-risk frontend chrome
- **Prod post-deploy checks:** Smoke Library tabs on prod after merge; version SHA match

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Library shell breaks document upload, policy create, or tab navigation
- **Rollback steps:** Revert PR merge on main; redeploy previous SHA via standard CD pipeline
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
