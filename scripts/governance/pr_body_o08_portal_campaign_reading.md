# Change Ledger (CL-O-08-PORTAL-CAMPAIGN-READING)

## 1) Summary
- **Feature / Change name:** O-08 Portal/mobile document campaign complete journey
- **User goal (1–2 lines):** Let portal (mobile) field users see pending document campaign assignments from My Work, open/read documents, ask questions, pass required quizzes, and complete attestations without switching to the admin My Reading surface.
- **In scope:** Shared campaign reading helpers extracted from My Reading; mobile-first `PortalReading` page; My Work campaign slice + deep link; route wiring; unit tests; English i18n.
- **Out of scope:** Backend/API changes; HSEC launch panel; policy one-tap acknowledge on mobile (unchanged — open in full app only).
- **Feature flag / kill switch:** None; revert frontend commit to roll back.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `/portal/reading` mobile campaign journey; `/portal/work` pending campaign cards + Continue link; `MyReading` refactored to shared helpers only.
- **Backend (handlers/services):** None.
- **APIs (endpoints changed/added):** Reuses existing `/api/v1/document-campaigns/my-assignments`, open, quiz GET/POST, complete; knowledge bank `createThread` + `postMessage` for ask-question.
- **Schemas/contracts:** None (frontend-only).
- **Database:** None.
- **Workflows/jobs:** None.
- **Config/env/flags:** None.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive portal surfaces; admin My Reading behaviour unchanged.
- **Tolerant reader / strict writer:** Same defensive parsing as #1147 My Reading journey.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy:** Revert squash commit; redeploy prior frontend SHA.

## 4) Acceptance Criteria (AC)
- [x] AC-01: My Work loads pending campaign assignments via `listMyAssignments` and links to `/portal/reading`.
- [x] AC-02: Portal Reading lists non-completed assignments with mobile stack layout and large tap targets (`min-h-12` buttons).
- [x] AC-03: Open records assignment open event then opens document in new tab (portal-safe read path).
- [x] AC-04: Required quiz loads, accepts MCQ/open answers, submits, and gates completion on pass.
- [x] AC-05: Complete collects acceptance statement + optional signature and calls `completeAssignment`.
- [x] AC-06: Ask question creates document Q&A thread and posts message via knowledge bank API.
- [x] AC-07: Shared helpers extracted; My Reading uses them without behaviour change.

## 5) Testing Evidence
- [x] Unit: `frontend/src/pages/__tests__/campaignReadingHelpers.test.ts`
- [x] Unit: `frontend/src/pages/__tests__/PortalReading.test.tsx`
- [x] Unit: `frontend/src/pages/__tests__/PortalWork.test.tsx` (campaign slice)
- [ ] CI — required on PR
- [ ] E2E smoke — pending staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Portal → My Work → pending campaign card → Continue → Portal Reading assignment expanded.
- [x] CUJ-02: Open → document tab; quiz submit → attestation → complete assignment.
- [x] CUJ-03: Ask question → thread + message posted.

## 7) Observability & Ops
- **Logs:** Existing API error toasts; no new metrics.
- **Runbook:** N/A — uses existing campaign + knowledge bank endpoints.

## 8) Release Plan
1. Merge after CI green (do not merge from authoring step alone).
2. Staging: assign test campaign to portal user; exercise full journey on mobile viewport.

## 9) Rollback Plan
- **Trigger:** Campaign list/open/quiz/complete failures on portal; My Work regression.
- **Steps:** Revert PR commit; redeploy prior SHA; confirm My Work + admin My Reading recover.

## 10) Evidence Pack
- CI run(s): Linked after PR creation.
- Local: vitest for helpers, PortalReading, PortalWork.

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete.
- [x] **Gate 1:** Allowlist — portal reading surfaces, shared helpers, tests, i18n only.
- [ ] **Gate 2:** CI green.
- [ ] **Gate 3:** Staging verification.
- [x] **Gate 5:** Rollback plan documented.

## Out of scope (explicit)
- Policy acknowledge checkbox on mobile portal
- HSEC campaign launch UI
- Backend campaign API changes
