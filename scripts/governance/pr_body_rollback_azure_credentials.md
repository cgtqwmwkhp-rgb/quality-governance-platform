# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Point the Emergency Rollback and nightly SWA cleanup workflows at an Azure credential that exists
- **User goal (1–2 lines):** Make the emergency production rollback workflow able to authenticate. It references a secret that has never existed, so it would have failed at the login step the first time anyone reached for it during an incident.
- **In scope:** The `azure/login` credential reference in `rollback-production.yml` and `swa-environment-cleanup.yml`.
- **Out of scope:** Creating the missing `PROD_E2E_EMAIL` / `PROD_E2E_PASSWORD` secrets (§7 — needs a decision about a production test account), and adding a CI guard that every referenced secret exists (§7 — needs a token with secret-read scope).
- **Feature flag / kill switch:** None applicable.

## 2) Impact Map (what changed)
- **Frontend / Backend / APIs / Schemas / Database:** None.
- **Workflows/jobs/queues:** One `creds:` value in each of two workflows. No job graph, trigger or step-order change.
- **Config/env/flags:** No secret is created or altered. This only stops referencing a name that resolves to nothing.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** `AZURE_CREDENTIALS` is the credential the production deploy already authenticates with, against the same subscription and the same `rg-qgp-prod` resources these two workflows target. Fourteen existing references use it successfully, so its scope is proven by the deploys that ran last night.
- **Tolerant reader / strict writer applied?** N/A.
- **Breaking changes:** None. Both workflows currently fail or would fail at login; neither can regress from that.
- **Migration plan:** None.
- **Rollback strategy (DB):** No data impact.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** No workflow references `secrets.AZURE_CREDENTIALS_PROD` any more.
- [x] **AC-02:** Both files still parse as valid workflow YAML with their jobs intact.
- [x] **AC-03:** `actionlint` finding count unchanged for both files (22 before, 22 after).
- [x] **AC-04:** Every remaining unresolved secret reference in `.github/workflows` is accounted for as a deliberate optional override, or recorded in §7 — verified by auditing all 24 references against the 16 secrets that exist.
- [ ] **AC-05:** The nightly cleanup authenticates successfully on its next run. Verified post-merge by dispatching it — see §8, since only the merged workflow can be dispatched.

## 5) Testing Evidence (link to runs)
- [x] **Lint** — `actionlint` reports 22 findings on `main` for these two files and 22 after; all pre-existing and untouched.
- [x] **Typecheck / Build / Unit / Contract / E2E** — no application code, dependencies or schema touched.

**The defect, measured.** `gh secret list` returns 16 repository secrets and both GitHub Environments (`production`, `staging`) hold none. `AZURE_CREDENTIALS_PROD` is not among them. The nightly `Azure SWA Environment Cleanup` has failed on exactly this for eight consecutive nights:

```
2026-08-04T03:06  failure     2026-07-31T03:07  failure
2026-08-03T03:07  failure     2026-07-30T03:06  failure
2026-08-02T03:07  failure     2026-07-29T03:05  failure
2026-08-01T03:06  failure     2026-07-28T03:06  failure
```

each with:

```
##[error]Login failed with Error: Using auth-type: SERVICE_PRINCIPAL. Not all values
are present. Ensure 'client-id' and 'tenant-id' are supplied.
```

**Full secret audit.** All 24 `secrets.*` references across `.github/workflows` were checked against the 16 that exist. `GITHUB_TOKEN` is supplied by Actions. Eight resolved to nothing; after this change, seven remain and every one is intentional:

| Secret | Where | Behaviour when absent |
| --- | --- | --- |
| `AZURE_CREDENTIALS_PROD` | rollback + cleanup | **Hard login failure — fixed by this PR** |
| `AZURE_PROD_WEBAPP_NAME` | canary routing | Falls back to `$AZURE_WEBAPP_NAME`; step is `continue-on-error` |
| `PROD_MIGRATION_SUBNET_ID` | migration network | Explicitly optional; subnet auto-discovered |
| `AZURE_DB_SERVER_NAME` | recovery point check | Falls back to Key Vault; confirmed working in run 30866772620 |
| `PROD_E2E_EMAIL` / `PROD_E2E_PASSWORD` | prod audit E2E | Skips with a message — **see §7** |
| `QGP_STAGING_READ_TOKEN` | nightly contract | Nightly run 03:03 today still reported `SUCCESS (VERIFIED)` |
| `STAGING_BASE_URL` | chaos testing | Manually dispatched workflow |

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Emergency production rollback — the login step now references the credential that the production deploy authenticates with, so the workflow can reach Azure. Deliberately **not** executed, because running it would roll production back; the cleanup workflow shares the identical login step and is the safe proxy (§8).
- [x] **CUJ-02:** Automatic recovery is unaffected and was never broken — the `rollback` and `auto-rollback` jobs in `deploy-production.yml` both use `AZURE_CREDENTIALS`.
- [ ] **CUJ-03:** Nightly preview-environment cleanup succeeds — confirmed post-merge per §8.

## 7) Observability & Ops
- **Logs / Metrics:** Unchanged.
- **Alerts:** A nightly red run disappears. That matters beyond the job itself: eight nights of an ignorable failure is how a genuine one gets ignored too.
- **Runbook updates:** None needed, but worth knowing that `docs/runbooks/rollback-decision-tree.md` points operators at a rollback path whose dedicated workflow could not have run.

**Findings recorded, not fixed here:**
1. **The production audit lifecycle E2E has never run.** `PROD_E2E_EMAIL` / `PROD_E2E_PASSWORD` do not exist, so every production deploy skips it with an informational line. It is `continue-on-error: true` and advisory by design, but the practical effect is that a post-deploy verification we appear to have is not happening. Needs a decision on a production test account rather than a code change.
2. **Nothing prevents this recurring.** A CI check that every `secrets.*` reference resolves would have caught this in January. It needs a token with secret-read scope, so it is a permissions decision, not a scripting one.
3. **Two rollback paths exist** — the `rollback` job inside `deploy-production.yml` and this standalone workflow. Two paths that must stay in step is how one of them rots unnoticed. Worth considering consolidation.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Not applicable; neither workflow deploys application code.
- **Canary plan:** Not applicable.
- **Prod post-deploy checks:** After merge, dispatch `Azure SWA Environment Cleanup` manually and confirm the Azure login succeeds. That exercises the identical `azure/login@v3` step with the identical credential as the rollback workflow, which is the closest safe proof that emergency rollback can now authenticate — short of rolling production back to find out.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** `AZURE_CREDENTIALS` turning out to lack a permission these two workflows need, which would surface as an authorization error after a successful login.
- **Rollback steps:** Revert this commit. That restores a login that fails outright, so reverting cannot make either workflow less capable than it is today. The real remedy in that case would be to create a correctly-scoped `AZURE_CREDENTIALS_PROD` rather than to revert.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks.
- Failing nightly that exposed it: [30873781761](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/30873781761).
- Production state at time of writing: `81407410`, `healthz` and `readyz` both HTTP 200.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — n/a, neither workflow deploys application code
- [ ] **Gate 4:** Canary healthy (if used) — n/a
- [ ] **Gate 5:** Production verification plan + monitoring ready — per §8
