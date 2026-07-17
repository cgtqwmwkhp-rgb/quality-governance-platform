# Change Ledger (CL-RR-W1-ASSESS-TREND)

## 1) Summary
- **Feature / Change name:** RR-W1 — Assess SSOT + net-score auto-trend + profile chart
- **User goal (1–2 lines):** Assess a risk from its profile page, persist scores + history atomically, and see net-score direction and monthly trend.
- **In scope:** `POST /api/v1/risk-register/{id}/assess` single-transaction history+scores; auto trend from last two net scores (+ manual override); review dates on assess; profile trend/chart + assess form; typed DTOs; en/cy i18n; unit + Vitest
- **Out of scope:** W2 notes/activity migrations, W3 CAPA, calendar, import, Layout.tsx, App.tsx, client.ts spine, Alembic
- **Feature flag / kill switch:** N/A — extends existing assess + profile routes

## 2) Impact Map (what changed)
- **Frontend:** `RiskProfile.tsx` trend chart + assess form; `riskRegisterClient.ts` assess payload + `getTrends(riskId)` filter
- **Backend:** `risk_service.update_risk_assessment` atomic commit; trend helpers; profile + assess responses include trend/review dates
- **APIs:** `POST .../assess` returns trend + review dates; `GET .../profile` adds likelihood/impact + trend; `GET .../trends?risk_id=` used by profile chart
- **Schemas:** `RiskProfileResponse`, `RiskAssessmentResponse`, route `RiskAssessmentUpdate`
- **Database:** None (trend persisted in existing `tags` JSON; activity event TODO for W2)
- **Tests:** `test_risk_service.py`, `test_risk_register_profile.py`, `RiskProfile.test.tsx`, `riskRegisterClient.test.ts`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive profile fields; assess body unchanged for existing clients omitting new optional fields
- **Tolerant reader / strict writer:** FE handles empty trend series; assess form defaults from profile scores
- **Breaking changes:** `riskRegisterApi.assess` payload now uses inherent/residual likelihood+impact (matches backend schema)
- **Migration plan:** N/A
- **Rollback strategy:** Revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Assess writes `risk_assessment_history` and updates scores in one DB transaction
- [x] AC-02: Auto trend increasing|stable|decreasing from last two net scores; manual `trend` override supported
- [x] AC-03: Review dates on assess path; surfaced on profile hero
- [x] AC-04: Profile net-score trend chart from `GET .../trends?risk_id=`
- [x] AC-05: Profile assess form posts to assess and reloads profile
- [x] AC-06: Typed `RiskProfileResponse` / client types extended
- [x] AC-07: Soft en.json/cy.json keys for new strings only
- [x] AC-08: TODO comment for W2 activity events (no invented migration)

## 5) Testing Evidence (link to runs)
- [x] Unit — `pytest tests/unit/test_risk_service.py tests/unit/test_risk_register_profile.py` (local, py3.11)
- [x] Vitest — `RiskProfile.test.tsx`, `riskRegisterClient.test.ts` (local)
- [ ] CI — linked after push

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-1:** Profile loads → trend chart + badge → assess submit → profile reload with updated scores/reviews

## 7) Observability & Ops
- **Logs:** `trackError` on load/assess failure
- **Cache:** assess invalidates risk-register tenant cache

## 8) Release Plan
- **Staging:** Open profile → submit assess → confirm chart + trend badge update

## 9) Rollback Plan
- **Trigger:** Assess 500 / profile blank / history drift
- **Steps:** Revert PR

## 10) Evidence Pack
- CI run(s): linked after PR creation

---

# Gate Checklist
- [x] Gate 0: Scope lock + Change Ledger
- [x] Gate 1: Implementation + local tests
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification

## Exclusive allowlist (this PR)
- `src/domain/services/risk_service.py`
- `src/api/schemas/risk_register.py`
- `src/api/routes/risk_register.py`
- `tests/unit/test_risk_service.py`
- `tests/unit/test_risk_register_profile.py`
- `frontend/src/pages/RiskProfile.tsx`
- `frontend/src/pages/__tests__/RiskProfile.test.tsx`
- `frontend/src/api/riskRegisterClient.ts`
- `frontend/src/api/riskRegisterClient.test.ts`
- `frontend/src/i18n/locales/en.json` (`risk_register.profile.*` additions)
- `frontend/src/i18n/locales/cy.json` (`risk_register.profile.*` additions)
- `scripts/governance/pr_body_rr_w1_assess_trend.md`
