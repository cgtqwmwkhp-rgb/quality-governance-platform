# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Align risk-register API client with FastAPI/OpenAPI (bowtie + KRI value)
- **User goal:** Prevent 404/405 when UI starts calling bowtie element CRUD or KRI value updates.
- **In scope:** `riskRegisterApi.addBowtieElement`, `deleteBowtieElement`, `updateKRIValue` paths/methods; regression tests.
- **Out of scope:** Bow-tie visual wiring in `RiskRegister.tsx` (still static UX); backend route changes.
- **Feature flag:** None

## 2) Impact Map
- **Frontend:** `frontend/src/api/client.ts`, new `riskRegisterPaths.ts` + test
- **Backend:** None
- **APIs:** Client only — paths now match `src/api/routes/risk_register.py` L318, L355, L417 and OpenAPI `/bowtie/elements`, `/kris/{id}/value` PUT

## 3) Compatibility & Data Safety
- **Compatibility:** Client-only fix; backward-compatible for servers already exposing correct routes.
- **Breaking changes:** None (callers previously would have failed against correct backend).

## 4) Acceptance Criteria
- [x] Bowtie POST targets `.../bowtie/elements`
- [x] Bowtie DELETE targets `.../bowtie/elements/{element_id}`
- [x] KRI value uses HTTP PUT with `{ value }` body
- [x] Vitest regression for path templates

## 5) Testing Evidence
- [x] Lint — `npm run lint`
- [x] Typecheck — `tsc --noEmit`
- [x] Unit — `vitest run src/api/riskRegisterPaths.test.ts` + full FE suite via `make pr-ready`

## 6) Critical Journeys
- [x] CUJ-04 (risk register): API client contract alignment (future bowtie/KRI features)

## 7) Observability & Ops
- N/A

## 8) Release Plan
- Merge → CI → staging (if triggered) → production dispatch per runbook after green staging

## 9) Rollback
- Revert PR; redeploy prior frontend build

## 10) Evidence Pack
- Local: `make pr-ready` pass on branch

---

# Gate Checklist
- [x] Gate 0–2: Change ledger + CI path defined
- [x] Gate 2: `make pr-ready` green on branch
- [ ] Gate 3–5: Post-merge staging/prod per org process
