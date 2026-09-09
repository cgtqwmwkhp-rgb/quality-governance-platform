# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Merge Dependabot PRs with a credential that actually triggers the deploy pipeline
- **User goal (1–2 lines):** Auto-merge enabled with `GITHUB_TOKEN` merges the PR but does not fire a `push` event, so the change lands on `main` and is never built or deployed. This repoints the merge at an App/PAT credential and refuses to run without one.
- **In scope:** `.github/workflows/dependabot-auto-merge.yml`.
- **Out of scope:** The pip lockfile deadlock, which needs the same credential but is a separate change. A drift detector (§7).
- **Feature flag / kill switch:** `allow_auto_merge` at the repository level, currently **false**. Nothing auto-merges until it is turned back on.

**DRAFT — do not merge until `DEPENDABOT_AUTOMERGE_TOKEN` exists as a Dependabot secret.** Merging first is harmless (auto-merge is off) but pointless, and the job would fail by design on every Dependabot PR.

## 2) Impact Map (what changed)
- **Frontend / Backend / APIs / Schemas / Database:** None.
- **Workflows/jobs/queues:** One workflow. A new guard step is added, and the merge step's `GH_TOKEN` changes from `secrets.GITHUB_TOKEN` to `secrets.DEPENDABOT_AUTOMERGE_TOKEN`.
- **Config/env/flags:** Requires a new **Dependabot** secret, `DEPENDABOT_AUTOMERGE_TOKEN`.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** `dependabot/fetch-metadata` keeps using `GITHUB_TOKEN`; reading metadata does not need the elevated identity, and narrowing the blast radius of the new credential is worth the asymmetry.
- **Breaking changes:** The job now fails on every Dependabot PR until the secret exists. That is deliberate — see below.
- **Migration plan / Rollback strategy (DB):** No data impact.

**What went wrong, precisely.** On 2026-08-04 auto-merge was enabled and worked: #1559 (15 grouped npm updates) merged itself with all 46 checks green. But no CI run was ever created for the merge commit `78a2efe7`. CI triggers on `push` to `main`, and `deploy-staging` chains off CI via `workflow_run`, so nothing downstream fired. `main` sat at `78a2efe7` while production stayed on `2e4a84eb` — no failure, no red check, no notification. The drift was found by watching the deploy, not by any alarm, and production had to be re-converged by dispatching staging by hand.

The cause is that events authored by `GITHUB_TOKEN` do not trigger workflow runs. Auto-merge enabled with `GITHUB_TOKEN` inherits that. An App or PAT-authored merge does fire `push`.

**Why the guard fails closed rather than falling back.** The obvious defensive move — fall back to `GITHUB_TOKEN` when the new secret is missing — is exactly wrong here, because the failure mode is silent. A fallback would merge successfully, report success, and quietly stop deploying. Failing the job is loud, and loud is recoverable.

**Why it must be a Dependabot secret.** Workflow runs triggered by Dependabot read secrets from a separate store. An Actions secret of the same name arrives empty, which would trip the guard — noisily, at least, rather than silently.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** The merge step uses `DEPENDABOT_AUTOMERGE_TOKEN`, not `GITHUB_TOKEN`.
- [x] **AC-02:** The job fails with an actionable message when the secret is absent.
- [x] **AC-03:** The guard does not crash under `set -u` when the variable is unset entirely.
- [x] **AC-04:** The `github_actions` exclusion is preserved.
- [x] **AC-05:** No approval step is reintroduced, and `can_approve_pull_request_reviews` stays `false`.
- [x] **AC-06:** No new lint debt.
- [ ] **AC-07:** A real auto-merged PR produces a `push`-event CI run and reaches production. **Cannot be verified until the secret exists — see §8.**

## 5) Testing Evidence (link to runs)
- [x] **Lint** — `actionlint` delta **0**; YAML parses.
- [x] **Typecheck / Build / Unit / Contract / E2E** — no application code, dependencies or schema touched.

**AC-02 / AC-03 — the guard was extracted from the YAML with a parser and executed**, so the thing tested is the thing that ships:

```
  token absent  -> exit=1   (fails loudly)
  token present -> exit=0
  var unset     -> exit=1   (no crash under set -u)
```

**AC-01 / AC-04 / AC-05 — confirmed by inspection of the file:** `GH_TOKEN` on the merge step resolves to `DEPENDABOT_AUTOMERGE_TOKEN`; `GITHUB_TOKEN` survives only on `fetch-metadata`; the `package-ecosystem != 'github_actions'` condition is intact; there is no `gh pr review --approve` step.

**Not verified, and this is the important line.** I have not observed an App/PAT-enabled auto-merge firing a `push` event in this repository. That an App or PAT-authored merge triggers workflows while `GITHUB_TOKEN` does not is documented behaviour, and it is the whole premise of this change — but the last thing assumed from documentation on this exact topic turned out to be the defect above. §8 therefore treats the first PR as an experiment with a named observable, not as a rollout.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** With no secret configured, no Dependabot PR can auto-merge silently — the job fails first.
- [x] **CUJ-02:** A `github-actions` bump is still excluded from auto-merge and left for a human.
- [ ] **CUJ-03:** A patch/minor library PR auto-merges *and* reaches production. Pending §8.

## 7) Observability & Ops
- **Logs:** The guard states plainly which secret is missing and where to add it.
- **Metrics / Alerts:** None added.
- **Runbook updates:** To stop all auto-merging, set `allow_auto_merge=false`; no code change needed.

**Adjacent gap, deliberately not fixed here.** Nothing in this repository detects `main` having moved ahead of production. That is what made today's incident silent, and it is a broader hole than auto-merge — any lost trigger, cancelled run or failed chain produces the same invisible drift. A scheduled job comparing `main` HEAD against the deployed image tag would catch the whole class. Recommended as a follow-up rather than bundled in, since it is a different concern from this credential change.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Not applicable; CI configuration only.
- **Canary plan / Prod post-deploy checks:** Not applicable.

**Order of operations. Do not skip step 3.**

1. Create the credential — a GitHub App (repository permissions **Contents: Read and write**, **Pull requests: Read and write**, installed on this repository only) or a fine-grained PAT with the same two permissions scoped to this repository.
2. Store it at Settings → Secrets and variables → **Dependabot** → `DEPENDABOT_AUTOMERGE_TOKEN`. **Not** under Actions.
3. Merge this PR, then re-enable auto-merge on **one** PR only and confirm the named observable: a **`push`-event CI run appears for the merge commit**, and the chain carries through to production. Checking that the PR merged is not sufficient — it merged last time too.
4. Only after that, set `allow_auto_merge=true` for the queue:
   ```bash
   gh api --method PATCH repos/cgtqwmwkhp-rgb/quality-governance-platform -F allow_auto_merge=true
   ```

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** A merge commit appearing on `main` with no corresponding `push`-event CI run, or any divergence between `main` and the deployed image.
- **Rollback steps:** `gh api --method PATCH repos/... -F allow_auto_merge=false` stops it immediately without a code change. If `main` has already drifted, re-converge with `gh workflow run deploy-staging.yml --ref main`, which re-enters the chain and carries through to production — this is the procedure used to recover `78a2efe7`.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- Incident: merge commit `78a2efe7` with zero `push`-event workflow runs; production held at `2e4a84eb` until manually re-converged.
- Guard test: step body extracted from the workflow via a YAML parser and executed against three input states.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — n/a, CI configuration only
- [ ] **Gate 4:** Canary healthy (if used) — n/a
- [ ] **Gate 5:** Production verification plan + monitoring ready — the §8 step 3 observation
