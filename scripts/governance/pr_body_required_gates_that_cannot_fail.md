# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Make two aggregate CI gates capable of failing
- **User goal (1–2 lines):** A required status check on `main` called `Dependency Vulnerability Check` could not fail under any circumstance, and `All Checks Passed` would report success if CI failed. Both are gates in name only.
- **In scope:** The `dependency-check` job in `security-scan.yml` and the `all-checks` job in `ci.yml`.
- **Out of scope:** Adding `All Checks Passed` to the required contexts. That is the point of hardening it, but it must not be done until a real run is observed reporting **failure** rather than **skipped** — see §8.
- **Feature flag / kill switch:** None. Reverting restores the previous non-blocking behaviour.

## 2) Impact Map (what changed)
- **Frontend / Backend / APIs / Schemas / Database:** None.
- **Workflows/jobs/queues:** Two job definitions. No job renamed, no trigger changed.
- **Config/env/flags:** None. Branch protection is **not** modified by this PR.
- **Dependencies:** `security-scan.yml`'s `dependency-check` job no longer installs `safety`/`bandit` or Python; it sets up Node instead.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Both jobs keep their exact `name:`. That matters: `Dependency Vulnerability Check` is a required status check, and renaming it would detach the branch protection rule so every PR would block forever waiting on a context that never reports.
- **Breaking changes:** Both jobs can now fail. That is the intent. Verified below that neither fails on the current tree.
- **Migration plan / Rollback strategy (DB):** No data impact.

**Defect 1 — a required gate that could not fail.** The whole substance of `Dependency Vulnerability Check` was:

```bash
pip install -r requirements.lock
safety check --json > safety-report.json || true
cat safety-report.json
```

`|| true` swallows the verdict, and `cat` always succeeds, so the job returned success regardless of what was found. It has been a required check on `main` reporting green unconditionally.

I did **not** simply delete the `|| true`, for two reasons. `safety check` prints `DEPRECATED: this command (check) has been DEPRECATED, and will be unsupported beyond 01 June 2024` on every run, and making a deprecated command blocking across 20 required contexts invites a future outage when it is withdrawn. More importantly the repository has already decided `safety` is advisory: the required `Security Scan` job in `ci.yml` runs `safety check --full-report || echo "…(non-blocking)"` deliberately, right beside the gate that does the real work.

Python is genuinely covered. `Security Scan` runs `pip-audit --strict` against `requirements.lock` with a dated waiver file (`scripts/validate_security_waivers.py`), and a hard `bandit -r src/ -ll`. Removing the duplicate deprecated `safety check` therefore loses nothing.

**npm was the actual hole.** The only `npm audit` in the repository is a step inside `Frontend Tests`, which is **not** a required check. So nothing blocking examined frontend dependencies at all. This job now does, which makes its name true for the first time.

**Defect 2 — a gate that goes green when CI fails.** `all-checks` aggregates 39 jobs but was declared `if: github.event_name != 'schedule'`. Without `always()`, a failure anywhere in `needs` **skips** this job, and GitHub reports a skipped required check as successful. It was not yet required, so nothing was relying on it — but it is the natural candidate to require, and requiring it in that state would have created a gate that passes precisely when it should fail. It now runs unconditionally and computes an explicit verdict from `needs.*.result`.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** `Dependency Vulnerability Check` keeps its exact required-context name.
- [x] **AC-02:** It fails when a high or critical vulnerability exists in production frontend dependencies.
- [x] **AC-03:** It passes on the current tree, so this PR does not block the repository.
- [x] **AC-04:** It runs no package install scripts (`--package-lock-only`), so the gate cannot itself be exploited by a malicious dependency.
- [x] **AC-05:** `all-checks` runs even when an upstream job fails, and fails with it.
- [x] **AC-06:** `all-checks` still passes when jobs are legitimately skipped.
- [x] **AC-07:** No new lint debt.

## 5) Testing Evidence (link to runs)
- [x] **Lint** — `actionlint` delta **0** on both files (`security-scan` 0→0, `ci` 0→0). One finding was introduced and fixed en route: `join(needs.*.result, " ")` used double quotes, which Actions expressions do not accept. It is now passed via `env:` rather than interpolated into the script.
- [x] **Typecheck / Build / Unit / Contract / E2E** — no application code, dependencies or schema touched.

**AC-02 / AC-03 — the npm gate, measured against the committed lockfile.** Current state is 8 findings across all scopes (2 high, 6 moderate), but only 2 moderate in production scope. So:

```
  --omit=dev --audit-level=high      exit=0   <- the blocking command: passes today
  --omit=dev --audit-level=moderate  exit=1   <- proves the command can fail
  all scopes --audit-level=high      exit=1   <- proves it can fail
```

The second and third lines matter as much as the first. A gate that passes is only meaningful once you have shown it is capable of failing — which is exactly the property the old job lacked.

**AC-05 / AC-06 — the verdict logic, extracted from the YAML and unit-tested.** The step body was parsed out of `ci.yml` (so the thing tested is the thing that ships) and run against every combination that matters:

```
  success success success    rc=0  all succeeded          OK
  success skipped success    rc=0  skips are legitimate   OK
  skipped skipped            rc=0  all skipped            OK
  success failure success    rc=1  a failure              OK
  success cancelled          rc=1  a cancellation         OK
  success failure cancelled  rc=1  mixed bad              OK
```

`skipped` is treated as acceptable deliberately — many jobs in this matrix skip by design, and failing on skips would make the gate permanently red. Anything that is not `success` or `skipped` fails, so unexpected states fail closed.

**Not verified:** that `All Checks Passed` reports **failure** rather than **skipped** in a real GitHub run with a genuinely failing upstream job. The local unit test covers the script's logic, not GitHub's job-scheduling behaviour. This is the reason §1 puts the branch-protection change out of scope — see §8.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** A PR introducing a high-severity production frontend dependency is now blocked by a required check. Previously nothing blocking inspected npm dependencies.
- [x] **CUJ-02:** A PR whose CI fails can no longer be reported as fully green by the aggregate gate.
- [x] **CUJ-03:** A normal PR with legitimately skipped jobs is unaffected and still merges.

## 7) Observability & Ops
- **Logs:** The advisory step prints a severity-sorted table of every npm finding with the fix version, so dev-scope issues are visible rather than hidden behind `--omit=dev`. `npm-audit-report.json` is uploaded as an artifact, replacing `safety-report.json`.
- **Metrics / Alerts:** None added.
- **Runbook updates:** None.

**Known findings this deliberately does not block, recorded rather than buried.** Two high-severity issues exist in *development* scope — `basic-ftp` and `brace-expansion`, both denial-of-service, both with fixes available. They do not ship, but they do execute on CI runners, so blocking on them is the right end state. That is a follow-up rather than part of this PR, because making it blocking today would fail the gate immediately and block the repository. The advisory step exists so these stay visible in the meantime.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Not applicable; CI configuration only.
- **Canary plan:** Not applicable.
- **Prod post-deploy checks:** None; nothing about the deployed artefact changes.

**Required follow-up, in order.** After this merges, deliberately fail a job on a throwaway PR and confirm `All Checks Passed` reports **failure**, not **skipped**. Only then add it as a required context:

```bash
gh api --method POST \
  repos/cgtqwmwkhp-rgb/quality-governance-platform/branches/main/protection/required_status_checks/contexts \
  -f 'contexts[]=All Checks Passed'
```

Doing that before the observation would risk pinning a gate that silently passes.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Either gate failing in a way not attributable to a real defect — for example a transient npm registry error making the audit unavailable.
- **Rollback steps:** Revert the commit. Both jobs return to their previous non-blocking form immediately; no state to unwind and no branch-protection change to undo, since this PR makes none.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks.
- npm audit measured against `frontend/package-lock.json` at `601fac94`.
- Verdict logic test: step body extracted from `ci.yml` via a YAML parser and executed against six result vectors.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — n/a, CI configuration only
- [ ] **Gate 4:** Canary healthy (if used) — n/a
- [ ] **Gate 5:** Production verification plan + monitoring ready — n/a; follow-up in §8
