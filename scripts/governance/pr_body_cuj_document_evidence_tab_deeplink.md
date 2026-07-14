# Change Ledger (CL-PATH11-CUJ-DOCUMENT-EVIDENCE-TAB-DEEPLINK)

## File allowlist (exclusive)
- `frontend/src/pages/DocumentDetail.tsx`
- `frontend/src/pages/documentEvidenceTab.ts` (NEW)
- `frontend/src/pages/__tests__/documentEvidenceTab.test.ts` (NEW)
- `scripts/governance/pr_body_cuj_document_evidence_tab_deeplink.md`

**Zero overlap** with standards-parity PRs, exceptions-inbox-filters, Layout.tsx, docs-search.

## 1) Summary
- **Feature / Change name:** CUJ — Document Standards & Evidence tab deeplink + proposed scroll
- **User goal (1-2 lines):** `/documents/:id?tab=evidence` opens Standards & Evidence and scrolls to the proposed-links action region.
- **In scope:** Tab resolve helper; proposed anchor + smooth scroll; unit tests
- **Out of scope:** Layout; Exceptions inbox; case Standards tabs; version-control
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `DocumentDetail.tsx`, `documentEvidenceTab.ts`
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive URL `tab` + optional `#proposed-evidence-links`
- **Tolerant reader / strict writer applied?** Yes — unknown tabs fall back to overview
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** Revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: `?tab=evidence` selects Standards & Evidence
- [x] AC-02: Proposed links region has stable anchor id and scrolls into view
- [x] AC-03: Helper unit tests cover resolve + scroll gate

## 5) Testing Evidence (link to runs)
- [x] Frontend unit — documentEvidenceTab tests
- [ ] CI — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Related-doc link with `?tab=evidence` opens Standards & Evidence
- [x] **CUJ-02:** Page scrolls to proposed evidence actions after load
- [x] **CUJ-03:** Invalid `tab` falls back to overview

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Open `/documents/{id}?tab=evidence` and confirm scroll target
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check one evidence deeplink from Standards panel related docs

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Wrong tab selected or scroll jank blocking review
- **Rollback steps:** Revert commit, redeploy
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: pending
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
