# Change Ledger (CL-CUJ-DOCUMENTS-SEARCH)

## File allowlist (exclusive)
- `frontend/src/pages/Documents.tsx`
- `frontend/src/pages/__tests__/Documents.test.tsx`
- `frontend/tests/e2e/documents-cuj.spec.ts` (placeholder selector sync only)
- `frontend/tests/e2e/documents-search-cuj.spec.ts` (NEW)
- `scripts/governance/pr_body_cuj_documents_search.md`

**Zero overlap** with `path11/cuj-document-version-control` (DocumentControl / documents.py / DocumentDetail) and `path11/cuj-standards-map-inputs` (KnowledgeExceptions / Assessor). Prefer English literals (no `en.json`/`cy.json`). Parked **#853 SMTP/PD**.

## 1) Summary
- **Feature / Change name:** CUJ — Documents/Library search discoverability + honesty + deep links
- **User goal:** Operators can clearly find and use Library search; share `?q=` deep links; never confuse API failure with zero matches; see keyword + semantic result counts.
- **In scope:** Visible “Search library” control; `?q=` URL sync; server `search=` on list; honest zero vs unavailable semantic panels; vitest + Playwright
- **Out of scope:** Version control; Assessor/GKB mapping; Layout admin hub; Workforce; SMTP
- **Feature flag / kill switch:** N/A — revert commit
- **Stack:** Targets `main` tip including #926/#928/#929/#932

## 2) Impact Map (what changed)
- **Frontend:** `Documents.tsx` search UX + deep links + honesty panels
- **Backend:** None (uses existing list `search` + semantic endpoints)
- **APIs:** Consumes `GET /documents/?search=` and `GET /documents/search/semantic`
- **Schemas/DB/Deps:** None

## 3) Compatibility & Data Safety
- Additive FE only; tolerant of missing `total` on list responses
- Breaking changes: None
- Rollback: revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Search control visibly labeled (`Search library` + `data-testid=documents-library-search`)
- [x] AC-02: `?q=` deep-links hydrate the control and drive server keyword search
- [x] AC-03: Semantic API failure → unavailable panel (never silent / never fake zero)
- [x] AC-04: Semantic empty array → explicit “No semantic matches” (distinct from unavailable)
- [x] AC-05: Vitest + Playwright cover deep link + honesty paths

## 5) Testing Evidence
- [x] Unit — Documents.test.tsx deep link + zero matches + unavailable
- [x] E2E — documents-search-cuj.spec.ts
- [ ] CI lint/type/build — on draft PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-SEARCH-01: Search control visible
- [x] CUJ-SEARCH-02: `?q=` deep link
- [x] CUJ-SEARCH-03: Semantic unavailable honesty
- [x] CUJ-SEARCH-04: Honest zero semantic matches

## 7) Observability & Ops
- Toasts retained on semantic failure; no new backend metrics

## 8) Release Plan
- Draft PR → conveyor merge → staging tip==SHA → prod tip==LIVE

## 9) Rollback Plan
- Revert squash-merge; redeploy prior tip

## 10) Evidence Pack
- Gate 0/1: this ledger + exclusive allowlist
- Gates 2–5: CI / staging / prod after merge

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Exclusive allowlist (Documents search only)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging tip==SHA
- [ ] **Gate 4:** Prod tip==SHA
- [ ] **Gate 5:** Evidence pack updated

## Test plan
- [x] `npm test -- Documents` (unit)
- [ ] `npx playwright test documents-search-cuj.spec.ts`
- [ ] Staging tip after merge
- Do **not** merge until conveyor review
