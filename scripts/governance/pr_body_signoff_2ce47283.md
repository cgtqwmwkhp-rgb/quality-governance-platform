# Change Ledger (CL-SIGNOFF-2CE47283)

## 1) Summary
- **Feature / Change name:** Align release sign-off with live promoted SHA 2ce47283; harden PR body template CUJ tokens
- **User goal (1-2 lines):** Remove false statements in `release_signoff.json` (file claimed ffd8e17a live while Azure/HTTP report 2ce47283); prevent future PRs from failing Change Ledger Enforcement when copying the template.
- **In scope:** `docs/evidence/release_signoff.json`, `scripts/governance/pr_body_template.md`
- **Out of scope:** Application logic, Dockerfile, Azure config
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** None
- **APIs:** None
- **Database:** None
- **Workflows:** None
- **Governance:** `release_signoff.json` — `release_sha` and `deployment_evidence` aligned to merge **2ce47283** and runs **24035104103** / **24035302378** / **24035515675** / UX **24035515685**; `pr_body_template.md` — CUJ section uses **CUJ-01**..**CUJ-03** labels per `.github/workflows/change-ledger-enforcement.yml`

## 3) Compatibility & Data Safety
- **Compatibility:** Governance JSON + docs only
- **Breaking changes:** None for runtime APIs
- **Rollback:** Revert merge on `main`; redeploy prior tip if required

## 4) Acceptance Criteria (AC)
- [x] AC-01: `release_sha` equals live `GET https://app-qgp-prod.azurewebsites.net/api/v1/meta/version` `build_sha` (**2ce47283c44f24e74bf23af67ac27795d965960d**)
- [x] AC-02: `validate_release_signoff.py --file docs/evidence/release_signoff.json --sha 2ce47283c44f24e74bf23af67ac27795d965960d` exits 0
- [x] AC-03: Referenced `uat_report_path` and `rollback_drill_path` files exist
- [x] AC-04: `pr_body_template.md` section 6 contains at least **CUJ-01** and **CUJ-02** literal tokens

## 5) Testing Evidence (link to runs)
- [x] Lint — via `make pr-ready` on branch
- [x] Typecheck — via `make pr-ready`
- [x] Unit tests — via `make pr-ready`
- [x] PR CI — required checks on this PR
- [x] Integration / E2E — CI jobs on PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Production version endpoint returns expected `build_sha` (curl evidence before PR)
- [x] CUJ-02: Staging version endpoint matches same `build_sha`
- [x] CUJ-03: Production `/healthz` and `/readyz` return HTTP 200

## 7) Observability & Ops
- **Logs / metrics / alerts:** No change
- **Runbooks:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging / prod:** Standard auto chain after merge to `main`
- **Canary:** N/A

## 9) Rollback Plan (Mandatory)
- **Trigger:** Unexpected pipeline or runtime regression
- **Rollback steps:** `git revert` merge commit; follow `.github/workflows/rollback-production.yml` and `docs/runbooks/rollback-drills.md`
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI (2ce47283): https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24035104103
- Staging: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24035302378
- Production: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24035515675
- UX gate: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24035515685

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (N/A)
- [ ] **Gate 2:** CI green on PR
- [ ] **Gate 3:** Staging verification post-merge
- [ ] **Gate 4:** Canary (N/A)
- [x] **Gate 5:** Production verification plan documented
