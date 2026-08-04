# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Make the emergency rollback's image-existence gate actually reject missing tags
- **User goal (1–2 lines):** The `Verify target image exists` step in the emergency rollback workflow passes every input. An operator recovering from an incident can point production at an image that does not exist, turning the recovery path into a second outage.
- **In scope:** The one verification step in `rollback-production.yml`.
- **Out of scope:** Everything else in the rollback path — it restores only the container image, never app settings or the Celery worker/beat apps, and it cannot undo a migration. Those are separate and already logged.
- **Feature flag / kill switch:** None. Reverting restores today's behaviour, which is "no gate at all".

## 2) Impact Map (what changed)
- **Frontend / Backend / APIs / Schemas / Database:** None.
- **Workflows/jobs/queues:** One step body in `rollback-production.yml`. No trigger, job, ordering or permission change.
- **Config/env/flags:** The dispatch input is now passed to the shell through a step-level `env:` rather than interpolated into the script text.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** A valid rollback behaves exactly as before. Only invalid input changes outcome — from "silently deploys a nonexistent image" to "fails the step".
- **Breaking changes:** None for correct input. A rollback dispatched with a short SHA now fails fast instead of appearing to succeed. That is the point.
- **Migration plan / Rollback strategy (DB):** No data impact.

**Two defects in one step, and they compound.**

```bash
az acr repository show-tags ... --query "[?contains(@, '<sha>')]" -o tsv
if [ $? -ne 0 ]; then
  echo "ERROR: Image not found in ACR"
  exit 1
fi
```

1. **A `--query` that matches nothing still exits 0.** Testing `$?` therefore only ever caught `az` itself failing — a missing tag sailed straight through to the next step, which sets the production container image.
2. **`contains(@, ...)` is a substring test, and the deploy step interpolates the raw input.** A short SHA matches the full-length tag and "verifies", then the deploy uses the short form, which is not a tag in the registry. The gate confirms one image and ships another.

The second is the one that will actually bite. `ab87ecb6` is the short form the GitHub UI displays and the form that appears throughout our own deploy logs, so it is the natural thing to paste into a dispatch box during an incident.

The fix is exact equality plus a test on the *output* instead of the exit code, with `set -euo pipefail` so an `az` failure fails closed rather than leaving `MATCHED_TAG` empty and unexamined. Passing the input via `env:` also stops a dispatch input being interpolated into the script text.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** A full 40-character SHA present in the registry is accepted.
- [x] **AC-02:** A release tag such as `release-2597` is accepted.
- [x] **AC-03:** A SHA absent from the registry is rejected with a non-zero exit.
- [x] **AC-04:** A short SHA that is a prefix of a real tag is rejected, not silently accepted.
- [x] **AC-05:** Empty input is rejected.
- [x] **AC-06:** The step fails closed when `az` itself errors (bad registry, bad repository) rather than treating an empty result as success.
- [x] **AC-07:** No new lint debt.

## 5) Testing Evidence (link to runs)
- [x] **Lint** — `actionlint` 11 findings → 10. The one removed is `SC2181` on this exact step: *"Check exit code directly with e.g. 'if ! mycmd;', not indirectly with `$?`"*. Shellcheck had been reporting this defect all along. The remaining four differences are the same findings in a later step renumbered by the added lines; net by rule code is `SC2086 8, SC2129 2` before and after, with `SC2181 1 → 0`.
- [x] **Typecheck / Build / Unit / Contract / E2E** — no application code, dependencies or schema touched.

**The old and new checks, run side by side against the real production registry** (`acrqgpprodcdcd4691`, repository `quality-governance-platform`), where "truth" is an exact `grep -Fx` against the live tag list:

```
  real full SHA              ab87ecb6b95f3d…  old=ALLOWS  new=ALLOWS  truth=exists
  short SHA (typical paste)  ab87ecb6…        old=ALLOWS  new=BLOCKS  truth=DOES NOT EXIST
  nonexistent SHA            deadbeefdeadbe…  old=ALLOWS  new=BLOCKS  truth=DOES NOT EXIST
  real release tag           release-2597…    old=ALLOWS  new=ALLOWS  truth=exists
```

The old check allows all four. It has never rejected anything.

**AC-01 to AC-06, running the committed script itself.** The step body was extracted from the YAML with a parser (so the thing under test is the thing that ships, not a retyped copy) and executed against the live registry:

```
  real full SHA      want=ALLOW got=ALLOW rc=0  OK
  short SHA          want=BLOCK got=BLOCK rc=1  OK
  nonexistent        want=BLOCK got=BLOCK rc=1  OK
  real release tag   want=ALLOW got=ALLOW rc=0  OK
  empty input        want=BLOCK got=BLOCK rc=1  OK

  bad repository   rc=1  OK blocks
  bad registry     rc=1  OK blocks
```

**Not verified:** I did not dispatch the rollback workflow end to end, because doing so writes production. The step is pure verification and was exercised directly against the same registry and repository the workflow uses, but the first real dispatch is still the first time this runs inside Actions.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** A legitimate emergency rollback to a known-good full SHA proceeds unchanged.
- [x] **CUJ-02:** A rollback dispatched with a mistyped or shortened SHA now stops at verification instead of pointing production at a nonexistent image.
- [x] **CUJ-03:** A registry or auth failure during verification blocks the rollback rather than being read as "image absent" or "image present".

## 7) Observability & Ops
- **Logs:** The failure is now a GitHub `::error::` annotation naming the rejected tag and telling the operator to supply the full 40-character SHA or a release tag — visible at the top of the run rather than buried in step output. Success prints the matched tag, so the log records what was actually verified.
- **Metrics / Alerts:** None added.
- **Runbook updates:** None required; the error message carries the instruction.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Not applicable; the workflow is production-only and dispatch-only.
- **Canary plan:** Not applicable.
- **Prod post-deploy checks:** Nothing deploys as a result of this merge. The change is exercised the next time a rollback is dispatched.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** The step rejecting a tag that genuinely exists.
- **Rollback steps:** Revert the commit. Note the pre-change behaviour is an inert gate, so reverting removes protection rather than restoring any capability. The break-glass path does not depend on this workflow: `az webapp config container set --resource-group rg-qgp-staging --name <app> --container-image-name <acr>.azurecr.io/quality-governance-platform:<sha>`.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks.
- Registry probed: `acrqgpprodcdcd4691` / `quality-governance-platform`.
- Found during review of the production concurrency work in #1553; deliberately not bundled into it.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — n/a, production-only dispatch workflow
- [ ] **Gate 4:** Canary healthy (if used) — n/a
- [ ] **Gate 5:** Production verification plan + monitoring ready — per §8; nothing deploys on merge
