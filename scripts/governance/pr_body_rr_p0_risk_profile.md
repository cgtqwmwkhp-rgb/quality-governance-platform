# Change Ledger (CL-RR-P0-RISK-PROFILE)

## 1) Summary
- **Feature / Change name:** RR-P0 — Risk Profile page + typed profile API DTO
- **User goal (1–2 lines):** Open a risk from the register/heatmap into a real profile view (Excel Risk Card shell) instead of only a dialog.
- **In scope:** `GET /api/v1/risk-register/{id}/profile` → `RiskProfileResponse`; `RiskProfile.tsx` at `/risk-register/:riskId`; App route; register/heatmap Open → profile; `riskRegisterApi.getProfile`; soft en/cy i18n keys; unit + Vitest; this ledger
- **Out of scope:** Notes table, activity events, assess UI, CAPA create panel, calendar feed, Excel import, Alembic, Layout.tsx, client.ts, api/__init__.py, W1–W5
- **Feature flag / kill switch:** N/A — additive profile route + typed GET

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `RiskProfile.tsx` (new); `App.tsx` route; `RiskRegister.tsx` Open/heatmap → `/risk-register/:id`; create/edit/triage dialogs retained
- **Backend (handlers/services):** `risk_register.py` profile endpoint (tenant fail-closed)
- **APIs (endpoints changed/added):** `GET /api/v1/risk-register/{risk_id}/profile`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `RiskProfileResponse` (+ reuse `AssessmentHistoryItem`); FE `RiskProfile` type + `getProfile`
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive `/profile` endpoint; existing `GET /{id}` unchanged for dialog/detail consumers
- **Tolerant reader / strict writer applied?** Yes — FE loading/error/404 honesty; null scores → null levels
- **Breaking changes:** None (Open button navigates to profile instead of view dialog; edit/create/triage dialogs kept)
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Typed `RiskProfileResponse` with required profile fields + assessment_history + linked_actions + review_notes
- [x] AC-02: `GET .../profile` tenant fail-closed (404 cross-tenant / missing)
- [x] AC-03: Risk Profile page hero (ref, title, status, category, Gross/Net, owner, updated, last/next review) + back link
- [x] AC-04: Loading / error / not-found honesty
- [x] AC-05: Register + heatmap primary Open navigates to `/risk-register/:id`
- [x] AC-06: `riskRegisterClient.getProfile` + Vitest smoke + register navigate
- [x] AC-07: Soft en.json/cy.json keys only; exclusive allowlist

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `tests/unit/test_risk_register_profile.py` (6 passed, local)
- [x] Frontend Vitest — `RiskProfile.test.tsx`, register Open navigate, `riskRegisterClient.test.ts` (local)
- [ ] Integration tests — N/A (route unit-tested)
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke — N/A for P0 shell

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-1 (RR):** Register/heatmap → Open → Risk Profile hero loads from typed `/profile` API (ref, scores, owner, reviews); back to register; 404/error honesty
- [x] CUJ-1b: Create/edit/triage dialogs remain available on register (Open no longer hijacks edit/triage)

## 7) Observability & Ops
- **Logs:** `trackError` on profile load failure
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open a known risk from register Open; confirm `/risk-register/:id` hero; confirm wrong-tenant/missing id shows not-found
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check one register Open → profile

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Profile route 500s / FE blank / register Open broken
- **Rollback steps:** Revert PR
- **Owner:** Platform / Risk Register track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A (draft)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Typed profile DTO + FE page + Open navigation
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Rollback plan verified
- [ ] **Gate 5:** Evidence pack linked / LIVE honesty noted

## Exclusive allowlist (this PR)
- `src/api/schemas/risk_register.py`
- `src/api/routes/risk_register.py`
- `tests/unit/test_risk_register_profile.py`
- `frontend/src/pages/RiskProfile.tsx`
- `frontend/src/pages/__tests__/RiskProfile.test.tsx`
- `frontend/src/pages/RiskRegister.tsx`
- `frontend/src/pages/__tests__/RiskRegister.test.tsx`
- `frontend/src/App.tsx`
- `frontend/src/api/riskRegisterClient.ts`
- `frontend/src/api/riskRegisterClient.test.ts`
- `frontend/src/i18n/locales/en.json` (`risk_register.profile.*` only)
- `frontend/src/i18n/locales/cy.json` (`risk_register.profile.*` only)
- `scripts/governance/pr_body_rr_p0_risk_profile.md`

**Forbidden / not touched:** Layout.tsx, client.ts, api/__init__.py, Alembic, CAPA redesign, W1–W5 notes/assess/calendar/import.
