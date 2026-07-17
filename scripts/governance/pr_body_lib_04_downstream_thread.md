# Change Ledger (CL-LIB-04-DOWNSTREAM-THREAD)

**Path claim:** `path11/lib-04-downstream-thread`

## File allowlist (exclusive)

- `frontend/src/pages/Documents.tsx`
- `frontend/src/pages/DocumentDetail.tsx`
- `frontend/src/pages/documentsDownstreamHelpers.ts`
- `frontend/src/pages/__tests__/documentsDownstreamHelpers.test.ts`
- `frontend/src/pages/__tests__/Documents.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_lib_04_downstream_thread.md`

**Zero overlap** with parallel lanes: `Investigations*`, `ComplianceAutomation*`, `PlanetMark*` (#1068), Layout/App/client.ts spines, `api/__init__.py`, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 LIB-04 — Library upload downstream golden-thread honesty → AI Exceptions
- **User goal:** After uploading a library document, operators see honest indexing/downstream guidance (not silent empty); indexed docs deep-link to AI Exceptions and Document Control golden thread.
- **In scope:** Post-upload banner; Document detail overview downstream panel; evidence-tab empty honesty; shared helpers + vitest; i18n en/cy
- **Out of scope:** Backend indexing pipeline; Document Control golden-thread API; KnowledgeExceptions page changes
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Post-upload | Toast only | **Downstream banner** — processing honesty + dismiss; indexed → AI Exceptions CTA |
| Document detail overview | No downstream context | **Golden thread panel** with phase-specific copy + handoffs |
| Evidence tab empty | Generic “Run AI mapping” | **Processing vs indexed** honesty + AI Exceptions link when indexed |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Read-only UI + existing upload response fields (`id`, `status`, `reference_number`)
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Successful upload shows downstream notice with processing next-step copy
- [x] AC-02: Indexed documents surface AI Exceptions closed-loop link (`entity_type=document`)
- [x] AC-03: Document detail overview shows downstream panel with Document Control note when indexed
- [x] AC-04: Evidence empty state distinguishes processing vs indexed
- [x] AC-05: Vitest covers helpers + upload banner

## 5) Testing Evidence

- [x] Vitest — `documentsDownstreamHelpers.test.ts`, `Documents.test.tsx`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Upload PDF → banner explains indexing → no fake AI Exceptions link while processing
- [x] CUJ-02: Open indexed document detail → AI Exceptions + Document Control handoffs visible

## 7) Observability & Ops

- **Playwright hooks:** `documents-upload-downstream-notice`, `documents-upload-exceptions-link`, `documents-detail-exceptions-link`, `documents-downstream-thread`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke: `/documents` upload + `/documents/:id` overview

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `cd frontend && npx vitest run src/pages/__tests__/documentsDownstreamHelpers.test.ts src/pages/__tests__/Documents.test.tsx`
- [ ] Manual: upload document → downstream banner with indexing note
- [ ] Manual: indexed document detail → AI Exceptions link works
