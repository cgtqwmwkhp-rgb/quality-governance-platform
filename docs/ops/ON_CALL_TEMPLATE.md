# On-Call Rotation Template

**Quality Governance Platform (QGP)**  
**Version:** 1.0  
**Last Updated:** 2026-03-03

---

## 1. On-Call Contacts

### Primary On-Call (L1)

| Role | Name | Phone | Email |
|------|------|-------|-------|
| Primary | [Primary On-Call Name] | +44 XXX XXXX XXXX | primary.oncall@example.com |
| Secondary | [Secondary On-Call Name] | +44 XXX XXXX XXXX | secondary.oncall@example.com |

### Secondary On-Call (L2)

| Role | Name | Phone | Email |
|------|------|-------|-------|
| L2 Engineer | [L2 Engineer Name] | +44 XXX XXXX XXXX | l2.engineer@example.com |
| L2 Backup | [L2 Backup Name] | +44 XXX XXXX XXXX | l2.backup@example.com |

### Tertiary / Escalation (L3)

| Role | Name | Phone | Email |
|------|------|-------|-------|
| Platform Lead | [Platform Lead Name] | +44 XXX XXXX XXXX | platform.lead@example.com |
| Engineering Manager | [Engineering Manager Name] | +44 XXX XXXX XXXX | eng.manager@example.com |

---

## 2. Escalation Matrix

| Level | Role | Response Time | Escalation Trigger |
|-------|------|---------------|-------------------|
| **L1** | Primary On-Call | Immediate (within 15 min) | Initial alert, user-reported incident |
| **L2** | Senior Engineer | 30 minutes | L1 unable to resolve, SEV1/SEV2, complex debugging |
| **L3** | Platform Lead / Manager | 60 minutes | SEV1 unresolved, architectural decision, vendor escalation |

### Time Thresholds

| Condition | Action |
|-----------|--------|
| L1 no response in **15 min** | Page L2 |
| L1 working > **30 min** on SEV1 | Escalate to L2 |
| L2 no response in **30 min** | Page L3 |
| L2 working > **60 min** on SEV1 | Escalate to L3 |
| SEV1 unresolved > **2 hours** | Executive notification |

---

## 3. Shift Schedule

### Weekly Rotation Pattern

| Week | Primary (L1) | Secondary (L1) | L2 Support |
|------|--------------|----------------|------------|
| Week 1 | [Engineer A] | [Engineer B] | [Engineer C] |
| Week 2 | [Engineer B] | [Engineer C] | [Engineer A] |
| Week 3 | [Engineer C] | [Engineer A] | [Engineer B] |
| Week 4 | [Engineer A] | [Engineer B] | [Engineer C] |

### Shift Times

- **Standard:** Monday 09:00 UTC → Next Monday 09:00 UTC
- **Handoff:** Every Monday 09:00 UTC
- **Overlap:** 30-minute overlap for handoff call

### Holiday / Leave Coverage

- Notify rotation at least **7 days** before leave
- Swap with another engineer or use backup list
- Update PagerDuty/OpsGenie schedule accordingly

---

## 4. Handoff Checklist

### End of Shift (Outgoing)

- [ ] Document any open incidents and current status
- [ ] Update incident tickets with latest notes
- [ ] List any known issues or workarounds
- [ ] Note any pending deployments or maintenance windows
- [ ] Share access to any temporary credentials or debug sessions
- [ ] Confirm handoff call completed with incoming engineer

### Start of Shift (Incoming)

- [ ] Review open incidents and their status
- [ ] Check recent deployments and release notes
- [ ] Verify alerting channels (Slack, PagerDuty, etc.) are working
- [ ] Confirm access to runbooks and escalation contacts
- [ ] Test on-call phone/device can receive pages
- [ ] Acknowledge handoff in rotation tool

### Handoff Call Agenda (15 min)

1. Open incidents summary
2. Recent changes (deploys, config)
3. Known issues / workarounds
4. Escalation path reminder
5. Q&A

---

## 5. Tools & Access

| Tool | Purpose |
|------|---------|
| PagerDuty / OpsGenie | Alert routing, escalation |
| Slack #incidents | Real-time coordination |
| Azure Portal | Infrastructure access |
| Runbooks | docs/ops/INCIDENT_RESPONSE_RUNBOOK.md |

---

*Replace placeholder names and phone numbers before use. Update this template when rotation changes.*
