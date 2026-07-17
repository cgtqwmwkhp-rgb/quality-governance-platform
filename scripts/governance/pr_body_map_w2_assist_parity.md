# Change Ledger (CL-MAP-W2-ASSIST-PARITY)

**Path claim:** `path11/map-w2-assist-parity`

## File allowlist (exclusive)

- `frontend/src/pages/AuditTemplateBuilder.tsx`
- `frontend/src/pages/builderMapAssistHonesty.ts`
- `frontend/src/pages/__tests__/builderMapAssistHonesty.test.ts`
- `frontend/src/pages/workforce/AssessmentCreate.tsx`
- `frontend/src/pages/workforce/__tests__/AssessmentCreate.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_map_w2_assist_parity.md`

**Zero overlap** with parallel lanes: PlanetMark*, Calendar*, AuditExecution* (#1076), PortalIncidentForm* (#1077), ComplaintDetail* (#1078), IMSDashboard (#1074 merged), Layout/App/client.ts, `api/__init__.py`, Alembic. Soft i18n only.

## 1) Summary

- **Feature / Change name:** Path11 MAP-W2 — Assist / standards mapping honesty parity on Inspection + Competency builders
- **User goal:** Authors on Inspection Template Builder and Competency assessment create see ISO / Planet Mark / UVDB Assist honesty plus live Template Stats ISO-clause coverage — never faux multi-scheme accept chips.
- **In scope:** Inspection builder Template Stats coverage + Assist honesty panel; Competency create parity panel; helper + vitest; flat en/cy keys
- **Out of scope:** Live Assist Map accept chips (MAP-W3 / MAP-04); Audit Execution photos; IMSDashboard; Alembic
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Inspection Template Stats | Sections / questions only | + manual ISO clause coverage % |
| Inspection Assist | AI generates sections only | Honesty panel + scheme chips (manual ISO vs Assist awaiting) |
| Competency create | Template picker only | Parity honesty + ISO / Planet Mark / UVDB awaiting chips |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** FE-only honesty; no API/Alembic
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Inspection Template Stats shows ISO clause coverage from Advanced Settings text
- [x] AC-02: Inspection Assist honesty panel shows ISO / Planet Mark / UVDB chips without faux accept
- [x] AC-03: Competency assessment create shows Assist parity honesty + awaiting scheme chips
- [x] AC-04: Helper keeps acceptedMultiSchemeLinks at 0 and assistMapLive false
- [x] AC-05: Vitest covers helper + AssessmentCreate MAP-W2 panel
- [x] AC-06: en + cy flat keys (≥95% cy for new keys)

## 5) Testing Evidence

- [x] Vitest — builderMapAssistHonesty + AssessmentCreate MAP-W2
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Audit templates → edit → Template Stats ISO coverage + Assist honesty visible
- [x] CUJ-02: Workforce → New Assessment → Assist parity honesty visible before create

## 7) Observability & Ops

- **Playwright hooks:** `map-w2-assist-panel`, `map-w2-iso-coverage`, `map-w2-scheme-chips`, `map-w2-competency-assist-panel`
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change

## 8) Release Plan

1. Draft PR → CI green (Change Ledger + required checks)
2. Squash-merge after review when required checks green (human — **do not merge from this lane**)
3. Staging smoke: Inspection builder Template Stats + Competency create Assist panel

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA
- **Rollback trigger:** Builder honesty regression post-deploy
- **Rollback steps:** Revert squash commit; redeploy previous SHA
- **Owner:** Platform team

## 10) Evidence Pack (links)

- PR diff + vitest proofs in this branch
- Living tracker checklist id **MAP-W2**

## 11) Gate Checklist

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Path claim exclusive (Inspection/Competency builders + helper/tests + soft i18n)
- [x] **Gate 2:** Local vitest green
- [ ] **Gate 3:** Required CI green on PR
- [ ] **Gate 4:** Squash-merge to main (serial tip LIVE)
- [ ] **Gate 5:** Azure/SWA bake + smoke Inspection + Competency Assist honesty

## Test plan

- [x] `cd frontend && npx vitest run src/pages/__tests__/builderMapAssistHonesty.test.ts src/pages/workforce/__tests__/AssessmentCreate.test.tsx`
- [ ] Manual: `/audit-templates/:id/edit` — Template Stats coverage + Assist panel
- [ ] Manual: `/workforce/assessments/new` — Competency Assist parity panel
