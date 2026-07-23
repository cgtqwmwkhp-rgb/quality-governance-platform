# Change Ledger (CL-SHAREPOINT-SEARCH-PALETTE)

## 1) Summary
- **Feature / Change name:** SharePoint-style top search palette + honest suggestions + NL interpret
- **User goal (1–2 lines):** Open global search from the header / ⌘K as an overlay that keeps the current page mounted; structured suggestion chips that work; fail-closed NL→FTS interpret; click-through to records.
- **Depends on:** Existing FTS `GET /api/v1/search` + Gemini stack
- **In scope:** Layout palette overlay; shared search hook/panel; `entity_id`/`path` on results; `POST /search/interpret` (rules → Gemini → keyword); structured suggestion chips; en/cy i18n; unit/FE tests; this Change Ledger
- **Out of scope:** Copilot chat replacement; document semantic search as global default; sidebar IA changes
- **Feature flag / kill switch:** Gemini path fails closed to keyword FTS (no new flag)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `Layout.tsx` (palette open state); `GlobalSearchPalette` / `GlobalSearchPanel` / `useGlobalSearch` / `suggestedSearches`; `GlobalSearch.tsx` reused shared panel; `searchApi.interpret`
- **Backend (handlers/services):** `search_paths.py`; `search_interpret_service.py`; `search_service.py` (`entity_id`/`path`, date/status filters); `global_search.py` schema + interpret route
- **APIs (endpoints changed/added):** `GET /api/v1/search` response adds `entity_id`, `path`; passes `date_from`/`date_to`; new `POST /api/v1/search/interpret`
- **Schemas/contracts:** Search result + interpret response models
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** Reuses `GOOGLE_GEMINI_API_KEY` / `USE_GOOGLE_GENAI` / `GEMINI_MODEL`
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive API fields; interpret fail-closed to keyword
- **Tolerant reader / strict writer applied?** Yes — FE treats missing `path` as non-navigable
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — redeploy prior SHA

## 4) Acceptance Criteria (AC)
- [x] AC-01: Header search / ⌘K opens overlay; does not navigate to `/search`
- [x] AC-02: Esc / backdrop closes palette; underlying route remains mounted
- [x] AC-03: Suggested searches are structured (not fake AI NL) and drive filters or list routes
- [x] AC-04: Result click navigates via `path` and closes palette
- [x] AC-05: `POST /search/interpret` rules → Gemini → keyword; allowlist validated
- [x] AC-06: Unit + FE tests cover path builder, interpret, Layout palette, chips

## 5) Testing Evidence (link to runs)
- [x] Local — pytest search paths/interpret; vitest GlobalSearch/Layout/Palette
- [ ] CI — this PR
- [ ] Staging — manual ⌘K on RTA detail after deploy

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: From `/rtas/:id`, open palette via header without leaving RTA (Layout test)
- [x] CUJ-02: Esc closes palette (Palette test)
- [x] CUJ-03: Result select closes palette and navigates (Palette test)
- [x] CUJ-04: Structured chip fires filtered FTS (Palette test)

## 7) Observability & Ops
- **Logs:** Interpret Gemini failures logged at info (fail-closed)
- **Metrics:** Existing `search.query` / `search.executed`
- **Alerts:** None new
- **Runbook updates:** None

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** ⌘K on RTA detail; Esc; select result; try “overdue actions” chip
- **Canary plan:** N/A — UX + additive API
- **Prod post-deploy checks:** Same as staging smoke

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Search overlay broken or interpret 500s blocking search
- **Rollback steps:** Redeploy prior SHA (FE can still call keyword search if interpret removed)
- **Owner:** Governance / Quality platform team

## 10) Evidence Pack (links)
- CI run(s): Linked on this PR checks tab
- Staging deploy evidence: After merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (additive search fields + interpret)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging smoke — ⌘K overlay on RTA detail
- [x] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
