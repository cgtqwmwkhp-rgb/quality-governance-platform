# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Identify the server for `backup list` across the `azure-cli` 2.86 argument break
- **User goal (1–2 lines):** Make the recovery point check merged in #1544 actually verify something. On its first real production run it warned instead, because the runner's `azure-cli` rejected the argument it used.
- **In scope:** The `backup list` invocation inside the `Verify database recovery point` step of `deploy-production.yml`.
- **Out of scope:** The geo-redundancy and retention posture decisions from #1544 §7, which remain open. Also out of scope: adding a `concurrency` guard to the production workflow, noted in §7.
- **Feature flag / kill switch:** None. `MAX_BACKUP_AGE_HOURS` remains the tunable.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None.
- **Backend (handlers/services):** None.
- **APIs (endpoints changed/added):** None.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None.
- **Database (migrations/entities/indexes):** None.
- **Workflows/jobs/queues:** One `az` invocation in `build-and-deploy` of `.github/workflows/deploy-production.yml`. No job graph change.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** This *is* the compatibility fix. `azure-cli` 2.86 repurposed `--name` on `flexible-server backup list` to mean the backup name and introduced `--server-name` for the server. Rather than pin to whichever spelling the runner image currently ships, the step tries `--server-name` and falls back to `--name`, so it works either side of the break and will keep working when the runner image moves again.
- **Tolerant reader / strict writer applied?** Yes in spirit: the retry is narrowed to unknown-argument rejections only. A permission or network failure is reported as itself rather than retried into a more confusing error from the other spelling.
- **Breaking changes:** None. `show` is untouched — `--name` still means the server there, and that call succeeded in the failing run.
- **Migration plan:** None.
- **Rollback strategy (DB):** No DB impact.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** On `azure-cli` 2.86+, the step lists backups via `--server-name` on the first attempt and completes verification.
- [x] **AC-02:** On `azure-cli` 2.85, the step falls back to `--name` and completes verification.
- [x] **AC-03:** A genuine authorization failure is **not** retried; the real `az` error is shown once and the step warns without blocking.
- [x] **AC-04:** The blocking behaviour from #1544 is intact — a backup older than the threshold still fails the deploy.
- [x] **AC-05:** No new `actionlint` findings.

## 5) Testing Evidence (link to runs)
- [x] **Lint** — `actionlint` finding count identical to `main` (7 before, 7 after), none in this step's line range.
- [x] **Typecheck / Build / Unit / Contract** — no application code, dependencies or schema touched.
- [ ] **Integration / E2E** — not affected.

**The defect, measured not inferred.** Production run [30862396299](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/30862396299):

```
Server: psql-qgp-prod (resource group rg-qgp-prod)
ERROR: unrecognized arguments: --name psql-qgp-prod
##[warning]Could not list backups for psql-qgp-prod — recovery point unverified.
```

Local `az` is 2.85.0, the runner is 2.86+. That skew is why verifying #1544 against the real production server still missed this.

**Each CLI generation exercised**, the first against the real production server and the rest against a stub reproducing the specific failure modes:

| Scenario | Expected | Observed |
| --- | --- | --- |
| `az` 2.86+ (matches the runner) | uses `--server-name` | "Listed backups using --server-name.", exit 0 |
| `az` 2.85 against real production | falls back to `--name` | "Listed backups using --name.", exit 0, 7 backups, newest 0.0 h |
| `AuthorizationFailed` | no retry, real error, warn only | error printed once, exit 0 |
| Backup older than threshold | **block the deploy** | exit 1, naming the age and the threshold |

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** A production deploy on the current runner image now records an actual recovery point in the job summary instead of a warning.
- [x] **CUJ-02:** A genuine lapse in Azure's automatic backups still stops the deploy before migrations run.
- [x] **CUJ-03:** An Azure outage or credential problem still warns rather than blocking, so the pipeline is not hostage to an unrelated API failure.

## 7) Observability & Ops
- **Logs:** The step now states which spelling worked, so the next CLI break is visible in the log rather than needing a reproduction.
- **Metrics / Alerts:** Unchanged. The geo-redundancy warning from #1544 still fires each deploy.
- **Runbook updates:** None.

**Adjacent findings, not fixed here:**
1. **`deploy-production.yml` has no `concurrency` guard.** Two merges in quick succession would run two production deploys against the same Web App simultaneously, which also races the `capture previous production image` step that the auto-rollback path depends on. Tonight this was avoided by hand, by waiting for one deploy to land before merging the next. It should be enforced rather than remembered.
2. Still open from #1544: geo-redundant backup disabled and 7-day retention on both servers.
3. Still open from #1546: `field_encryption.py` has no test coverage.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Not applicable; the step exists only in the production workflow.
- **Canary plan:** Not applicable to a pipeline gate.
- **Prod post-deploy checks:** The next production deploy is the verification. Confirm the log reads "Listed backups using --server-name." and that the `Pre-deploy recovery point` table appears in the job summary with a real backup age.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** The step blocking a deploy when backups are demonstrably healthy.
- **Rollback steps:** Revert this commit. That restores the #1544 behaviour, which warns rather than blocks, so reverting cannot wedge the pipeline. `rollback` and `auto-rollback` do not depend on this job in either case.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks.
- Failing run that prompted it: [30862396299](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/30862396299).
- Production state at time of writing: `0609fad3`, `healthz` and `readyz` both HTTP 200.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — n/a, production-only workflow
- [ ] **Gate 4:** Canary healthy (if used) — n/a
- [ ] **Gate 5:** Production verification plan + monitoring ready — per §8
