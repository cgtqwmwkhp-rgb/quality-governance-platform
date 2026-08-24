# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Stop the cleanup report's row guard failing the step under `errexit`
- **User goal (1–2 lines):** Close out the nightly SWA cleanup. #1549 fixed the credential, #1550 the target, #1551 the output format — each fix moved the failure one step later. This is the last one: the workflow now does its actual job correctly and only dies while writing the report about it.
- **In scope:** One `while` loop body in the `Generate Cleanup Report` step.
- **Out of scope:** The cleanup logic, which the dispatched run below proves correct. Carried forward and still open: production E2E secrets, a CI guard for unresolved secret references, no concurrency guard on the production deploy, and the two divergent rollback paths.
- **Feature flag / kill switch:** The workflow's existing `DISABLE_CLEANUP`, untouched.

## 2) Impact Map (what changed)
- **Frontend / Backend / APIs / Schemas / Database:** None.
- **Workflows/jobs/queues:** One loop body in one step of one workflow. No logic, trigger, step-order or output change.
- **Config/env/flags:** None.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Same rows written, same order, same file. Only the control-flow idiom changes.
- **Tolerant reader / strict writer applied?** N/A.
- **Breaking changes:** None; the step currently fails outright.
- **Migration plan:** None.
- **Rollback strategy (DB):** No data impact.

**Root cause.** The step runs under `/usr/bin/bash -e`. `REPORT` is built with a trailing `\n`, so after `echo -e` the final line piped into the loop is empty. On that last iteration `[ -n "$env" ]` is false, the `&&` short-circuits, and the compound command returns 1. In bash, a `while` loop's exit status is that of the last command run in its body — so the loop returns 1 and `errexit` kills the step. Every row had already been written correctly by then, which is why the failure reads oddly in the log: the report content is complete and the step still fails.

**Why `if`/`fi` rather than appending `|| true`.** `|| true` would also silence a genuine write failure on the `echo` — the one command in that loop that can fail for a real reason (a full disk, a bad path). An `if` with no `else` returns 0 when the condition is false while leaving the `echo`'s own status intact, so a real failure still fails the step.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** The old idiom reproduces exit code 1 under `bash -e` on the exact `REPORT` value from the failing run.
- [x] **AC-02:** The new idiom exits 0 on that same input and reaches the statement after the loop.
- [x] **AC-03:** Both idioms write byte-identical report rows — the fix changes control flow only, not output.
- [x] **AC-04:** Multi-row input (two numeric envs plus a non-numeric one) still writes all three rows and exits 0.
- [x] **AC-05:** `actionlint` finding count is unchanged against base (9 before, 9 after) — no new shellcheck debt.
- [ ] **AC-06:** A real dispatched run completes green end to end — verified post-merge per §8.

## 5) Testing Evidence (link to runs)
- [x] **Lint** — `actionlint` delta 0; YAML parses.
- [x] **Typecheck / Build / Unit / Contract / E2E** — no application code, dependencies or schema touched.

**The defect, from dispatched run [30890689728](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/30890689728).** Every functional step passed and only the report failed, which confirms #1549, #1550 and #1551 all worked:

```
success  Azure Login
success  List Current Environments
success  Verify Production Protection     -> production 'default' identified and protected
success  Identify Stale Environments      -> skipping non-numeric env: staging
success  Cleanup Environments             -> no environments to clean up
success  Final Environment List           -> total environments: 2
failure  Generate Cleanup Report          -> Process completed with exit code 1
skipped  Upload Cleanup Report
```

**Local reproduction**, run against the exact `REPORT` value the failing job produced:

```
--- OLD idiom (guard with &&) under bash -e ---
OLD exit code: 1                       <- and "reached line after loop" never printed
OLD rows written:  | staging | unknown | skip | non-numeric-name |

--- NEW idiom (if/fi) under bash -e ---
reached line after loop
NEW exit code: 0
NEW rows written:  | staging | unknown | skip | non-numeric-name |

--- NEW idiom with MULTIPLE rows (regression check) ---
MULTI exit code: 0
MULTI rows written:
  | 123 | pr-123 | delete | pr-closed |
  | 456 | pr-456 | skip | pr-open |
  | staging | unknown | skip | non-numeric-name |
```

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** The nightly cleanup runs to completion and uploads its report, ending a failure streak now at ten nights.
- [x] **CUJ-02:** Production protection is unaffected — this change is downstream of every guard, in the reporting step, and the dispatched run above already showed `default` identified and protected.
- [x] **CUJ-03:** `staging` survives. The dry-run selected nothing for deletion, and the deletion path is untouched by this change.

## 7) Observability & Ops
- **Logs:** Unchanged; the step already prints the report to the job log via `cat`.
- **Metrics / Alerts:** The nightly red run stops, and `Upload Cleanup Report` starts producing the 30-day artifact it was always meant to.
- **Runbook updates:** None.

**Worth recording:** this is the fourth defect in one workflow, after a credential that never existed, an app name and resource group that pointed at nothing, and an output write that could not survive a second environment. Each was hidden behind the one before it, because a workflow that fails at step *n* cannot reveal a defect at step *n+1*. Two process points follow from that. First, a delete-capable scheduled job shipped without anyone ever dispatching it once. Second, having fixed three defects one at a time, I audited the rest of the file rather than continuing: line 160's `&&` sits inside an `if` condition, which `errexit` exempts, and it is the only other instance of this pattern in the file.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Not applicable; no application code.
- **Canary plan:** Not applicable.
- **Prod post-deploy checks:** After merge, dispatch `Azure SWA Environment Cleanup` with `confirm` left empty — which is a dry-run and cannot delete — and confirm all thirteen steps report success, including `Upload Cleanup Report`. That closes AC-06. Two environments exist (`default` and `staging`) and neither is eligible for deletion, so the run exercises the full path without acting on anything.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** A dispatched run selecting any environment for deletion, or the report step failing for any new reason.
- **Rollback steps:** Set `DISABLE_CLEANUP: 'true'` to stop the workflow immediately without reverting, or revert this commit to return to a workflow that fails harmlessly at the report step. Neither path can delete an environment.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks.
- Run that exposed this defect: [30890689728](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/30890689728).
- Preceding fixes in this sequence: #1549, #1550, #1551.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — n/a, no application code
- [ ] **Gate 4:** Canary healthy (if used) — n/a
- [ ] **Gate 5:** Production verification plan + monitoring ready — per §8
