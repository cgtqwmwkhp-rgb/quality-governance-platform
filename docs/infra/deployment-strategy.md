# Deployment Strategy (D18 — CD Pipeline Enhancement)

This document describes how we deploy the Quality Governance Platform today, where we are heading, rollback, canary, freezes, hotfixes, and cadence.

## Current State

- **Single-slot deployment** (or primary production slot) with **automated health checks** after deploy.
- **SHA verification** against the build artifact to ensure the running image matches the intended commit.

## Target State

- **Staged rollout** with **health-gated promotion**: each stage must pass automated health and smoke checks before the next stage proceeds (except where a documented manual gate applies).

## Deployment Stages

1. **Build** — compile, test, container image build, push to registry, record digest / SHA.
2. **Staging deploy** — deploy to staging slot or environment; run migrations as per runbook.
3. **Smoke tests** — API liveness/readiness, critical user journeys, worker sanity.
4. **Manual gate** — engineer or release manager approves production promotion.
5. **Production deploy** — deploy to production (or swap to production slot).
6. **Health check** — `/healthz`, `/readyz`, `/metrics/resources`, error-rate dashboards.
7. **Traffic shift** — move 100% traffic to the new revision (or phased shift when canary is enabled).

## Rollback Strategy

- **Previous container image** remains available in the registry — redeploy the last known-good digest.
- Azure App Service slots: use slot swap reset when applicable:

```bash
az webapp deployment slot swap --action reset \
  --resource-group <RG> --name <APP_NAME> --slot <SLOT_NAME>
```

- If database migrations are backward-incompatible, follow the expand/contract migration playbook before relying on instant rollback.

## Canary Plan

| Phase | Description |
|-------|-------------|
| **Phase 1 (current)** | **Manual gate** after staging smoke tests; single promotion to production. |
| **Phase 2** | **Slot-based canary** with **10% → 50% → 100%** traffic shift, gated by health metrics and error budgets between steps. |

## Deploy Freeze Policy

- **No deploys** from **Friday 4pm** through **Monday 9am** (local business timezone unless otherwise stated).
- **No deploys** during **company holidays** listed on the internal calendar.
- **Exceptions**: require written approval from engineering leadership + product owner, documented incident or release ID, and a named rollback owner.

## Hotfix Process

- **Emergency PRs** may **bypass full staging** for **P1 incidents** only, with:
  - Minimal change set scoped to the incident
  - **Two approvals** (e.g., senior engineer + on-call lead or release manager)
  - Post-deploy verification and **scheduled** follow-up to merge equivalent changes through the normal pipeline

## Release Cadence

| Type | Cadence |
|------|---------|
| **Standard releases** | **Tuesday** and **Thursday** (primary windows) |
| **Hotfixes** | **Any time** when justified by severity and freeze policy |
