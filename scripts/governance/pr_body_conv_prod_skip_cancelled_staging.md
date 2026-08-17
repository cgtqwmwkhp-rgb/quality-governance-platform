# Change Ledger (CL-CONV-PROD-SKIP-CANCELLED-STAGING)

> **Start gate:** #1782 LIVE — tip `ed1eeb3843d4`. `STACK_MAX=1`. Merge ≠ LIVE.
> Unattended LIVE hole: cancelling a pending Staging twin fires Production `workflow_run` with conclusion cancelled; Notify fail-closes even though Azure was never written.

## 1) Summary
- **Feature / Change name:** CONV-PROD-SKIP — ignore non-success Staging twins
- **User goal:** Duplicate Staging runs can be cancelled before Azure write without painting a Production deploy failure. The successful Staging twin still promotes.
- **In scope:** `deploy-production.yml` job `ignore-non-success-staging`; Notify `if` skips when the triggering Staging run was not success.
- **Out of scope:** Entra flag. A4 four columns. Exceptions 200. Invented scheme EXACT. S4 trees. AP-07b CE↔CE+ NEAR. Dependabot. Changing Staging itself.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| CPS-01 | Production `workflow_run` from cancelled Staging | Pre-checks skipped; B&D skipped; Notify always() fail-closes → run **failure** | Named ignore job succeeds; Notify does not run; not a deploy |
| CPS-02 | Production `workflow_run` from successful Staging that did not deploy | Notify release gate fail-closes (honest non-deploy) | Unchanged |
| CPS-03 | Manual `workflow_dispatch` / release | Unchanged | Unchanged |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Workflow `if` only. No app code, no schema, no flags.
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy:** Revert merge and redeploy `ed1eeb3843d4`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Honest Production conclusion | Cancelled Staging twin → red Production (looks like deploy failed) | Named ignore; production unchanged; not reported as deploy failure |
| False-green non-deploy after successful Staging | Release gate still fails the run when B&D skipped | Unchanged — still fail-closes |
| Azure write | Never written on cancelled-twin path | Still never written |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `ignore-non-success-staging` runs only when `workflow_run.conclusion != success`.
- [x] AC-02: Notify does not run on that path (no release-gate `exit 1`).
- [x] AC-03: Pre-deployment checks still require Staging conclusion `success`.
- [x] AC-04: Release gate text for skipped B&D after a successful Staging run is unchanged.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit (local): `tests/unit/test_deploy_production_ignore_cancelled_staging.py`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Cancelled Staging twin → Production ignore job, not a failed deploy.
- [x] CUJ-02: Successful Staging with B&D skipped → Notify release gate still fail-closes.

## 7) Observability & Ops
- Ignore job writes a step summary: Staging conclusion, URL, candidate SHA.
- Chase must still wait for a real Production **Build and Deploy SUCCESS (not skipped)** plus health SHA match.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (`STACK_MAX=1`; admin-squash authorised).
2. Staging deploy still required for the governed path even though this change is workflow-only.
3. Promote PROD; verify `/api/v1/health` version = main tip; Production **Build and Deploy SUCCESS (not skipped)**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** A cancelled Staging twin again fail-closes Production, or a successful Staging non-deploy concludes success.
- **Rollback steps:** Revert merge commit; redeploy prior tip `ed1eeb3843d4` via governed Staging → Production path.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `fix/conv-prod-skip-cancelled-staging`
- Ledger: `scripts/governance/pr_body_conv_prod_skip_cancelled_staging.md`
- Parent LIVE: #1782 @ `ed1eeb3843d4`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
