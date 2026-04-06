# Rollback Decision Tree (D18)

**Owner:** Platform Engineering
**Version:** 1.0
**Last Updated:** 2026-04-04
**Review Cycle:** Quarterly

---

## 1. Purpose

Operator guidance for choosing the correct rollback strategy when a production issue is detected. This tree covers the four primary failure modes and maps each to a concrete remediation path with expected RTO and risk level.

---

## 2. Decision Flowchart

```
Production Issue Detected
    │
    ├─ Is the issue in application code (not data/schema)?
    │   │
    │   ├─ YES ─ Was the deploy < 1 hour ago?
    │   │   │
    │   │   ├─ YES → STRATEGY A: Slot Swap Reversal
    │   │   │
    │   │   └─ NO  → STRATEGY B: Image Pin Rollback
    │   │
    │   └─ NO ─ Is it a database / schema issue?
    │       │
    │       ├─ YES → STRATEGY C: Database Recovery
    │       │
    │       └─ NO ─ Is it a configuration issue?
    │           │
    │           ├─ YES → STRATEGY D: Config Rollback
    │           │
    │           └─ NO  → Escalate to on-call lead
    │                    (see docs/runbooks/escalation.md)
```

---

## 3. Strategy A — Slot Swap Reversal

| | |
|---|---|
| **When** | Application regression caught **within 1 hour** of deploy; previous version still warm in staging slot |
| **How** | Re-swap the staging and production deployment slots |
| **RTO** | ~2 minutes |
| **Risk** | **Low** — previous version is still running in the staging slot |

### Procedure

1. Confirm the staging slot still holds the prior known-good build.
2. Execute the swap:

```bash
az webapp deployment slot swap \
  --resource-group rg-qgp-production \
  --name qgp-production \
  --slot staging \
  --target-slot production
```

3. Verify rollback (see [Verification Checklist](#7-rollback-verification-checklist) below).
4. Notify via [Communication Protocol](#8-communication-protocol).

**Reference:** `.github/workflows/deploy-production.yml` — "Execute slot swap rollback" step (auto-rollback on health-check failure).

---

## 4. Strategy B — Image Pin Rollback

| | |
|---|---|
| **When** | Need to deploy a specific known-good version, or the staging slot has been overwritten |
| **How** | Trigger the `rollback-production.yml` workflow with the target ACR image SHA |
| **RTO** | ~5 minutes |
| **Risk** | **Medium** — cold start required; new container image pulled from ACR |

### Procedure

1. Identify the last known-good image SHA from ACR or deployment logs.
2. Trigger the rollback workflow:

```bash
gh workflow run rollback-production.yml \
  -f image_sha=<TARGET_SHA> \
  -f reason="Rollback: <brief description>"
```

3. Monitor the workflow run in GitHub Actions.
4. Verify rollback (see [Verification Checklist](#7-rollback-verification-checklist) below).
5. Notify via [Communication Protocol](#8-communication-protocol).

**Reference:** `.github/workflows/rollback-production.yml` — pulls specified ACR image tag and deploys to production App Service.

---

## 5. Strategy C — Database Recovery

| | |
|---|---|
| **When** | Schema migration failure, data corruption, or accidental data loss |
| **How** | Point-in-time restore (PITR) or logical restore per the database recovery runbook |
| **RTO** | 15–60 minutes depending on database size |
| **Risk** | **High** — potential data loss within the recovery window; requires coordination |

### Procedure

1. **Stop the application** to prevent further writes against a corrupted schema.
2. Determine the recovery target timestamp (last known-good state).
3. Follow the full procedure in [`docs/runbooks/database-recovery.md`](database-recovery.md).
4. After restore, redeploy the matching application version (Strategy A or B).
5. Verify rollback (see [Verification Checklist](#7-rollback-verification-checklist) below).
6. Notify via [Communication Protocol](#8-communication-protocol).

**Reference:** [`docs/runbooks/database-recovery.md`](database-recovery.md)

---

## 6. Strategy D — Config Rollback

| | |
|---|---|
| **When** | Environment variable misconfiguration or feature flag issue |
| **How** | Revert Azure App Settings and restart the App Service |
| **RTO** | ~3 minutes |
| **Risk** | **Low** — application code unchanged |

### Procedure

1. Identify the misconfigured setting(s) in Azure Portal or via CLI.
2. Revert the setting:

```bash
az webapp config appsettings set \
  --resource-group rg-qgp-production \
  --name qgp-production \
  --settings KEY=PREVIOUS_VALUE
```

3. Restart the app service:

```bash
az webapp restart \
  --resource-group rg-qgp-production \
  --name qgp-production
```

4. Verify rollback (see [Verification Checklist](#7-rollback-verification-checklist) below).
5. Notify via [Communication Protocol](#8-communication-protocol).

For feature flag issues, see [`docs/runbooks/feature-flag-governance.md`](feature-flag-governance.md).

---

## 7. Rollback Verification Checklist

After **any** rollback strategy, verify all of the following before declaring the incident resolved:

- [ ] `/healthz` returns HTTP 200
- [ ] `/readyz` returns HTTP 200 (database connectivity confirmed)
- [ ] `/api/v1/meta/version` shows expected `build_sha`
- [ ] Critical user journey spot-check (login → dashboard → key workflow)
- [ ] Error rate returned to pre-incident baseline (check monitoring dashboard)
- [ ] No new 5xx errors in application logs
- [ ] Alerting channels show no new firing alerts

---

## 8. Communication Protocol

| Step | Action | Timing |
|------|--------|--------|
| 1 | Notify `#incidents` channel with issue summary and chosen strategy | Immediately |
| 2 | Update status page (if customer-facing impact) | Within 5 minutes |
| 3 | Post resolution update to `#incidents` with verification results | After rollback verified |
| 4 | Schedule post-incident review | Within 48 hours |
| 5 | File post-incident report per [`docs/runbooks/incident-response.md`](incident-response.md) | Within 5 business days |

---

## 9. Strategy Comparison

| Strategy | Trigger | RTO | Risk | Data Loss | Automation |
|----------|---------|-----|------|-----------|------------|
| **A — Slot Swap** | App regression, < 1 hr | ~2 min | Low | None | Semi-auto (deploy workflow auto-rollback) |
| **B — Image Pin** | App regression, > 1 hr or slot overwritten | ~5 min | Medium | None | Manual trigger via GitHub Actions |
| **C — Database** | Schema / data issue | 15–60 min | High | Possible (recovery window) | Manual (PITR + redeploy) |
| **D — Config** | Env var / feature flag | ~3 min | Low | None | Manual (Azure CLI) |

---

## 10. Related Documents

| Document | Path |
|----------|------|
| Production Deploy Workflow | [`.github/workflows/deploy-production.yml`](../../.github/workflows/deploy-production.yml) |
| Emergency Rollback Workflow | [`.github/workflows/rollback-production.yml`](../../.github/workflows/rollback-production.yml) |
| Rollback Procedure | [`docs/runbooks/rollback.md`](rollback.md) |
| Rollback Drill Log | [`docs/runbooks/rollback-drills.md`](rollback-drills.md) |
| Database Recovery | [`docs/runbooks/database-recovery.md`](database-recovery.md) |
| Incident Response | [`docs/runbooks/incident-response.md`](incident-response.md) |
| Escalation Guide | [`docs/runbooks/escalation.md`](escalation.md) |
| Feature Flag Governance | [`docs/runbooks/feature-flag-governance.md`](feature-flag-governance.md) |
| On-Call Guide | [`docs/runbooks/on-call-guide.md`](on-call-guide.md) |
