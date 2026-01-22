# Security Monitoring & Alerting Runbook

## Overview

This runbook documents the security monitoring configuration for the Quality Governance Platform.
It covers alerting for security-relevant events including authentication failures, 500 errors,
and rate limiting triggers.

## Monitoring Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Application   │────▶│  Azure Monitor  │────▶│    Alerts       │
│   (FastAPI)     │     │  Log Analytics  │     │  (Action Groups)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
  JSON Structured         KQL Queries            Teams/Slack/
     Logging           (Alert Rules)           PagerDuty/Email
```

## Alert Categories

### 1. Authentication Failures (High Priority)

**Trigger:** Excessive 401 responses from a single IP

**KQL Query:**
```kql
AppRequests
| where TimeGenerated > ago(5m)
| where ResultCode == 401
| summarize Count = count() by ClientIP
| where Count > 50
```

**Threshold:** > 50 failed auth attempts in 5 minutes from single IP

**Severity:** High (Sev 2)

**Response Actions:**
1. Check if IP is legitimate (e.g., load balancer, internal service)
2. If suspicious, consider temporary IP block via Azure WAF
3. Review user accounts for potential brute force targets
4. Escalate to security team if attack pattern detected

---

### 2. Rate Limit Triggers (Medium Priority)

**Trigger:** 429 responses indicating rate limiting in effect

**KQL Query:**
```kql
AppRequests
| where TimeGenerated > ago(15m)
| where ResultCode == 429
| summarize Count = count() by ClientIP, Name
| where Count > 10
```

**Threshold:** > 10 rate limit hits in 15 minutes

**Severity:** Medium (Sev 3)

**Response Actions:**
1. Identify if legitimate high-volume user or potential abuse
2. If legitimate, consider rate limit adjustment
3. If abuse, add to WAF block list
4. Monitor for continued patterns

---

### 3. Server Errors (High Priority)

**Trigger:** 500 Internal Server Errors

**KQL Query:**
```kql
AppRequests
| where TimeGenerated > ago(5m)
| where ResultCode >= 500
| summarize Count = count() by Name, ClientIP
| where Count > 5
```

**Threshold:** > 5 server errors in 5 minutes

**Severity:** High (Sev 2)

**Response Actions:**
1. Check application logs for stack traces
2. Identify affected endpoint(s)
3. Check database connectivity
4. Roll back if related to recent deployment
5. Escalate to on-call engineer

---

### 4. Email Filter Abuse Detection (Critical)

**Trigger:** Suspicious patterns on email-filtered endpoints (Stage 2 CVE follow-up)

**KQL Query:**
```kql
AppRequests
| where TimeGenerated > ago(10m)
| where Name contains "incidents" or Name contains "complaints" or Name contains "rtas"
| where RequestUrl contains "email="
| summarize Count = count() by ClientIP
| where Count > 20
```

**Threshold:** > 20 email-filtered requests in 10 minutes from single IP

**Severity:** Critical (Sev 1)

**Response Actions:**
1. IMMEDIATE: Verify 401s are being returned (security fix in place)
2. Block IP via Azure WAF
3. Check if any data was exfiltrated (review successful responses)
4. Generate security incident report
5. Notify security team

---

### 5. Health Check Failures (Critical)

**Trigger:** /healthz or /readyz returning non-200

**KQL Query:**
```kql
AppRequests
| where TimeGenerated > ago(2m)
| where Name == "/healthz" or Name == "/readyz"
| where ResultCode != 200
| summarize Count = count()
| where Count > 3
```

**Threshold:** > 3 failed health checks in 2 minutes

**Severity:** Critical (Sev 1)

**Response Actions:**
1. Check Azure Web App status
2. Verify database connectivity
3. Check recent deployments
4. Initiate rollback if needed
5. Escalate to on-call engineer

---

## Azure Monitor Configuration

### Log Analytics Workspace

Ensure Application Insights is configured to send logs to Log Analytics:

```json
{
  "workspaceResourceId": "/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.OperationalInsights/workspaces/{workspace}"
}
```

### Alert Rules (ARM Template)

```json
{
  "type": "microsoft.insights/scheduledqueryrules",
  "apiVersion": "2022-06-15",
  "name": "auth-failure-alert",
  "location": "[resourceGroup().location]",
  "properties": {
    "displayName": "Authentication Failure Spike",
    "severity": 2,
    "enabled": true,
    "evaluationFrequency": "PT5M",
    "windowSize": "PT5M",
    "scopes": ["[resourceId('microsoft.insights/components', 'app-insights-qgp')]"],
    "criteria": {
      "allOf": [{
        "query": "AppRequests | where ResultCode == 401 | summarize Count = count() by ClientIP | where Count > 50",
        "timeAggregation": "Count",
        "operator": "GreaterThan",
        "threshold": 0
      }]
    },
    "actions": {
      "actionGroups": ["[resourceId('microsoft.insights/actionGroups', 'security-team')]"]
    }
  }
}
```

### Action Groups

| Group Name | Type | Recipients |
|------------|------|------------|
| security-team | Email/Teams | security@company.com, #security-alerts |
| ops-team | Email/PagerDuty | ops@company.com, PagerDuty service |
| on-call | PagerDuty | On-call rotation |

---

## Structured Logging

The application uses JSON structured logging for observability:

```python
# Example log entry
{
  "timestamp": "2026-01-22T15:30:00Z",
  "level": "INFO",
  "message": "Request completed",
  "request_id": "abc123",
  "method": "GET",
  "path": "/api/v1/incidents/",
  "status_code": 401,
  "user_id": null,
  "client_ip": "1.2.3.4",
  "duration_ms": 15
}
```

### Security-Relevant Log Fields

| Field | Description | Use |
|-------|-------------|-----|
| `status_code` | HTTP response code | Filter for 401, 403, 500 |
| `user_id` | Authenticated user ID | Track user activity |
| `client_ip` | Client IP address | Identify abuse sources |
| `request_id` | Unique request ID | Trace requests |
| `path` | Request path | Identify targeted endpoints |

---

## Audit Events

Security-relevant audit events are logged via `record_audit_event()`:

| Event Type | Description | Priority |
|------------|-------------|----------|
| `incident.list_filtered` | Email filter used on incidents | Monitor |
| `complaint.list_filtered` | Email filter used on complaints | Monitor |
| `rta.list_filtered` | Email filter used on RTAs | Monitor |
| `user.login_failed` | Failed login attempt | Alert on volume |
| `user.login_success` | Successful login | Audit trail |
| `*.deleted` | Any deletion | Audit trail |

---

## Escalation Matrix

| Severity | Response Time | Escalation |
|----------|---------------|------------|
| Sev 1 (Critical) | 15 minutes | Immediate page to on-call |
| Sev 2 (High) | 30 minutes | Page on-call if unacknowledged |
| Sev 3 (Medium) | 4 hours | Email notification |
| Sev 4 (Low) | 24 hours | Ticket creation |

---

## Post-Incident Actions

After any security alert:

1. **Document** the incident in the security log
2. **Analyze** root cause
3. **Update** alerting thresholds if too noisy or too quiet
4. **Patch** if vulnerability identified
5. **Report** to stakeholders if data affected

---

## Related Documents

- [SECURITY_STAGE1_E2E_VERIFICATION.md](../evidence/SECURITY_STAGE1_E2E_VERIFICATION.md) - Initial vulnerability discovery
- [SECURITY_STAGE2_IMPLEMENTATION_PLAN.md](../evidence/SECURITY_STAGE2_IMPLEMENTATION_PLAN.md) - Azure AD JWT validation plan
- [ADR-0003: Readiness Probe](../adr/ADR-0003-readiness-probe.md) - Health check design
