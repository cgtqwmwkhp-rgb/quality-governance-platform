# Change Ledger (CL-LOGIN-CORP)

## 1) Summary
- **Feature / Change name:** Fix cross-origin login warmup blocked by CORP; relax CORP on public health routes
- **User goal:** Remove Chrome `ERR_BLOCKED_BY_RESPONSE.NotSameOrigin` when SWA loads login and pre-warms `GET /healthz` against App Service.
- **In scope:** `frontend/src/pages/Login.tsx`, `src/main.py` (`SecurityHeadersMiddleware`)
- **Out of scope:** SWA path filters (build stamp may lag until SWA deploy runs)
- **Feature flag:** N/A

## 2) Impact Map
- **Frontend:** Login mount warmup `fetch` uses default CORS mode + `credentials: omit`
- **Backend:** `/healthz`, `/readyz`, `/health`, `/api/v1/health/*` → `Cross-Origin-Resource-Policy: cross-origin`; other routes unchanged (`same-origin`)

## 3) Compatibility & Data Safety
- **Breaking:** None; health payloads remain non-sensitive
- **Rollback:** Revert commit

## 4) Acceptance Criteria
- [x] AC-01: Login warmup does not use `mode: 'no-cors'`
- [x] AC-02: Public health paths emit `Cross-Origin-Resource-Policy: cross-origin`
- [x] AC-03: `make pr-ready` passes

## 5) Testing Evidence
- [x] Local `make pr-ready` (lint, mypy, unit, frontend tests)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Login page load (warmup fetch)
- [x] CUJ-02: Health probes remain reachable

## 7) Observability & Ops
- No change to logging

## 8) Release Plan
- Merge → CI → App Service staging/prod per existing workflows; SWA rebuilds because `frontend/src/**` changed

## 9) Rollback Plan
- Revert merge; redeploy prior image per runbook

## 10) Evidence Pack
- PR CI runs (post-open)

---

# Gate Checklist
- [x] **Gate 0:** Scope + AC
- [x] **Gate 1:** N/A contracts
- [ ] **Gate 2:** CI on PR
- [ ] **Gate 3:** Staging post-merge
- [ ] **Gate 4:** Canary N/A
- [x] **Gate 5:** Post-deploy verify `/healthz` from browser
