# Change Ledger (CL-RR-W2-NOTES-ACTIVITY)

## 1) Summary
- **Feature / Change name:** RR-W2 — risk notes + activity audit trail
- **User goal (1–2 lines):** Comment on a risk profile and review a typed activity trail (assessments, notes) with tenant-scoped pagination.
- **In scope:** Alembic `risk_notes` + `risk_activity_events`; models; GET/POST `.../notes`, GET `.../activity`; assess path writes activity in same transaction; RiskProfile notes + activity panels; en/cy i18n; unit + Vitest
- **Out of scope:** W3 CAPA/calendar, Excel import (#1093), RiskHeatMap (HM-03), App.tsx, Layout.tsx, client.ts spine
- **Feature flag / kill switch:** N/A — additive tables/routes

## 2) Impact Map (what changed)
- **Frontend:** `RiskProfile.tsx` notes timeline + activity trail + append form; `riskRegisterClient.ts` list/create notes + list activity
- **Backend:** `risk_service.update_risk_assessment` appends `assessed` activity; `append_risk_note` writes note + `note_added` activity
- **APIs:** `GET/POST /api/v1/risk-register/{id}/notes`, `GET /api/v1/risk-register/{id}/activity` (paginated, typed Pydantic)
- **Schemas:** `RiskNoteCreate`, `RiskNoteItem`, `RiskNoteListResponse`, `RiskActivityEventItem`, `RiskActivityListResponse`
- **Database:** Alembic `20260723_rr_notes_act` — `risk_notes`, `risk_activity_events` (tenant_id NOT NULL, indexes)
- **Tests:** `test_risk_notes_activity.py`, `test_risk_service.py`, `RiskProfile.test.tsx`, `riskRegisterClient.test.ts`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive tables and routes; existing assess/profile unchanged for clients that omit notes/activity
- **Tolerant reader / strict writer:** FE handles empty lists; note body stripped server-side
- **Breaking changes:** None
- **Migration plan:** Solo Alembic tip — deploy migration before relying on notes/activity UI
- **Rollback strategy (DB):** Downgrade drops `risk_activity_events` then `risk_notes`

## 4) Acceptance Criteria (AC)
- [x] AC-01: `risk_notes` table with tenant_id NOT NULL, risk_id FK, body, created_by_id, created_at + indexes
- [x] AC-02: `risk_activity_events` table with tenant_id NOT NULL, risk_id FK, event_type, summary, payload JSONB, actor_id, created_at + indexes
- [x] AC-03: GET/POST `/{id}/notes` and GET `/{id}/activity` paginated with typed schemas
- [x] AC-04: Assess path writes activity event in same transaction as history
- [x] AC-05: RiskProfile notes panel + activity trail + append note form
- [x] AC-06: Soft en/cy i18n for new strings
- [x] AC-07: Unit tests for models/routes/service; Vitest for profile panels

## 5) Testing Evidence (link to runs)
- [x] Unit — `pytest tests/unit/test_risk_notes_activity.py tests/unit/test_risk_service.py` (local)
- [x] Vitest — `RiskProfile.test.tsx`, `riskRegisterClient.test.ts` (local)
- [ ] CI — linked after push

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Profile loads notes + activity lists alongside existing hero/assess/trend
- [x] **CUJ-02:** Append note → POST notes → activity trail refreshes with `note_added`
- [x] **CUJ-03:** Assess → history + `assessed` activity in one transaction

## 7) Observability & Ops
- **Logs:** `trackError` on note create failure
- **Cache:** note create invalidates risk-register tenant cache

## 8) Release Plan
- **Staging:** Run migration → open risk profile → add note → assess → confirm activity trail

## 9) Rollback Plan
- **Rollback trigger:** Migration failure or notes/activity 500s
- **Rollback steps:** Revert PR; downgrade Alembic if applied
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

## Exclusive allowlist (this PR)
- `alembic/versions/20260723_rr_notes_activity.py`
- `src/domain/models/risk_register.py`
- `src/domain/models/__init__.py`
- `src/domain/services/risk_service.py`
- `src/api/schemas/risk_register.py`
- `src/api/routes/risk_register.py`
- `tests/unit/test_risk_notes_activity.py`
- `tests/unit/test_risk_service.py`
- `frontend/src/pages/RiskProfile.tsx`
- `frontend/src/pages/__tests__/RiskProfile.test.tsx`
- `frontend/src/api/riskRegisterClient.ts`
- `frontend/src/api/riskRegisterClient.test.ts`
- `frontend/src/i18n/locales/en.json` (`risk_register.profile.*` additions)
- `frontend/src/i18n/locales/cy.json` (`risk_register.profile.*` additions)
- `scripts/governance/pr_body_rr_w2_notes_activity.md`
