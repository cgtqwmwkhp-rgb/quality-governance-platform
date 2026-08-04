# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Write the multi-line environment lists to `$GITHUB_OUTPUT` using the delimiter form
- **User goal (1–2 lines):** Finish making the nightly SWA cleanup actually run. With the credential (#1549) and the target (#1550) fixed, it now reaches the listing step and fails there instead.
- **In scope:** The two `$GITHUB_OUTPUT` writes in the `List Current Environments` step.
- **Out of scope:** The cleanup logic, which is correct. Carried forward and still open: production E2E secrets, a CI guard for unresolved secret references, and the two divergent rollback paths.
- **Feature flag / kill switch:** The workflow's existing `DISABLE_CLEANUP`, untouched.

## 2) Impact Map (what changed)
- **Frontend / Backend / APIs / Schemas / Database:** None.
- **Workflows/jobs/queues:** Two output writes in one step of one workflow. No logic, trigger or step-order change.
- **Config/env/flags:** None.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** The `key<<DELIM` form preserves newlines, so both consuming steps see exactly the value shape they were written against. No consumer changes.
- **Tolerant reader / strict writer applied?** N/A.
- **Breaking changes:** None; the step currently fails outright.
- **Migration plan:** None.
- **Rollback strategy (DB):** No data impact.

**Why not simply collapse the newlines to spaces**, which is the more obvious fix: `Verify Production Protection` matches with `grep -q "^$PRODUCTION_ENV_NAME$"`, and a space-joined `default staging` cannot satisfy an anchored match. I ran that variant to be sure rather than reasoning about it, and it fails to find `default` and falls through to "proceeding with caution" — on the step whose entire job is to stop the production environment being deleted. The delimiter form avoids introducing that.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** Both writes produce a `$GITHUB_OUTPUT` file that parses without "Invalid format".
- [x] **AC-02:** Parsed values retain their newlines (`all_envs` = `default\nstaging`).
- [x] **AC-03:** `Verify Production Protection` finds `default` and reports it protected.
- [x] **AC-04:** `Identify Stale Environments` skips `staging` as non-numeric and selects nothing.
- [x] **AC-05:** A space-collapsed alternative demonstrably breaks AC-03 — establishing the delimiter form is required, not merely tidier.
- [ ] **AC-06:** A real dispatched run completes green — verified post-merge per §8.

## 5) Testing Evidence (link to runs)
- [x] **Lint** — shell block only; no expression syntax touched.
- [x] **Typecheck / Build / Unit / Contract / E2E** — no application code, dependencies or schema touched.

**The defect, from the dispatched run [30887935472](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/30887935472).** Note the listing itself succeeded, which confirms #1549 and #1550 both worked:

```
📋 Current Azure SWA environments:
default   ...  rg-qgp-staging  main  Ready
staging   ...  rg-qgp-staging  main  Ready
##[error]Unable to process file command 'output' successfully.
##[error]Invalid format 'staging'
```

**Verified end to end against live Azure** — real `az` calls, the new writes, the runner's own parsing rules, then both consumer steps run on the parsed result:

```
$GITHUB_OUTPUT written:        all_envs<<ENVS_EOF / default / staging / ENVS_EOF
parsed as runner parses:       all_envs = 'default\nstaging'
                               non_prod_envs = 'staging'
Verify Production Protection:  production 'default' identified and protected
Identify Stale Environments:   skip non-numeric: staging
would delete:                  (nothing)

control — space-collapsed:     protection FAILS to find production
```

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** The nightly cleanup completes its listing step instead of erroring, ending a failure streak now at nine nights.
- [x] **CUJ-02:** Production protection still works — verified on the parsed output, not just the raw command, because the parse is where the value shape could have changed.
- [x] **CUJ-03:** `staging` survives. Making a delete-capable workflow functional is the risk here, and both guards were exercised on real data.

## 7) Observability & Ops
- **Logs:** Unchanged; the step already prints its environment table.
- **Metrics / Alerts:** Assuming this is the last defect, the nightly red run stops.
- **Runbook updates:** None.

**Worth recording:** this is the third defect in one workflow — a credential that never existed, an app name and resource group that pointed at nothing, and an output write that could not survive a second environment. Each was hidden behind the one before it. The workflow has never functioned since it was added, and a nightly failure alarm ran for over a week without prompting a look. The concrete lesson for §7 of #1549 is that a scheduled job which has never once succeeded is not usefully distinguishable from one that does not exist.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Not applicable; no application code.
- **Canary plan:** Not applicable.
- **Prod post-deploy checks:** After merge, dispatch `Azure SWA Environment Cleanup` (its `confirm` input defaults to dry-run) and confirm it completes green, reports production protected, and deletes nothing.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** The dispatched run selecting any environment for deletion.
- **Rollback steps:** Set `DISABLE_CLEANUP: 'true'` to stop immediately without reverting, or revert this commit to return to a workflow that fails harmlessly at the listing step.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks.
- Run that exposed this defect: [30887935472](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/30887935472).
- Preceding fixes: #1549, #1550.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — n/a, no application code
- [ ] **Gate 4:** Canary healthy (if used) — n/a
- [ ] **Gate 5:** Production verification plan + monitoring ready — per §8
