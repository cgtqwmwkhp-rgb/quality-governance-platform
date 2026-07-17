# Change Ledger (CL-RR-W3-ACTIONS-UPSTREAM-OWNER)

## 1) Summary
- **Feature / Change name:** RR-W3 — Actions (CAPA SSOT) + upstream 360 + owner picker
- **User goal (1–2 lines):** From a risk profile, see CAPA actions bound by source join, create a follow-up action with returnTo, pick an owner, and inspect upstream cases/findings that link to the risk.
- **In scope:** GET/POST `/{id}/actions`, GET `/{id}/upstream`, PUT `/{id}/owner` (+ hardened PUT owner activity); CAPA-by-source list/create; case_risk_links reverse + audit_finding_risks; RiskProfile actions/upstream/owner panels; Actions create `sourceType=risk`; en/cy i18n; unit + Vitest
- **Out of scope:** Alembic / App.tsx / Layout.tsx / heat map / PlanetMark / RR-TITLE; **Action Plan sheet import → CAPA** deferred (W4 still honesty-skips `action_plan_skipped`)
- **Feature flag / kill switch:** N/A — additive routes/panels

## 2) Impact Map (what changed)
- **Frontend:** `RiskProfile.tsx` CAPA Actions panel, Upstream panel, owner UserEmailSearch; `riskRegisterClient.ts` list/create actions, upstream, owner, `buildRiskCreateActionHref`
- **Backend:** `risk_service` CAPA-by-source + owner activity + upstream reverse; `case_risk_links.list_case_links_for_risk` / `case_type_href`; `capa_service` RISK golden-thread source validation; `actions.py` create `source_type=risk` + activity emit
- **APIs:** `GET/POST /api/v1/risk-register/{id}/actions`, `GET .../upstream`, `PUT .../owner`; PUT `/{id}` owner fields emit `owner_changed`
- **Schemas:** `RiskActionCreate/Item/ListResponse`, `RiskUpstreamItem/Response`, `RiskOwnerUpdate/Response`
- **Database:** None (uses existing CAPA + case_risk_links + audit_finding_risks + risk_activity_events)
- **Tests:** `test_risk_actions_upstream.py`, `test_case_risk_links.py`, `RiskProfile.test.tsx`, `riskRegisterClient.test.ts`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoints; Actions create gains `risk` source
- **Tolerant reader / strict writer:** FE empty-state honesty; CAPA list ignores JSONB `linked_actions`
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: CAPA Actions panel lists `source_type=risk` & `source_id=risk.id` via server join (not JSONB-only)
- [x] AC-02: Create action from profile → CAPA bound to risk + activity; `returnTo` `/risk-register/:id`
- [x] AC-03: Owner User picker sets `risk_owner_id` + denormalized `risk_owner_name` + `owner_changed` activity
- [x] AC-04: Upstream panel reverse-queries `case_risk_links` + audit finding refs with deep-link hrefs
- [x] AC-05: Typed APIs GET/POST `/{id}/actions`, GET `/{id}/upstream`; PUT owner hardened
- [x] AC-06: Soft en/cy i18n keys for new profile strings
- [x] AC-07: Unit tests CAPA-by-source + upstream reverse; Vitest RiskProfile panels
- [x] AC-08: Action Plan import→CAPA **deferred** with honesty note (W4 `action_plan_skipped` remains)

## 5) Testing Evidence (link to runs)
- [x] Unit — `pytest tests/unit/test_risk_actions_upstream.py tests/unit/test_case_risk_links.py` (local)
- [x] Vitest — `RiskProfile.test.tsx`, `riskRegisterClient.test.ts` (local)
- [ ] CI — linked after push

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Open risk profile → hero/assess/notes/activity still load; actions + upstream panels present
- [x] **CUJ-02:** Assess → scores/history/trend unchanged path
- [x] **CUJ-03:** Note → append + activity refresh
- [x] **CUJ-04:** Action → Create action deep-link with `sourceType=risk` + `returnTo` profile; list shows CAPA-by-source
- [x] **CUJ-05:** Upstream → incident/finding deep links from reverse joins
- [x] **CUJ-06:** Owner → picker sets id+name and activity trail shows `owner_changed`

## 7) Observability & Ops
- **Logs:** `trackError` on owner/actions load failures
- **Cache:** owner/action create invalidates `risk-register` (+ `capa` on action create)

## 8) Release Plan
- **Staging:** Open risk profile with linked cases/CAPAs → create action via returnTo → change owner → confirm upstream links

## 9) Rollback Plan
- **Rollback trigger:** Actions/upstream 500s or owner update regressions
- **Rollback steps:** Revert PR (no migration)
- **Owner:** Platform / Risk Register track

## 10) Evidence Pack
- CI run(s): linked after PR creation

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + Change Ledger
- [x] **Gate 1:** Implementation + local tests
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Rollback plan verified
- [ ] **Gate 5:** Evidence pack linked

## Deferred (honesty)
- **Action Plan sheet → CAPA create:** W4 import dry-run still reports `action_plan_skipped=true`. No import-path CAPA create wired in this PR.
