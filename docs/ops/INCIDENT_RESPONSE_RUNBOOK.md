# Incident Response Runbook

**Quality Governance Platform (QGP)**  
**Version:** 1.0  
**Last Updated:** 2026-03-03

---

## 1. Severity Classification

| Severity | Definition | Response Time (Acknowledge) | Resolution Target |
|----------|-------------|----------------------------|-------------------|
| **SEV1** | Complete outage; core functionality unavailable (portal, API, auth) | 15 minutes | 4 hours |
| **SEV2** | Major degradation; significant feature broken; workaround exists | 30 minutes | 8 hours |
| **SEV3** | Minor degradation; non-critical feature impaired | 2 hours | 24 hours |
| **SEV4** | Low impact; cosmetic or edge-case issue | 1 business day | 1 week |

### Severity Decision Guide

- **SEV1:** Portal down, login broken, report submission fails for all users
- **SEV2:** Single report type broken, admin dashboard slow, export failing
- **SEV3:** Analytics delayed, non-critical UI glitch, partial degradation
- **SEV4:** Typos, minor UX issues, low-traffic feature bug

---

## 2. Communication Templates

### Initial Acknowledgment (Internal)

```
[INCIDENT] SEV{X}: {Brief description}
Status: Investigating
Started: {ISO timestamp}
Incident Lead: {Name}
Channel: #incidents
```

### Stakeholder Update (During Incident)

```
Incident Update - {Date} {Time}

Severity: SEV{X}
Status: {Investigating | Identified | Fixing | Resolved}
Impact: {Description of user impact}

Current actions:
- {Action 1}
- {Action 2}

Next update: {Time} or when status changes
```

### Resolution Notice

```
[RESOLVED] SEV{X}: {Brief description}
Resolved: {ISO timestamp}
Duration: {X hours Y minutes}
Root cause: {One-line summary}
Post-incident review: {Link to PIR}
```

### Customer-Facing (If Required)

```
We are aware of an issue affecting {service/feature}. Our team is actively working on a resolution. We will provide an update within {timeframe}. We apologize for any inconvenience.
```

---

## 3. Rollback Decision Tree

```
                    ┌─────────────────────┐
                    │  Incident Detected  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Recent deploy (<24h)?│
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │ Yes            │                │ No
              ▼                │                ▼
    ┌─────────────────┐        │      ┌─────────────────┐
    │ Can we identify │        │      │ Proceed with    │
    │ deploy as cause?│        │      │ standard        │
    └────────┬────────┘        │      │ troubleshooting │
             │                │      └─────────────────┘
    ┌────────┴────────┐        │
    │ Yes      │ No   │        │
    ▼          ▼      │        │
┌───────┐  ┌───────┐  │        │
│ROLLBACK│  │ Consider│ │        │
│        │  │ rollback│ │        │
│ Execute│  │ if high │ │        │
│ rollback│ │ severity│ │        │
└───────┘  └───────┘  │        │
```

### Rollback Criteria

| Condition | Action |
|-----------|--------|
| Deploy < 24h AND clear correlation | **Execute rollback** |
| SEV1 AND deploy < 48h | **Execute rollback** (investigate after) |
| SEV2 AND no quick fix | **Consider rollback** |
| Data corruption risk | **Do NOT rollback** — contain and fix forward |
| Rollback would cause more damage | **Do NOT rollback** — fix forward |

### Rollback Commands (Reference)

```bash
# Azure Container Apps - revert to previous revision
az containerapp revision list --name qgp-staging --resource-group rg-qgp-staging -o table
az containerapp revision activate --name qgp-staging --resource-group rg-qgp-staging --revision <PREVIOUS_REVISION>
```

---

## 4. Post-Incident Review Checklist

### Within 24 Hours of Resolution

- [ ] Create PIR document (template below)
- [ ] Schedule blameless PIR meeting (within 5 business days)
- [ ] Notify stakeholders that PIR is scheduled

### PIR Document Template

```markdown
# Post-Incident Review: [Incident ID]

## Summary
- **Severity:** SEV{X}
- **Start:** {timestamp}
- **End:** {timestamp}
- **Duration:** {X}h {Y}m
- **Incident Lead:** {name}

## Timeline
| Time | Event |
|------|-------|
| ... | ... |

## Root Cause
{Brief description}

## Impact
- Users affected: {estimate}
- Features impacted: {list}

## What Went Well
- ...

## What Could Be Improved
- ...

## Action Items
| # | Action | Owner | Due |
|---|--------|-------|-----|
| 1 | ... | ... | ... |

## Lessons Learned
...
```

### PIR Meeting Agenda (60 min)

1. **Timeline review** (15 min)
2. **Root cause analysis** (15 min)
3. **What went well / what didn't** (10 min)
4. **Action items** (15 min)
5. **Documentation updates** (5 min)

### Follow-Up

- [ ] Create tickets for all action items
- [ ] Update runbooks if new procedures discovered
- [ ] Add monitoring/alerting if gap identified
- [ ] Share PIR summary with stakeholders

---

## 5. Quick Reference

| Resource | Location |
|----------|----------|
| On-Call Contacts | docs/ops/ON_CALL_TEMPLATE.md |
| Scaling Playbook | docs/ops/SCALING_PLAYBOOK.md |
| Health Checks | `/healthz`, `/readyz` |
| Azure Portal | Portal → Resource Group → Container App |
