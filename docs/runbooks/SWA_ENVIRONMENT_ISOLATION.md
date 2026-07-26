# SWA Environment Isolation (PX-178)

How the frontend pipeline keeps the staging bake off the production hostname, and what to do when it does not.

**Module**: CI/CD Governance
**Version**: 1.0
**Last Updated**: 2026-07-26
**Workflow**: [`.github/workflows/azure-static-web-apps-purple-water-03205fa03.yml`](../../.github/workflows/azure-static-web-apps-purple-water-03205fa03.yml)
**Tickets**: PX-178 (P0, shared-hostname exposure), PX-191 (P3, undocumented behaviour)

---

## 1. Hostnames

A single Azure Static Web App resource serves multiple *environments*, each on its own hostname.

| SWA environment | Hostname | Baked `VITE_API_URL` | Audience |
|-----------------|----------|----------------------|----------|
| `default` (production) | `https://purple-water-03205fa03.6.azurestaticapps.net` | `https://app-qgp-prod.azurewebsites.net` | Real users |
| `staging` (pre-production) | `https://purple-water-03205fa03-staging.6.azurestaticapps.net` | `https://qgp-staging-plantexpand.azurewebsites.net` | Playwright gate only |

The named environment is selected by the `deployment_environment` input of
`Azure/static-web-apps-deploy@v1`. **Omitting that input deploys to `default`,
i.e. straight to the production hostname.** Azure derives the named hostname as
`<app-name>-<environment>.<region>.azurestaticapps.net`.

---

## 2. The defect this prevents

Before PX-178 the staging upload omitted `deployment_environment`, so the STAGING
bake was published to the production hostname. Consequences:

| Path | Old outcome | New outcome |
|------|-------------|-------------|
| Push to main, gate passes | Production served a staging-API frontend for the whole gate (~10-20 min), then was overwritten | Production never changes until the production bake is published |
| Push to main, gate fails | Staging bake **stranded** on production until a human ran the emergency job | Production keeps the last good production bake; nothing is published |
| `workflow_dispatch` validation mode | Staging bake stranded on production **permanently** — `deploy_production_swa` never runs on dispatch | Staging bake lands on the pre-production hostname; production untouched |
| `workflow_dispatch` with `force_production_bake=true` | `deploy_to_staging` ran concurrently with `emergency_production_bake` and raced it for the same hostname | `deploy_to_staging` is skipped; the emergency job is the only writer |

---

## 3. Job-to-hostname map

| Job | Trigger | Bakes | Writes to |
|-----|---------|-------|-----------|
| `build_and_deploy_job` | `pull_request` | Staging API | Nothing (build-only, no deploy step) |
| `deploy_to_staging` | push to main; dispatch without `force_production_bake` | Staging API | `staging` environment hostname |
| `staging_ui_verification` | same as above | — | Reads the `staging` hostname only |
| `deploy_production_swa` | push to main, after the gate passes | Production API | **Production hostname** |
| `emergency_production_bake` | dispatch with `force_production_bake=true` | Production API | **Production hostname** |
| `production_isolation_audit` | after the above, when `deploy_to_staging` succeeded | — | Nothing (reports only) |

**Invariant**: every job that bakes `STAGING_API_URL` either does not deploy at
all or passes `deployment_environment`. Only the two jobs that bake
`PRODUCTION_API_URL` omit it. This holds structurally, independent of any `if:`
condition.

---

## 4. Layered controls

| Control | Where | Fails the run? |
|---------|-------|----------------|
| `deployment_environment` on the staging upload | `deploy_to_staging` | Yes, if Azure rejects it (fail-safe: nothing reaches production) |
| Resolve pre-production hostname and compare to production | `deploy_to_staging` | No, by design — see below |
| Probe the production hostname for a staging-API bundle | `deploy_to_staging` | No, by design |
| Playwright hard gate | `staging_ui_verification` | Yes — blocks the production write |
| `Verify tip==LIVE production API bake` (scans `dist/`) | `deploy_production_swa`, `emergency_production_bake` | Yes — blocks the production write |
| `production_isolation_audit` | final job | Yes |

### Why the isolation checks do not fail immediately

If isolation were ever violated, the best available outcome is for
`deploy_production_swa` to run and overwrite the bad content. Failing
`deploy_to_staging` would starve that job of its `needs` and leave the staging
bundle on the production hostname — reproducing PX-178 rather than fixing it.

So detection is recorded as a job output, the pipeline continues, and
`production_isolation_audit` — which depends on `deploy_production_swa` with
`always()` — turns the run red afterwards. Self-healing and loud failure, in
that order.

### Probe scope

The probe fetches `/` from the production hostname and inspects the
`/assets/*.js` entry chunks it references (max 10). It strips the legitimate
`staging: '<url>'` entry of the `API_URLS` map in
[`frontend/src/config/apiBase.ts`](../../frontend/src/config/apiBase.ts) before
looking for the staging URL, so a correct production bundle does not trip it. It
is best-effort: it does not walk lazily-loaded chunks, and reports `unknown`
(non-blocking) when the hostname cannot be reached.

---

## 5. Recovery

If `production_isolation_audit` fails, or the production hostname is otherwise
serving the wrong API:

1. Re-publish a production bake:

```bash
gh workflow run azure-static-web-apps-purple-water-03205fa03.yml \
  -f force_production_bake=true
```

2. Confirm the served bundle:

```bash
curl -s https://purple-water-03205fa03.6.azurestaticapps.net/ \
  | grep -o '/assets/[^"]*\.js' | head -1
# then fetch that chunk and confirm it inlines app-qgp-prod, not qgp-staging-plantexpand
```

3. Confirm `deployment_environment` is still present on the staging upload step
   in the workflow. Its removal is the single change that reintroduces PX-178.

---

## 6. Environment capacity

The Free plan allows 3 staging environments; the Standard plan allows 10. This
pipeline now holds one permanently (`staging`). It does not create per-PR preview
environments — PRs are build-only — so the reserved slot does not compete with PR
previews.

[`swa-environment-cleanup.yml`](../../.github/workflows/swa-environment-cleanup.yml)
only deletes environments whose names are purely numeric (former PR previews) and
explicitly skips non-numeric names, so it will not delete the `staging`
environment.

---

## 7. Known follow-ups

- [`SWA_DEPLOYMENT_POLICY.md`](SWA_DEPLOYMENT_POLICY.md) §2 "Bake semantics (same
  hostname)" describes the pre-PX-178 behaviour and is superseded by section 3
  above.
- The staging API allows the new origin via the
  `^https://[a-z0-9-]+\.[0-9]+\.azurestaticapps\.net$` regex in
  [`src/main.py`](../../src/main.py); no CORS change was required. If that regex
  is ever tightened to an explicit allowlist, the pre-production hostname must be
  added to it.
- The workflow has no `concurrency` group, so two overlapping pushes to main can
  still interleave their production bakes. Unrelated to the hostname split, but
  it is the remaining way an older commit can win on the production hostname.

---

## Related Documents

- [`SWA_DEPLOYMENT_POLICY.md`](SWA_DEPLOYMENT_POLICY.md) — deployment triggers and environment limits
- [`AZURE_SWA_GOVERNANCE.md`](AZURE_SWA_GOVERNANCE.md) — SWA governance controls
- [`AZURE_SWA_ENVIRONMENT_CLEANUP.md`](AZURE_SWA_ENVIRONMENT_CLEANUP.md) — cleanup procedure
