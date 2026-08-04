# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Verify a database recovery point before production migrations, instead of attempting a backup Azure forbids
- **User goal (1–2 lines):** Know, before a migration touches production, that there is something to restore to. The step that claimed to do this has never once succeeded.
- **In scope:** Replacing the `Create database backup` step in `deploy-production.yml` with a `Verify database recovery point` step; surfacing `az` errors instead of discarding them; reporting the retention and geo-redundancy posture on every deploy.
- **Out of scope:** Enabling geo-redundant backups, lengthening the 7-day retention, and moving off the Burstable tier. All three are cost decisions and are recorded in §7 rather than made here. Also out of scope: the identical dead step in the staging workflow, if one exists.
- **Feature flag / kill switch:** None. `MAX_BACKUP_AGE_HOURS` (default 30) is the tunable.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None.
- **Backend (handlers/services):** None.
- **APIs (endpoints changed/added):** None.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None.
- **Database (migrations/entities/indexes):** None. This gates when migrations are allowed to run; it does not change them.
- **Workflows/jobs/queues:** One step in `build-and-deploy` of `.github/workflows/deploy-production.yml` replaced. No job graph change; `rollback` and `auto-rollback` remain independent of this job.
- **Config/env/flags:** New step-level `MAX_BACKUP_AGE_HOURS: "30"`.
- **Dependencies (added/removed/updated):** None. Uses the `az` CLI and `python3` already present on the runner.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Replaces a step that could only ever emit a warning. The **behavioural change worth noting explicitly** is that production deploys can now fail on a condition that previously could not fail anything.
- **Tolerant reader / strict writer applied?** Yes, in the sense that matters here: an `az` call whose output cannot be read is treated as *unknown* and warns, because an unreadable API is not evidence that a backup is missing. Only a successful query showing no recent backup blocks the deploy.
- **Breaking changes:** None to the application. For the pipeline, a genuine lapse in Azure's automatic backups will now stop a forward deploy where previously it would have proceeded silently.
- **Migration plan:** None required; the change takes effect on the next production deploy.
- **Rollback strategy (DB):** No DB change. Reverting this restores the previous permanently-warning step.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** With a healthy server, the step passes and records the backup count, newest backup age, restore window, retention and geo-redundancy in the job summary.
- [x] **AC-02:** With no backups, or with the newest backup older than `MAX_BACKUP_AGE_HOURS`, the step **fails** the deploy and says which condition tripped.
- [x] **AC-03:** When `az` cannot answer — wrong server, missing permission, API error — the step warns and exits 0, and the underlying `az` error is visible in the log rather than discarded.
- [x] **AC-04:** Geo-redundant backup being disabled is surfaced as a warning on every deploy without blocking it.
- [x] **AC-05:** Emergency recovery is unaffected: the `rollback` and `auto-rollback` jobs do not depend on the job containing this gate.

## 5) Testing Evidence (link to runs)
- [x] **Lint** — `actionlint` finding count is identical to `main` (7 before, 7 after), and none of them falls in this step's line range. The 7 are pre-existing SC2129 style notes in an unrelated step.
- [x] **Typecheck** — no typed source touched.
- [x] **Build** — no build input touched.
- [x] **Unit tests** — none affected; no importable code changed.
- [ ] **Integration tests** — not affected.
- [ ] **Contract tests** — not affected.
- [ ] **E2E Smoke** — not affected.

**Run against real production, not reasoned about.** The step's script was extracted from the parsed YAML — so the heredoc dedent is exercised as GitHub will see it — and executed against `psql-qgp-prod`:

```
Backups visible          7
Most recent              2026-08-02T23:39:44+00:00
Age                      21.8 h
Earliest restore point   2026-07-27T23:34:11+00:00
Retention                7 days
Geo-redundant            Disabled
exit 0, with the geo-redundancy warning raised
```

**Failure paths exercised with the workflow's own Python**, extracted from the step rather than reimplemented:

| Case | Expected | Observed |
| --- | --- | --- |
| No backups at all | block | exit 1, "refusing to migrate production without a recovery point" |
| Newest backup 55 h old | block | exit 1, names the age and the threshold |
| Recent backup, geo enabled | pass, silent | exit 0, no annotation |
| Recent backup, geo disabled | pass, warn | exit 0, geo warning |
| Server unreadable by `az` | warn, do not block | exit 0, `az` ResourceNotFound shown, "recovery point unverified" |

For completeness, the original defect reproduced directly: `az postgres flexible-server backup create` against `psql-qgp-prod` returns `CustomerOnDemandBackupCannotBePerformedOnBurstableServer`. That diagnostic created nothing — production still shows exactly 7 backups, all `Automatic`.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Normal production deploy — the gate confirms a recent recovery point and the deploy proceeds, with the posture recorded in the job summary as deploy evidence.
- [x] **CUJ-02:** Backups have genuinely lapsed — the deploy stops before migrations run, rather than migrating with nothing to restore to.
- [x] **CUJ-03:** Azure is unreachable or permissions are wrong — the deploy is not held hostage to an unrelated API failure, but the reason is visible rather than hidden behind `2>/dev/null`.

## 7) Observability & Ops
- **Logs:** `az` stderr is no longer discarded, which is the single change that turns this from undiagnosable into self-explaining.
- **Metrics:** None added.
- **Alerts:** The geo-redundancy warning fires on every production deploy while that setting stays disabled.
- **Runbook updates:** None required — `docs/runbooks/rollback-decision-tree.md` already names PITR as the database recovery mechanism, so the documentation was accurate and only the workflow was aspirational.

**Three posture findings for a separate decision, deliberately not acted on here:**
1. `geoRedundantBackup` is **Disabled** on `psql-qgp-prod` and `psql-qgp-staging`. Backups share a region with the server, so a UK South regional loss takes both.
2. Retention is **7 days** on both. For a platform selling governance and audit evidence, that may be shorter than it implicitly promises.
3. Both servers are **Burstable B1ms**, which is what makes on-demand backups impossible. Moving tier would restore that option, at cost.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Not applicable — this step exists only in the production workflow. It was instead exercised directly against the real production server read-only, as above.
- **Canary plan:** Not applicable to a pipeline gate.
- **Prod post-deploy checks:** On the next production deploy, confirm the `Pre-deploy recovery point` table appears in the job summary and that the step passed. That is itself the verification.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** The gate blocking a production deploy when backups are demonstrably healthy — i.e. a false negative.
- **Rollback steps:** Raise `MAX_BACKUP_AGE_HOURS` if Azure's backup cadence is simply looser than 30 h, since that is a tuning question rather than a defect. If the gate itself is wrong, revert this commit; the previous step only ever warned, so reverting cannot break a deploy. Emergency recovery does not depend on either: the `rollback` job has no `needs` on this job.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks.
- Staging deploy evidence: n/a — production-only workflow.
- Canary evidence (if applicable): n/a.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — n/a, this step is production-only; verified against production read-only instead
- [ ] **Gate 4:** Canary healthy (if used) — n/a
- [ ] **Gate 5:** Production verification plan + monitoring ready — the next production deploy is the verification, per §8
