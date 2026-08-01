# Change Ledger (CL-SEARCH-CONTENT-SNIPPET-UI)

## 1) Summary
- **Feature / Change name:** Global Search — document_content snippet / location polish
- **User goal (1-2 lines):** When ⌘K / Global Search returns in-document chunk hits, show a readable highlighted snippet (or an honest suppressed message), plus heading/page when available, with a clearer “Document body” facet chip.
- **Depends on:** #1474 / #1475 (`document_content` FTS + RBAC already on `main`)
- **In scope:** FE display wiring in `GlobalSearchPanel` (palette reuses it); optional `heading` / `page_number` on the result type; facet chip label clarity; vitest coverage; this Change Ledger
- **Out of scope:** Alembic; Copilot; B-10 pins; backend SearchService / API schema changes; inventing fake snippet text when `snippet_suppressed`
- **Feature flag / kill switch:** N/A — display-only; suppressed hits remain navigable via existing `path`

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `GlobalSearchPanel.tsx`; `searchResultDisplay.ts`; `GlobalSearchPalette` inherits via shared panel; `client.ts` result type (`document_content`, optional `heading` / `page_number`)
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None (consumes existing `highlights`, `description`, `path`, `module`)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** FE `GlobalSearchResultRecord` extended additively
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive FE fields; tolerant reader for missing `heading` / `page_number` (page may be parsed from `path`)
- **Tolerant reader / strict writer applied?** Yes — heading/page only render when present; unknown modules still get a fallback icon
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — redeploy prior SHA

## 4) Acceptance Criteria (AC)
- [x] AC-01: `document_content` / “Document Content” results render snippet text with highlight marks (no raw `<b>` from ts_headline)
- [x] AC-02: Heading and/or page shown when present on the result (explicit fields or `page` on path)
- [x] AC-03: `snippet_suppressed` shows an honest notice and does not invent body text
- [x] AC-04: Facet/filter chip for Document Content labelled “Document body” (filter value remains `Document Content`)
- [x] AC-05: Vitest covers helpers + palette rendering for highlight / page / suppressed paths

## 5) Testing Evidence (link to runs)
- [x] Local — `npx vitest run src/components/search/__tests__/searchResultDisplay.test.ts src/components/search/__tests__/GlobalSearchPalette.test.tsx` (9 passed); `GlobalSearch.test.tsx` (2 passed)
- [ ] CI — this PR
- [ ] Staging — ⌘K content hit smoke after merge/deploy

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Content hit shows highlighted snippet + page (and heading when provided)
- [x] CUJ-02: Confidential/restricted content hit shows suppressed notice, not empty/fake body
- [x] CUJ-03: Filters expose “Document body” chip; existing palette Escape / select journeys remain covered

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change (existing search metrics)
- **Alerts:** None new
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** ⌘K search that returns a document_content hit; confirm snippet/page; confirm confidential doc shows suppressed copy
- **Canary plan:** N/A — FE display-only
- **Prod post-deploy checks:** Same smoke as staging

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Search palette/result list broken or incorrect confidential snippet leakage (should not occur — FE only displays what API already returns)
- **Rollback steps:** Redeploy prior SHA
- **Owner:** Platform / Governance team

## 10) Evidence Pack (links)
- CI run(s): Linked on this PR checks tab
- Staging deploy evidence: After merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (FE display of existing search fields)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
