# Change Ledger (CL-AUDIT-MAP-ASSIST-API-BASE)

## File allowlist (exclusive)
- `frontend/src/pages/builderMapAssistApi.ts`
- `frontend/src/pages/__tests__/builderMapAssistApi.test.ts`
- `frontend/src/pages/Standards.tsx`
- `frontend/src/pages/audit-builder/QuestionEditor.tsx`
- `frontend/staticwebapp.config.json`
- `scripts/governance/pr_body_audit_map_assist_api_base.md`

**Out of scope:** Backend mapper rewrite (already live on App Service); Document Spine; Dependabot.

## 1) Summary
- **Feature / Change name:** Fix Audit Builder Standards Map Assist HTTP 405 + ISO Standards deep-link
- **User goal:** “Suggest standards mappings” reaches the real API and accepted ISO refs open the Standards clause tree for inspection prep.
- **In scope:** Route Assist Map through shared axios `API_BASE_URL`; SWA `/api/*` fallback exclude; `/standards?code=&clause=` deep-link + highlight.
- **Out of scope:** Changing ISO keyword catalogue; new Alembic tables.
- **Feature flag / kill switch:** None — revert commit.

## 2) Impact Map (what changed)
- **Frontend:** `builderMapAssistApi` uses `api` axios (App Service), not relative `fetch` to SWA.
- **SWA:** `navigationFallback.exclude` includes `/api/*`.
- **Standards UX:** Query-param select + clause highlight/scroll for Assist refs like `9001-7.2`.
- **Builder UX:** ISO chips link to Standards.
- **Backend:** None (route already returns 401 when hit on App Service).

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive client routing fix; same suggest/decide contracts.
- **Tolerant reader / strict writer applied?** Yes.
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy (DB):** Revert commit; force_deploy prior SHA.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Suggest uses axios base URL (unit test asserts `api.post` path)
- [x] AC-02: SWA config excludes `/api/*` from SPA fallback
- [x] AC-03: `standardsHrefForIsoRef('9001-7.2')` → `/standards?code=ISO9001&clause=7.2`
- [x] AC-04: Standards page selects ISO9001 and highlights matching clause from query
- [x] AC-05: ISO map chips in QuestionEditor deep-link to Standards

## 5) Testing Evidence (link to runs)
- [x] Unit: `builderMapAssistApi.test.ts`
- [ ] CI — this PR
- [ ] Prod glance: Audit Builder → Suggest → Accept ISO → open Standards clause

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Suggest standards mappings no longer 405 on SWA origin
- [x] CUJ-02: Accepted ISO ref opens `/standards` clause for inspection prep

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** Existing API request ids
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Suggest on Audit Builder template with question text; confirm chips; open ISO link.
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same on tip SWA + App Service.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Suggest regressions / Standards deep-link broken
- **Rollback steps:** Revert squash-merge; force_deploy previous SHA
- **Owner:** Tip-owner

## 10) Evidence Pack (links)
- SWA POST `/api/v1/ai-templates/suggest-standard-links` → **405** Allow GET,HEAD,OPTIONS
- App Service same path → **401** AUTHENTICATION_REQUIRED (route live)
- Canvas: `qgp-audit-map-assist-405`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts — existing suggest/decide endpoints
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary — N/A
- [ ] **Gate 5:** Production verification plan ready
