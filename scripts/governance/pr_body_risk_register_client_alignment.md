# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Align risk-register API client with FastAPI/OpenAPI (bowtie + KRI value)
- **User goal:** Prevent 404/405 when UI calls bowtie element CRUD or KRI value updates.
- **In scope:** `riskRegisterApi.addBowtieElement`, `deleteBowtieElement`, `updateKRIValue`; `riskRegisterPaths.ts`; Vitest regression.
- **Out of scope:** Bow-tie visual wiring in `RiskRegister.tsx` (static UX unchanged); backend routes.

## 2) Impact Map (what changed)
- **Frontend:** `frontend/src/api/client.ts`, `frontend/src/api/riskRegisterPaths.ts`, `frontend/src/api/riskRegisterPaths.test.ts`
- **Backend:** None
- **APIs:** Client paths align with `src/api/routes/risk_register.py` L318, L355, L417 and OpenAPI bowtie/KRI paths
- **Database:** None
- **Workflows:** None

## 3) Compatibility & Data Safety
- **Compatibility:** Additive client fix; servers already exposed correct routes.
- **Breaking changes:** None

## 4) Acceptance Criteria (AC)
- [x] AC-01: Bowtie POST uses `/api/v1/risk-register/{id}/bowtie/elements`
- [x] AC-02: Bowtie DELETE uses `/api/v1/risk-register/{id}/bowtie/elements/{element_id}`
- [x] AC-03: KRI value update uses HTTP PUT with `{ value }` body

## 5) Testing Evidence (link to runs)
- [x] Lint: `npm run lint` (frontend)
- [x] Typecheck: `tsc --noEmit`
- [x] Unit: `vitest` `riskRegisterPaths.test.ts` + full FE suite via `make pr-ready` on branch
- [x] CI: PR checks workflow after push

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Portal / staff flows unaffected (no route changes)
- [x] CUJ-04: Risk register API client contract aligned for future bowtie/KRI UI

## 7) Observability & Ops
- **Logs:** N/A
- **Metrics:** N/A
- **Runbook updates:** None

## 8) Release Plan (Local -> Staging -> Prod)
- Merge to `main` → CI → staging deploy if triggered → manual production promotion per `deploy-production.yml`

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Regression on risk-register API calls in production UI
- **Rollback steps:** Revert merge commit; redeploy prior frontend static build / container tag per Azure runbook
- **Owner:** Platform / release manager

## 10) Evidence Pack (links)
- Local `make pr-ready` green on branch `fix/risk-register-client-openapi-alignment`
- GitHub Actions CI on PR #441

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** N/A API contract change on client only
- [x] **Gate 2:** CI green (lint/type/build/tests) on PR
- [x] **Gate 3:** Staging verification when deploy job runs on merge
- [x] **Gate 4:** N/A canary unless org requires
- [x] **Gate 5:** Production verification plan: healthz/readyz/version + smoke after deploy
