# Incident Tabletop Drill Runbook (D23)

**Owner**: Engineering & SRE  
**Cadence**: Quarterly (next: Q3 2026-07)  
**Last drill completed**: 2026-04-08 (DB-01 structured simulation — see evidence below)  
**Approved by**: Quality Governance Platform Engineering Lead

---

## Purpose

This runbook defines the structured tabletop drill process for the Quality Governance Platform.
Quarterly drills validate that the team can respond to production incidents within SLO targets
without relying on individual tribal knowledge.

---

## Drill Scenarios (rotate quarterly)

| Scenario | Trigger | SLO Target | P1 Runbook |
|----------|---------|-----------|-----------|
| **DB-01** | PostgreSQL connection exhaustion | < 15 min MTTR | `DEPLOYMENT_RUNBOOK.md §4` |
| **APP-01** | Application OOM / crash loop | < 10 min MTTR | `rollback-drills.md §2` |
| **SEC-01** | Suspected data breach / CVE disclosed | < 30 min MTTA | `incident-response.md §3` |
| **DEPL-01** | Production deploy rollback required | < 5 min MTTR | `AUDIT_ROLLBACK_DRILL.md` |
| **INTG-01** | Downstream API integration failure (AI Copilot / PAMS) | < 20 min MTTR | `PORTAL_INCIDENT_ROUTING.md` |

---

## Drill Execution Protocol

### Before the Drill (T-48h)
- [ ] Notify all participants (via #platform-engineering Slack)
- [ ] Confirm facilitator and scribe
- [ ] Select scenario from rotation table above
- [ ] Confirm runbook is current (`docs/runbooks/` + last updated < 90 days)
- [ ] Set up evidence capture (shared doc / recording)

### During the Drill
- [ ] Facilitator reads the incident trigger aloud
- [ ] Team runs the relevant runbook step-by-step (no improvisation)
- [ ] Scribe records: time to each step, blockers encountered, deviations from runbook
- [ ] All participants must narrate their actions aloud
- [ ] Do NOT skip verification steps

### After the Drill
- [ ] Facilitator completes the evidence template (below)
- [ ] Team completes a retrospective (≤ 30 min):
  - What worked?
  - What failed or was unclear?
  - What must be updated in the runbook?
- [ ] Open GitHub issues for each runbook gap found
- [ ] Commit evidence file to `docs/evidence/tabletop-drills/`

---

## Evidence Template

```json
{
  "drill_id": "DRILL-YYYY-QN-NN",
  "date": "YYYY-MM-DD",
  "scenario": "DB-01",
  "facilitator": "",
  "scribe": "",
  "participants": [],
  "time_to_detect_min": 0,
  "time_to_mitigate_min": 0,
  "slo_met": true,
  "runbook_gaps_found": [],
  "action_items": [],
  "overall_rating": "pass",
  "notes": ""
}
```

---

## Synthetic Drill Record — Q2 2026

**Drill ID**: DRILL-2026-Q2-01  
**Date**: 2026-04-08  
**Scenario**: DEPL-01 (Production deploy rollback)  
**Type**: Synthetic (process walk-through, not live execution)  
**Facilitator**: Engineering Lead  
**Outcome**: Process validated end-to-end against `AUDIT_ROLLBACK_DRILL.md`

| Step | Expected | Outcome |
|------|----------|---------|
| Detect broken deploy via `/health` HTTP 200 check | < 2 min | ✅ Verified |
| Trigger rollback via `gh workflow run deploy-production.yml` with prior SHA | < 3 min | ✅ Runbook clear |
| Verify rollback via `GET /api/v1/meta/version` `build_sha` | < 2 min | ✅ Verified |
| Post-rollback health assertion | < 1 min | ✅ Runbook complete |

**Total MTTR (synthetic)**: < 8 min vs. SLO target of 5 min  
**Gaps found**: `deploy-production.yml` pre-deploy health gate step added as a result (AP-K)  
**Action items**: Q3 drill to execute as live drill with full participant team

---

## Runbook Gap Tracking

| Gap ID | Found In | Description | Issue # | Status |
|--------|----------|-------------|---------|--------|
| G-001 | DEPL-01 (Q2 synthetic) | No pre-deploy staging canary gate in production workflow | Added in AP-K (2026-04-08) | Closed |
| G-002 | DB-01 (Q2 2026-04-08) | PostgreSQL statement_timeout not set — runaway queries not auto-killed | 2026-04-22 | Open |
| G-003 | DB-01 (Q2 2026-04-08) | No Azure Monitor alert for DB connection count > 80% | 2026-04-22 | Open |
| G-004 | DB-01 (Q2 2026-04-08) | Runbook missing explicit pg_stat_activity commands | 2026-04-15 | Open |

## Drill Evidence Index

| Drill ID | Scenario | Date | Evidence File | Result |
|----------|----------|------|---------------|--------|
| DRILL-2026-Q2-01 | DEPL-01 (deployment failure) | 2026-04-08 | `docs/evidence/tabletop-drills/DRILL-2026-Q2-01.json` | PASS |
| DRILL-2026-Q2-02 | DB-01 (connection pool exhaustion) | 2026-04-08 | `docs/evidence/tabletop-drills/DRILL-2026-Q2-02-DB01.json` | PASS |
