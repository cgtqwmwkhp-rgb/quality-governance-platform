# ADR-0019: Isolate Production Hosting and Consolidate on UK South

**Status**: Proposed
**Date**: 2026-07-25
**Decision Makers**: Platform Team — awaiting review

## Context

Investigating why the production Celery worker's logs had gone silent (fixed in #1290) surfaced
the hosting layout underneath. It was never decided; it accumulated.

### What exists today

Every App Service — both environments — runs on **one** App Service Plan:

| Fact | Value |
|---|---|
| Plan | `plan-qgp-staging-weu` |
| SKU | **Basic B2** (2 vCPU, 3.5 GB), **1 instance** |
| Sites on it | **6** — `app-qgp-prod`, `app-qgp-prod-worker`, `app-qgp-prod-beat`, `qgp-staging-plantexpand`, `-worker`, `-beat` |
| Plan region | **West Europe** |
| Resource group | `rg-qgp-staging` — including all three production sites |

Data and dependencies sit elsewhere:

| Resource | Region | Resource group |
|---|---|---|
| `psql-qgp-prod`, `psql-qgp-staging` | UK South | `rg-qgp-prod` / `rg-qgp-staging` |
| `redis-qgp-prod`, `redis-qgp-staging` | UK South | `rg-qgp-staging` |
| `acrqgpprodcdcd4691` (prod images) | UK South | `rg-qgp-staging` |
| `kv-qgp-prod` | **West Europe** | `rg-qgp-staging` |
| `stqgpprdcdd14b` (prod documents) | **West Europe** | `rg-qgp-staging` |

`rg-qgp-prod` contains only the production database, a legacy container app and a Log Analytics
workspace. `app-qgp-prod` has no custom domain: its public URL is `app-qgp-prod.azurewebsites.net`,
so the Azure resource name *is* the contract with the frontend.

### Why this matters

**1. Staging and production compete for the same 2 vCPUs.** Two API apps, two Celery workers
(concurrency 2 each) and two beat schedulers share one Basic B2 instance. This is the most likely
explanation for the cold starts we have been designing around rather than fixing: a staging worker
redeploy was observed unreachable for **5m10s**, and #1287 raised the smoke-test retry budget from
~50s to ~10min to accommodate it. That budget is a symptom.

**2. Basic tier has no deployment slots.** Deploys therefore restart in place, which is precisely
when the worker is unavailable — and, per #1290, when its log capture has been observed to die
permanently. No slots also means no warm-up before traffic and no instant rollback.

**3. Compute is in a different country from its data.** Every database query, every Celery broker
round-trip and every container image pull crosses West Europe ↔ UK South. It also means the
production document store (`stqgpprdcdd14b`) and `kv-qgp-prod` hold UK governance data in the
Netherlands, which is a question for the business, not for engineering.

**4. Basic tier cannot autoscale and offers no zone redundancy.** A single instance is a single
point of failure for production.

## Decision (proposed)

Move production onto its own Premium v3 plan in UK South, in `rg-qgp-prod`, and put a custom domain
in front of the API first so the public URL stops being tied to an Azure resource name.

The custom domain is sequenced first deliberately. App Service names are globally unique, so while
`app-qgp-prod` exists no replacement can take that name — meaning a region move today forces either
a client-visible URL change or a delete-then-recreate with real downtime and a name-squatting
window. A custom domain removes that constraint permanently, for this migration and every one after.

### Costed options

Monthly, GBP, Azure retail as at 2026-07-25 (`prices.azure.com`, 730h):

| Option | Production | Staging | Total | Δ vs today |
|---|---|---|---|---|
| **0. Do nothing** | shared B2 WEU £19.93 | (shared) | **£19.93** | — |
| **1. Split only** (both stay Basic, UK South) | B2 £19.34 | B1 £9.93 | **£29.27** | +£9.34 |
| **2. Recommended** — prod Premium v3, staging Basic | **P0v3 £47.82** | B1 £9.93 | **£57.75** | +£37.82 |
| **3. Headroom** — prod P1v3 | P1v3 £95.65 | B1 £9.93 | **£105.58** | +£85.65 |

Option 2 is recommended. P0v3 is the cheapest tier that provides deployment slots, autoscale and
proper warm-up, and it is **cheaper than Standard S1 (£55.33)** while being a newer generation.
Option 1 removes contention but keeps the no-slots restart problem, so the 10-minute smoke budget
and the restart-time log gap would stay.

Against +£37.82/month, note that £921/year of empty Standard container registries was deleted on
2026-07-25 as part of this investigation, so the net position is still a saving.

### Sequence

Each step is independently reversible and none is a point of no return.

1. **Custom domain + managed certificate** on the existing `app-qgp-prod`; point `frontend/src/config/apiBase.ts` at it and redeploy the frontend. No infrastructure moves. Verify old and new hostnames both serve.
2. **New plan** `plan-qgp-prod-uks` (P0v3) in `rg-qgp-prod`, UK South.
3. **New sites** for API, worker and beat on that plan, from the same image digest, with app settings copied from the current sites and the `celery-logs` diagnostic setting from `provision-celery-workers.sh`.
4. **Verify against production data** before any cutover: `/api/v1/health`, `inspect ping`, one index job end to end, and the Log Analytics query in `CELERY_WORKER_BEAT_DEPLOY.md`.
5. **Cut over** by repointing the custom domain. Roll back by repointing it. Keep the old sites stopped but intact for one week.
6. **Move the stragglers**: `kv-qgp-prod` and `stqgpprdcdd14b` to UK South (storage requires a copy, so treat as its own change with its own ADR), then retire the old sites and plan.
7. **Update `deploy-production.yml`** resource group and app names, and delete the West Europe plan only once nothing references it.

### Explicitly not proposed here

- Moving staging into `rg-qgp-staging` cleanly, or renaming `plan-qgp-staging-weu`. Cosmetic next to the above.
- Zone redundancy or multi-region. Premium v3 makes it possible later; nothing today needs it.
- Touching `infra/main.bicep`. It does not describe live production and is not deployed; reconciling it is separate work and out of scope.

## Consequences

**If accepted:** production stops sharing CPU with staging; deploys become slot swaps rather than
restarts, which removes the 5-minute worker outage and the retry budget that hides it; compute sits
with its data; and the public URL is decoupled from Azure resource naming. Cost rises £37.82/month
before the registry saving.

**If rejected:** the shared Basic B2 instance remains a single point of failure for production, and
staging load will continue to affect production. Any future recurrence of the worker log gap or the
5-minute cold start should be read against this ADR rather than investigated afresh.

**Either way:** the discovery work stands on its own. #1290 gave the worker a durable log sink, and
the empty registries and dead container instances are already gone.

## References

- #1287 — raised the Celery smoke retry budget to ~10min to survive a 5m10s worker restart.
- #1290 — durable log sink; the investigation that surfaced this layout.
- `docs/runbooks/CELERY_WORKER_BEAT_DEPLOY.md` — how to verify worker health without filesystem logs.
