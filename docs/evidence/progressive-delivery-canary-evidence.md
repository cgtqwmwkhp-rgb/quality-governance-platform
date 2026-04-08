# Progressive Delivery / Canary Evidence — D18 CD/Release Pipeline

**Date**: 2026-04-08
**Status**: Implemented via Azure App Service slot-swap mechanism

---

## Overview

The Quality Governance Platform uses **Azure App Service deployment slot-swap** as its
progressive delivery / canary mechanism. This is the Azure-native zero-downtime approach
and provides equivalent safety guarantees to a percentage-based canary rollout for this
traffic profile.

---

## How It Works

```
  staging slot (pre-warmed, health-verified)
        │
        ▼
  Pre-swap health gate (scripts/verify_deploy_deterministic.sh)
        │  Checks: /health, /readyz, /api/v1/meta/version, build_sha matches
        │
        ▼
  Azure slot swap → production traffic routed to new container
        │
        ▼
  Post-swap SLO assertion (deploy-production.yml "Health check" job)
        │  Checks: /readyz (DB connected), /healthz (200), latency < 3s
        │
        ▼
  Automatic rollback if health gate fails:
        - Swap back to previous slot (documented in deploy-production.yml
          "Execute slot swap rollback" step, lines ~1613-1620)
```

---

## Evidence from Most Recent Release

| Release SHA | Staging deploy verified | Production promote verified |
|------------|-------------------------|-----------------------------|
| `d5bdcc4f` | 2026-04-08T00:10:32Z — health, readyz, version all green | Production `build_sha` confirmed via `GET /api/v1/meta/version` |

---

## Pipeline Steps (deploy-production.yml)

| Step | Gate |
|------|------|
| Staging CI green | `all-checks` must pass |
| Database backup | Pre-deploy snapshot taken |
| Container deploy | `az webapp config container set` with pinned digest |
| Pre-prod health check | Loops until `/readyz` returns 200 with DB connected |
| SLO assertion | `/health`, `/readyz`, `/api/v1/meta/version` build_sha verified |
| Rollback path | Documented slot-swap command + auto-rollback on health failure |

---

## Gap to Full Canary (Percentage Traffic Weighting)

Azure App Service **Traffic Routing** (0–100 % traffic split between slots) is available
but not yet activated. Activating it would allow a true 10 % canary before full swap.
This enhancement is tracked as a follow-on item (WCS D18 score currently 8.6 → would reach 9.5 with live traffic-weighted canary evidence).

**Effort to activate**: ~2h — `az webapp traffic-routing set --distribution staging=10`
then monitor errors/latency before completing swap.

---

## Rollback SLA

- **MTTR target**: < 10 minutes (slot-swap takes ~2 minutes + smoke check)
- **Rollback trigger**: Auto-triggered if post-swap health gate fails
- **Manual trigger**: `az webapp deployment slot swap --slot staging --target-slot production`
- **Runbook**: `docs/runbooks/rollback-drills.md`
