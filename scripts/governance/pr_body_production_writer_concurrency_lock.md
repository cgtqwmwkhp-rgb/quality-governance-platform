# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Serialise every workflow that writes production behind one concurrency group
- **User goal (1–2 lines):** Two production deploys can currently run at once and race the step that captures the rollback target. Today I avoided that by sequencing merges by hand, which is not a control.
- **In scope:** A top-level `concurrency` stanza on the three workflows that can set the container image on `app-qgp-prod`, plus a CI assertion that they stay in agreement.
- **Out of scope:** The absence of deployment slots (already logged as IT handover item 1), which is the change that would retire this problem class entirely. Also out of scope and listed in §7: a broken image-existence gate in the rollback workflow.
- **Feature flag / kill switch:** None. Reverting the commit restores today's behaviour exactly.

## 2) Impact Map (what changed)
- **Frontend / Backend / APIs / Schemas / Database:** None.
- **Workflows/jobs/queues:** One `concurrency` block added to `deploy-production.yml` and `provision-production.yml`; the existing block in `rollback-production.yml` changes `cancel-in-progress` from `false` to `true`. No job, step, trigger or ordering change.
- **Config/env/flags:** None.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Purely additive scheduling. A single production deploy behaves identically; only overlap is affected.
- **Breaking changes:** None.
- **Migration plan / Rollback strategy (DB):** No data impact.

**The race.** `Capture previous production image` (`id: capture_previous_image`) reads the live image from Azure immediately before `Deploy to Azure Web App` overwrites it, and exports it as `previous_image` for `auto-rollback`. The workflow notes there are no deployment slots on this tier, so that captured value is the **only** automatic recovery target. Two overlapping runs both capture the same predecessor, so the second run's rollback target is already one deploy stale before it is ever used.

**Three writers, not one.** `deploy-production.yml` is the obvious one. `rollback-production.yml` sets the container image too, and already declared `group: deploy-production` — but because the deploy workflow never joined that group, it has only ever serialised rollbacks against each other. `provision-production.yml` is the third: its `Create Web App` step re-points an existing production Web App at `quality-governance-platform:latest`, because the `if` guarding it only skips the `az webapp create`, not the container set. All three now share `deploy-production`.

**Why `cancel-in-progress` is deliberately asymmetric.** The deploy and provision workflows keep `false`; the emergency rollback moves to `true`. This is not about shaving minutes off an incident. GitHub keeps at most one *pending* run per group and cancels it when the next one arrives. With `false` on the rollback, an operator dispatching a rollback during a bad deploy puts it in `pending` — and the next merge to `main` produces a staging success, which fires the `workflow_run` trigger, which queues a production deploy, **which cancels the pending rollback**. It shows as "cancelled" in a list the operator is not watching. That is the same silent-loss failure this PR exists to close, aimed at the recovery path. Preemption removes it: the rollback takes the group immediately and becomes the last writer.

**What preemption costs.** Cancelling a deploy mid-flight is safe for the image write — production is pinned by digest, and `Capture expected image digest` already fails closed on a partial push. It is *not* safe for schema state: `Run database migrations` creates an Azure Container Instance running `alembic upgrade head` and only polls it, so cancelling the run kills the poller, not the migration. That caveat is written into the workflow comment so the operator checks the alembic revision. Note this hazard is not created by preemption — queueing lets the deploy finish its migration anyway.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** All three production writers declare a top-level concurrency group resolving to `deploy-production`.
- [x] **AC-02:** `cancel-in-progress` is `true` on the emergency rollback only, and `false` on the other two.
- [x] **AC-03:** Cross-workflow preemption actually works — demonstrated live, not inferred from documentation.
- [x] **AC-04:** The documentation-only `rollback: true` dispatch resolves to a separate group so it never occupies the production lock.
- [x] **AC-05:** The group expression resolves correctly on an event carrying no `inputs` payload, and does not error.
- [x] **AC-06:** CI fails if any of the three files drifts out of agreement, including a rename to a *superstring* of the group name.
- [x] **AC-07:** No new lint debt: `actionlint` delta 0 on all three workflows; `flake8` count unchanged against base.

## 5) Testing Evidence (link to runs)
- [x] **Lint** — `actionlint` findings unchanged on each workflow (7/11/69 before and after). `flake8` on the validator back to the base count of 2 after removing an f-string I had added without placeholders. `black` at the repo's line-length 120 leaves my additions untouched. Note CI gates `src/` and `tests/` only, so `scripts/` violations here are pre-existing and deliberately not swept up.
- [x] **Typecheck / Build / Unit / Contract / E2E** — no application code, dependencies or schema touched.

**AC-03: cross-workflow preemption, observed.** Two throwaway workflows sharing group `zz-probe-lock`: a holder with `cancel-in-progress: false` sleeping 180s, and a preemptor with `cancel-in-progress: true`. The holder was confirmed `in_progress`, then the preemptor was dispatched:

```
holder 30896836709 status before: in_progress/
dispatching preemptor (cancel-in-progress: true, same group)...
10:36:46 holder=completed/cancelled  preemptor=queued/
10:37:02 holder=completed/cancelled  preemptor=completed/success
```

The holder was cancelled and never printed its completion line. This establishes that `cancel-in-progress` is a property of the *arriving* run and acts across workflow boundaries — the assumption the asymmetry rests on. Both probes were removed before this PR.

**AC-05: the group expression under an event with no `inputs`.** A probe carrying the identical expression, exercised on all three shapes:

```
event_name = push               -> RESOLVED_GROUP = deploy-production-deploy
event_name = workflow_dispatch  (rollback=true)  -> deploy-production-rollback
event_name = workflow_dispatch  (rollback=false) -> deploy-production-deploy
```

A missing property evaluates to null rather than erroring, so `workflow_run` and `release` events resolve to the shared group. This mattered enough to test: a malformed expression here would block every production deploy.

**AC-06: the CI assertion, negative-tested against each drift mode.**

```
BASELINE                                 exit=0
provision group renamed to a superstring exit=1  CAUGHT
rollback group renamed                   exit=1  CAUGHT
rollback preemption disabled             exit=1  CAUGHT
deploy fallback branch renamed           exit=1  CAUGHT
deploy allowed to preempt                exit=1  CAUGHT
restored baseline                        exit=0
```

The first case is the reason the check does not use a substring test. My initial implementation did, and it **passed** a rename to `deploy-production-provision` — a different group that happens to contain the right name. That is exactly the silent drift the assertion exists to catch, so plain groups are now compared exactly and expression groups must offer the bare group as a quoted branch.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** A single production deploy is unaffected — one run takes the group uncontended and proceeds exactly as before.
- [x] **CUJ-02:** An emergency rollback during an in-flight deploy now preempts it and becomes the last writer, rather than queueing where it could be silently cancelled. Verified by the probe pair above.
- [x] **CUJ-03:** The documentation-only rollback dispatch still runs immediately during a deploy, because it sits in its own group and mutates nothing.

## 7) Observability & Ops
- **Logs:** Unchanged. A blocked run shows as `Queued`/`Pending` in the Actions UI with no job started.
- **Metrics / Alerts:** None added.
- **Runbook updates:** The workflow header now names all three group holders and the `gh run list` / `gh run cancel` commands to find and clear one, because the group name is not surfaced in the API. The break-glass path bypasses Actions entirely.

**Worth recording — the reviewer caught a live defect adjacent to this work, which I have deliberately not fixed here.** In `rollback-production.yml`, the `Verify target image exists` step runs `az acr repository show-tags --query "[?contains(@, '<sha>')]"` and then tests `$?`. That command exits **0 with empty output** when the tag is absent, so the check never fires. A mistyped `image_sha` passes verification and the next step points production at a nonexistent image — a production outage caused by the emergency recovery path. It needs an emptiness test on the output, not an exit-code test. Raised separately rather than bundled into a concurrency change.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Not applicable; no application code.
- **Canary plan:** Not applicable.
- **Prod post-deploy checks:** The first production deploy after merge exercises the stanza. Confirm it acquires the group and runs normally — the expected outcome is that nothing looks different, because there is nothing to contend with. The CI assertion runs on this PR and every subsequent one.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Production deploys sitting in `Queued` with no holder identifiable, or the emergency rollback failing to start.
- **Rollback steps:** Revert this commit; the workflows return to unguarded concurrency immediately with no residual state, since a concurrency group is not a persistent lock. To clear a stuck holder without reverting: `gh run list --workflow="Deploy to Azure Production"` (and the rollback and provision workflows) to find it, then `gh run cancel <id>`.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks.
- Preemption probe: holder run 30896836709 (cancelled), preemptor run 30897060967 (success).
- Expression probe: run 30895003479 and the two dispatches following it.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — n/a, no application code
- [ ] **Gate 4:** Canary healthy (if used) — n/a
- [ ] **Gate 5:** Production verification plan + monitoring ready — per §8
