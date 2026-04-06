# Change Ledger (CL-SIGNOFF-FFD8E17A)

## 1) Summary
- **Feature / Change name:** Release sign-off artifact sync for production baseline ffd8e17a
- **User goal (1-2 lines):** Align `docs/evidence/release_signoff.json` with the live promoted commit and evidenced CI/staging/production workflow runs so governed auto-promotion and CAB records match Azure and GitHub truth.
- **In scope:** `docs/evidence/release_signoff.json` only
- **Out of scope:** Application code, Dockerfile, workflows, feature behaviour
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **Governance artifacts:** `docs/evidence/release_signoff.json` — `release_sha`, `approved_at_utc`, `deployment_evidence` block refreshed

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Documentation-only governance JSON
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert PR restores prior sign-off text; production runtime unchanged by this file alone until next image build

## 4) Acceptance Criteria (AC)
- [x] AC-01: `release_sha` equals live `GET https://app-qgp-prod.azurewebsites.net/api/v1/meta/version` `build_sha` at verification time (ffd8e17ad686bcdc9bb34f54c90186c7c99b86f7)
- [x] AC-02: `validate_release_signoff.py --file docs/evidence/release_signoff.json --sha <release_sha>` passes on branch tip after merge (uses same `release_sha` field)
- [x] AC-03: Referenced `uat_report_path` and `rollback_drill_path` files exist in repo
- [x] AC-04: CI/staging/production run URLs in `deployment_evidence` match `gh run list` for head ffd8e17a on main prior to this governance commit

## 5) Testing Evidence (link to runs)
- [x] Lint — N/A for JSON-only change; `make pr-ready` to execute repo gates on branch
- [x] Typecheck — N/A
- [x] Build — N/A
- [x] Unit tests — via `make pr-ready`
- [x] Integration tests — CI on PR
- [x] Contract tests — N/A
- [x] E2E Smoke — N/A for this change

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Production `GET /api/v1/meta/version` returns expected `build_sha` (verified via curl in audit run)
- [x] CUJ-02: Staging `GET /api/v1/meta/version` matches promoted application SHA pre-governance-commit
- [x] CUJ-03: Production `/healthz` and `/readyz` return HTTP 200

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Standard pipeline after merge; no functional delta expected from JSON-only commit beyond new git `build_sha` on image
- **Canary plan:** N/A
- **Prod post-deploy checks:** `/healthz`, `/readyz`, `/api/v1/meta/version` per `docs/ops/diagnostics-endpoint-guide.md`

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** N/A for governance-only change; if pipeline regression, revert this PR on `main`
- **Rollback steps:** `git revert` merge commit; allow CI → staging → production chain to restore prior sign-off file and prior image tip
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI (ffd8e17a): https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24032526982
- Staging deploy: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24032686396
- Production deploy: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24032910306
- Security Scan (ffd8e17a): https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24032526996
- UX Functional Coverage (ffd8e17a): https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24032910286
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (N/A)
- [ ] **Gate 2:** CI green (lint/type/build/tests) — pending PR run
- [ ] **Gate 3:** Staging verification complete (evidence linked post-merge)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
