# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Make Dependabot auto-merge actually work, with grouping and generated ledgers
- **User goal (1–2 lines):** 27 Dependabot PRs are open and none can merge unattended. The auto-merge workflow has never worked — not "is broken", but has never been capable of working, for three independent reasons.
- **In scope:** `dependabot-auto-merge.yml`, `change-ledger-enforcement.yml`, `.github/dependabot.yml`.
- **Out of scope:** The pip lockfile deadlock (§7) — pip PRs cannot pass a required check *and* are currently no-ops, so they need a separate fix before auto-merge means anything for them. Also out of scope: the two known dev-scope npm highs, and enabling `allow_auto_merge`, which is a repository setting applied at merge time (§8).
- **Feature flag / kill switch:** `allow_auto_merge` at the repository level. Turning it off disables auto-merge instantly without touching any file.

## 2) Impact Map (what changed)
- **Frontend / Backend / APIs / Schemas / Database:** None.
- **Workflows/jobs/queues:** The approve step is deleted from `dependabot-auto-merge.yml` and `github_actions` is excluded. `change-ledger-enforcement.yml` gains ledger generation for Dependabot and now reads the PR body from the API. `dependabot.yml` gains groups, cooldown and an off-peak schedule.
- **Config/env/flags:** `change-ledger-enforcement.yml` gains an explicit `permissions:` block (`contents: read`, `pull-requests: write`) so it can write the generated ledger.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Human PRs are unaffected — verified below that the gate still blocks a human PR with no ledger and still passes one with a real ledger.
- **Breaking changes:** None. Grouping causes Dependabot to close and recreate its PRs as groups on the next scheduled run; that is the intent.
- **Migration plan / Rollback strategy (DB):** No data impact.

**Three independent blockers, all confirmed, any one of which is fatal.**

1. The approve step failed on every PR with `GitHub Actions is not permitted to approve pull requests`, because `can_approve_pull_request_reviews` is `false`. With no `continue-on-error` the job died there, so `Enable auto-merge` never ran.
2. `allow_auto_merge` is `false` at the repository level, so `gh pr merge --auto` would have failed even if it had been reached.
3. The Change Ledger gate is red on every Dependabot PR.

**I deleted the approve step rather than granting the permission.** Branch protection on `main` requires no reviews, so an approval buys nothing — while `can_approve_pull_request_reviews: true` would let any workflow satisfy a review requirement, including one added later by someone who assumes reviews mean human eyes. The setting stays off.

**`github_actions` is excluded from auto-merge.** This is the one place I deliberately kept friction. A compromised action executes inside CI holding this repository's credentials and can rewrite the very workflows meant to catch it; nothing in the required checks inspects what an action *does*, since `actionlint` checks syntax. A library at least has to survive the test suite, CodeQL and `pip-audit`. That is five PRs a week for a human to look at.

**Grouping is load-bearing, not cosmetic.** Branch protection sets `strict: true`, and GitHub does not update PR branches for you — 17 of the 27 open PRs currently report `BEHIND`. Ungrouped, every merge invalidates the rest and the queue drains at roughly one PR per Dependabot rebase cycle while burning a full CI matrix each time. Grouping collapses it into a handful of PRs. `cooldown` applies to version updates only and never to security updates, so routine churn waits a week while a security patch still arrives immediately.

**On the ledger: generated, not waived.** Exempting Dependabot in the `if:` was the easy option and throws away the audit trail. Instead the gate synthesises a ledger from Dependabot metadata and stamps it into the PR body. It is honest about what it is — the heading says `(generated)` and the body says **no human has attested to this ledger**. Generation and validation had to live in the same job: a body edit written with `GITHUB_TOKEN` does not start a new workflow run, so a separate workflow would leave the check red on a stale result forever.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** The generated ledger satisfies the validator's own rules.
- [x] **AC-02:** Generation is idempotent — re-running does not stamp a second ledger.
- [x] **AC-03:** A human PR with no ledger is still blocked.
- [x] **AC-04:** A human PR with a real ledger still passes.
- [x] **AC-05:** `github_actions` updates are excluded from auto-merge.
- [x] **AC-06:** No approval step remains, and `can_approve_pull_request_reviews` stays `false`.
- [x] **AC-07:** The CI security covenant still passes — no `pull_request_target`, no unsafe secret use.
- [x] **AC-08:** No new lint debt.

## 5) Testing Evidence (link to runs)
- [x] **Lint** — `actionlint` delta **0** on both workflows. All three files parse as YAML. `scripts/validate_ci_security_covenant.py` exits 0.
- [x] **Typecheck / Build / Unit / Contract / E2E** — no application code, dependencies or schema touched.

**AC-01 to AC-04 — the generator and validator were extracted from the YAML with a parser and executed against each other under a stubbed Actions environment**, so what was tested is what ships rather than a retyped copy:

```
  extracted generator 67 lines
  extracted validator 59 lines
    [info] Generated Change Ledger written to PR body.
  generated body length: 1905
  --- running the real validator against it ---
    [info] Change Ledger checks passed.
  RESULT: validator PASSED

  idempotent (no duplicate stamp): YES
  marker count in body: 1
  human PR with no ledger -> BLOCKED (correct)
    reason: Missing required PR sections: change ledger, summary, impact map, ...
  human PR with real ledger -> PASSED (correct)
```

The third case matters most. The risk of generating ledgers is that the gate quietly stops applying to humans; it does not. The fourth case used this repository's own ledger file from #1555 as the input.

**Not verified:** that Dependabot's `GITHUB_TOKEN` can write the PR body in practice, and that `gh pr merge --auto` succeeds once `allow_auto_merge` is on. Runner logs from PRs #1364 and #1357 show Dependabot `pull_request` events granting `Contents: write` / `PullRequests: write` when a `permissions:` block is declared, which is why I expect both to work — but expecting is not observing. §8 makes the first real Dependabot PR the checkpoint.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** A human PR still cannot merge without writing a real Change Ledger.
- [x] **CUJ-02:** A Dependabot patch/minor library PR gets a generated ledger and, once all required checks pass, merges without a human.
- [x] **CUJ-03:** A Dependabot `github-actions` PR gets a ledger but is **not** auto-merged, so a human still reviews it.
- [x] **CUJ-04:** A major-version bump falls outside every group and outside the auto-merge condition, so it arrives as an individual PR for review — which is the behaviour wanted for the outstanding `react-router` 6→7 work.

## 7) Observability & Ops
- **Logs:** The ledger step logs whether it generated or skipped. The auto-merge job is visible per PR as before.
- **Metrics / Alerts:** None added.
- **Runbook updates:** To stop all auto-merging immediately, set `allow_auto_merge=false` on the repository; no code change or revert needed.

**Adjacent finding this does not fix — pip Dependabot PRs are worse than blocked, they are pointless.** They fail the required `Unit Tests` check every time, because Dependabot edits `requirements.txt` while `requirements.lock` is generated by `pip-compile` and nothing regenerates it on the PR branch. `lockfile-update.yml` only runs after a push to `main`, which cannot happen while the PR is blocked. And the `Dockerfile` installs `requirements.lock` in preference to `requirements.txt`, as does the `pip-audit` gate — so a pip PR today changes neither what ships nor what the scanner sees. Auto-merge will not help them until the lock is regenerated on the branch, which needs a token Dependabot events cannot supply. Tracked separately.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Not applicable; CI configuration only.
- **Canary plan:** Not applicable.
- **Prod post-deploy checks:** None; nothing about the deployed artefact changes.

**Required step at merge time**, without which nothing changes:

```bash
gh api --method PATCH repos/cgtqwmwkhp-rgb/quality-governance-platform \
  -F allow_auto_merge=true -F delete_branch_on_merge=true
```

`delete_branch_on_merge` is currently `false`; with weekly grouped bumps the branches would otherwise accumulate indefinitely.

**Then watch the first Dependabot PR end to end** and confirm three things before trusting the mechanism: the ledger check goes green on a generated ledger, the auto-merge job succeeds rather than erroring, and a `github-actions` PR is *not* auto-merged.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Anything auto-merging that should not have, the ledger gate failing on human PRs, or Dependabot PRs merging while red.
- **Rollback steps:** Immediate stop is `gh api --method PATCH repos/... -F allow_auto_merge=false`, which halts auto-merge without a code change. Then revert this commit to restore the previous workflows. Grouping reverts with it; Dependabot re-opens individual PRs on its next run.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks.
- Generator/validator harness: both scripts extracted from `change-ledger-enforcement.yml` via a YAML parser and run under a stubbed Actions environment.
- Blocker evidence: repository settings via the API, and the failing auto-merge run on #1547.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — n/a, CI configuration only
- [ ] **Gate 4:** Canary healthy (if used) — n/a
- [ ] **Gate 5:** Production verification plan + monitoring ready — per §8, first Dependabot PR is the checkpoint
