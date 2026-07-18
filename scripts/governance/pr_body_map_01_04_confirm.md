# Change Ledger (CL-MAP-01-04-CONFIRM)

**Path claim:** `path11/flag-map-01-04-confirm`

## File allowlist (exclusive)

- `frontend/src/pages/AuditTemplateBuilder.tsx`
- `frontend/src/pages/audit-builder/types.ts`
- `frontend/src/pages/audit-builder/templateHelpers.ts`
- `frontend/src/pages/audit-builder/QuestionEditor.tsx`
- `frontend/src/pages/workforce/AssessmentCreate.tsx`
- `frontend/src/pages/workforce/__tests__/AssessmentCreate.test.tsx`
- `frontend/src/pages/builderMapAssistHonesty.ts`
- `frontend/src/pages/builderMapAssistApi.ts`
- `frontend/src/pages/mapW3StaleRescoreHonesty.ts`
- `frontend/src/pages/__tests__/builderMapAssistHonesty.test.ts`
- `frontend/src/pages/__tests__/mapW3StaleRescoreHonesty.test.ts`
- `src/api/routes/ai_templates.py`
- `src/domain/services/builder_standard_link_service.py`
- `tests/unit/test_builder_standard_link_service.py`
- `scripts/governance/pr_body_map_01_04_confirm.md`

**Zero overlap** with DENY lanes: InvestigationDetail*, Investigations.tsx, Actions*, RiskRegister*, DocumentControl, Layout, PlanetMark OCR, Alembic, `api/__init__.py`.

## 1) Summary

- **Feature / Change name:** Path11 MAP-01..04 — Standards confirm-loop persist (flag debt PR-7)
- **User goal:** Authors on Audit / Inspection / Competency builders can suggest multi-scheme question↔standard links, Accept / Edit / Reject them, and see live coverage % from persisted accepted links — not free-text `isoClause` alone.
- **In scope:** Suggest + decide + coverage APIs on `/ai-templates`; persist on `assessor_guidance_json` + evidence-link mirror; builder Assist Map CTA + Advanced Settings confirm chips; Competency create coverage readout; honesty helpers live.
- **Out of scope / leftover:** Bulk Accept drawer; Gemini-grounded suggest (keyword/ISO/UVDB/PM libraries used); soft publish gate; i18n cy keys for new English strings; IMSDashboard re-score wire-up beyond helpers.
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Link model | Free-text `isoClause` only | Multi-scheme links in `assessor_guidance_json.map_standard_links` |
| AI Assist | Generate sections / honesty chips offline | Suggest standards mappings (ISO / Planet Mark / UVDB) |
| Confirm loop | Honesty-only awaiting | Accept / Edit / Reject → persisted + coverage % |
| Template Stats | Manual ISO % | + multi-scheme coverage from accepted links |
| Competency create | Awaiting chips | Live coverage from selected template |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** No Alembic — reuse `assessor_guidance_json` + polymorphic `ComplianceEvidenceLink` (`entity_type=audit_question`)
- **Breaking changes:** None (`assistMapLive` now true when not stale)
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Multi-scheme link model beyond free-text isoClause
- [x] AC-02: Assist suggest endpoint returns ranked ISO / Planet Mark / UVDB candidates
- [x] AC-03: Accept / Edit / Reject persists links + mirrors evidence confirm/reject spine
- [x] AC-04: Template Stats shows multi-scheme coverage %
- [x] AC-05: Wired on AuditTemplateBuilder + AssessmentCreate (competency)
- [x] AC-06: Unit + Vitest coverage for helpers/service
- [ ] AC-07: Required CI green on PR

## 5) Testing Evidence

- [x] Unit — `test_builder_standard_link_service`
- [x] Vitest — builderMapAssistHonesty + mapW3StaleRescoreHonesty + AssessmentCreate
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01 (unit): Suggest → accept → coverage increases
- [x] CUJ-02 (builder): Assist Map CTA + Advanced Settings chips
- [x] CUJ-03 (competency): Template select shows persisted coverage when available

## 7) Observability & Ops

- **Playwright hooks:** `map-04-suggest-cta`, `map-04-multi-scheme-coverage`, `map-confirm-chips-*`, `map-04-competency-coverage`
- **Logs:** `AiDecisionLog` actions `builder_standard_link_{accept|edit|reject}`
- **Metrics:** No change
- **Alerts:** No change

## 8) Release Plan

1. Draft PR → CI green (Change Ledger + required checks)
2. Squash-merge after review when required checks green (human — **do not merge from this lane**)
3. Staging smoke: edit template → Suggest → Accept → coverage updates; competency create coverage

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA
- **Rollback trigger:** Builder mapping persist regression
- **Owner:** Platform team

## 10) Evidence Pack (links)

- PR diff + unit/vitest proofs in this branch
- Living tracker checklist ids **MAP-01…MAP-04**

## 11) Gate Checklist

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Path claim exclusive (builders + map helpers + ai-templates persist)
- [x] **Gate 2:** Local unit + vitest green
- [ ] **Gate 3:** Required CI green on PR
- [ ] **Gate 4:** Squash-merge to main (serial tip LIVE)
- [ ] **Gate 5:** Azure/SWA bake + smoke Assist Map confirm loop

## Test plan

- [x] `pytest tests/unit/test_builder_standard_link_service.py -q`
- [x] `cd frontend && npx vitest run src/pages/__tests__/builderMapAssistHonesty.test.ts src/pages/__tests__/mapW3StaleRescoreHonesty.test.ts src/pages/workforce/__tests__/AssessmentCreate.test.tsx`
- [ ] Manual: `/audit-templates/:id/edit` — Suggest → Accept → multi-scheme coverage
- [ ] Manual: `/workforce/assessments/new` — select template → coverage readout
