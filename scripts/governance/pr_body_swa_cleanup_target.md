# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Point the nightly SWA cleanup at the Static Web App and resource group that actually exist
- **User goal (1–2 lines):** Finish making the nightly cleanup work. #1549 fixed the credential it logs in with, but the very next step would still have failed, because the app name and resource group are both wrong.
- **In scope:** `SWA_APP_NAME` and `RESOURCE_GROUP` in `swa-environment-cleanup.yml`.
- **Out of scope:** The deletion logic itself, which is sound and needed no change. Also out of scope: the findings carried forward from #1549 §7 (production E2E secrets, a CI guard for unresolved secret references, two divergent rollback paths).
- **Feature flag / kill switch:** The workflow's existing `DISABLE_CLEANUP` switch, untouched and still `'false'`.

## 2) Impact Map (what changed)
- **Frontend / Backend / APIs / Schemas / Database:** None.
- **Workflows/jobs/queues:** Two `env` values in one workflow. No step, trigger or logic change.
- **Config/env/flags:** No secret created or altered.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** `qgp-frontend` in `rg-qgp-staging` is the app that PR previews deploy to. Its default hostname is `purple-water-03205fa03.6.azurestaticapps.net`, which is where the old value was evidently copied from, and the preview deploy workflow authenticates with `AZURE_STATIC_WEB_APPS_API_TOKEN_PURPLE_WATER_03205FA03` — the same app.
- **Tolerant reader / strict writer applied?** N/A.
- **Breaking changes:** None. Every `az staticwebapp` call in this workflow currently fails, so it cannot regress.
- **Migration plan:** None.
- **Rollback strategy (DB):** No data impact.

**On deletion safety, since this makes a delete-capable workflow functional for the first time.** Three independent guards were checked against live Azure state rather than read and assumed: `default` is excluded by `PRODUCTION_ENV_NAME`; any environment whose name is not purely numeric is skipped explicitly; and a numeric environment is only deleted when its PR number is not in the open-PR list. The only non-production environment that exists is `staging`, which is non-numeric and therefore skipped.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** `az staticwebapp environment list` succeeds against the corrected app and resource group.
- [x] **AC-02:** The workflow's production-protection check finds `default` and reports it protected.
- [x] **AC-03:** Running the workflow's own stale-detection logic against live Azure state selects **nothing** for deletion.
- [x] **AC-04:** `staging` is skipped as non-numeric rather than treated as stale.
- [x] **AC-05:** The workflow still parses as valid YAML with `DISABLE_CLEANUP` unchanged.
- [ ] **AC-06:** A real dispatched run completes successfully — verified post-merge per §8, since only the merged workflow can be dispatched.

## 5) Testing Evidence (link to runs)
- [x] **Lint** — two `env` scalar values changed; no shell or expression syntax touched.
- [x] **Typecheck / Build / Unit / Contract / E2E** — no application code, dependencies or schema touched.

**The defect, reproduced against live Azure with the workflow's exact command:**

```
$ az staticwebapp environment list --name purple-water-03205fa03 --resource-group rg-qgp-prod
ERROR: (ParentResourceNotFound) Failed to perform 'read' on resource(s) of type
'staticSites/builds', because the parent resource
'/resourceGroups/rg-qgp-prod/providers/Microsoft.Web/staticSites/purple-water-03205fa03'
could not be found.
```

`rg-qgp-prod` contains no Static Web App at all — confirmed by listing the subscription's apps and filtering on that resource group, which returns empty.

**The corrected target, and the workflow's own logic run against it:**

```
all envs               : default staging
non-prod envs          : staging
production protection  : OK (default found)
skip non-numeric       : staging
would delete           : (nothing)
```

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** The nightly cleanup can enumerate environments instead of erroring, so the eight-night failure streak ends.
- [x] **CUJ-02:** Production preview environment is protected — `default` is excluded, verified against live state rather than inferred from the code.
- [x] **CUJ-03:** The `staging` environment survives. This was the real risk in making a delete-capable workflow functional, and it is guarded twice over: non-numeric names are skipped, and only closed-PR numbers are ever selected.

## 7) Observability & Ops
- **Logs:** The workflow already prints its environment table and per-environment decisions, so the first real run is self-documenting.
- **Metrics / Alerts:** A nightly red run stops. Eight consecutive ignorable failures is how a real one comes to be ignored too, which is the substantive reason to fix this rather than mute it.
- **Runbook updates:** None.

**Carried forward, still open:** the production audit lifecycle E2E skipping for want of `PROD_E2E_EMAIL`/`PROD_E2E_PASSWORD`; no CI guard that referenced secrets resolve; and two rollback paths that must be kept in step by hand.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Not applicable; this workflow deploys no application code.
- **Canary plan:** Not applicable.
- **Prod post-deploy checks:** After merge, dispatch `Azure SWA Environment Cleanup` and confirm it logs in, lists both environments, reports production protected, and deletes nothing. Combined with #1549 that is also the closest safe evidence that `Emergency Rollback - Production` can now authenticate, since both use the identical `azure/login@v3` step and credential — short of rolling production back to find out.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** The dispatched run selecting any environment for deletion, or `AZURE_CREDENTIALS` proving to lack permission on `rg-qgp-staging`.
- **Rollback steps:** Set `DISABLE_CLEANUP: 'true'` for an immediate stop without reverting, or revert this commit to return to a workflow that fails harmlessly at the first `az` call.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks.
- Failing nightly that started this: [30873781761](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/30873781761).
- Preceding fix: #1549.
- Production state at time of writing: `81407410`, `healthz` and `readyz` both HTTP 200.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — n/a, no application code
- [ ] **Gate 4:** Canary healthy (if used) — n/a
- [ ] **Gate 5:** Production verification plan + monitoring ready — per §8
