# Runbook: Escalation Procedures

**Owner**: Platform Engineering
**Last Updated**: 2026-03-07
**Review Cycle**: Quarterly

---

## 1. Escalation Matrix

| Severity | Initial Responder | Escalation (30 min) | Executive (60 min) |
|----------|------------------|---------------------|-------------------|
| **SEV-1** | On-call engineer | Engineering Lead | CTO |
| **SEV-2** | On-call engineer | Engineering Lead | — |
| **SEV-3** | Assigned engineer | — | — |
| **SEV-4** | Backlog triage | — | — |

## 2. When to Escalate

Escalate immediately (do not wait for time threshold) if:
- Data breach suspected or confirmed
- Multiple tenants affected simultaneously
- Authentication system completely down
- Regulatory compliance impact (GDPR data leak, RIDDOR reporting failure)
- Customer-facing commitment at risk (SLA breach imminent)

Escalate at time threshold if:
- Issue not resolved within severity response time
- Root cause not identified within 30 minutes of investigation
- Fix requires access or permissions you don't have
- Impact is spreading to additional systems/tenants

## 3. How to Escalate

### Step 1: Document Current State
Before escalating, prepare a brief:
- What is happening (symptoms)
- When it started
- What has been tried
- Current impact (users affected, error rate)
- Best theory on root cause

### Step 2: Contact Escalation Target
1. **Primary**: Message in #incidents channel, tagging the escalation target
2. **Urgent**: Direct message / phone call
3. **After hours**: Use on-call rotation contact (TBD: PagerDuty / OpsGenie)

### Step 3: Handoff
- Share diagnostic data gathered so far
- Share access to monitoring dashboards
- Remain available for questions from the escalation recipient
- Do not disengage until handoff is acknowledged

## 4. External Escalation

### Azure Support
- **When**: Azure infrastructure issues (database, App Service, Blob Storage)
- **How**: Azure Portal → Support + Troubleshooting → New support request
- **Severity**: Match to Azure severity (A = Critical, B = Moderate, C = Minimal)

### Third-Party Integrations
| Integration | Escalation Path |
|------------|-----------------|
| Azure AD / Entra ID | Azure Support (Identity) |
| Google Gemini AI | Google Cloud Support |
| SendGrid/SMTP | Email provider support |

## 5. Communication Templates

### Internal (SEV-1/SEV-2)
```
INCIDENT: [Brief description]
SEVERITY: SEV-[1/2]
IMPACT: [Who/what is affected]
STATUS: [Investigating/Identified/Resolving/Resolved]
NEXT UPDATE: [Time]
COMMANDER: [Name]
```

### Stakeholder Update
```
We are currently experiencing [issue description].
Impact: [User-facing impact in plain language]
We are actively working on resolution. Next update at [time].
```

## 6. Post-Escalation

- All SEV-1 and SEV-2 incidents require a post-mortem within 48 hours
- Post-mortem must include: timeline, root cause, impact metrics, action items
- Action items must be tracked as tickets and reviewed in next retrospective
- Update this runbook and `incident-response.md` with any process improvements
