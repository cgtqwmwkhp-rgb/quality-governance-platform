# Production View UAT Runbook

**Version**: 1.0.0  
**Last Updated**: 2026-01-28  
**Owner**: Release Governance Team

---

## Overview

This runbook describes how to perform User Acceptance Testing (UAT) on the **production view** (production UI) safely, without risking production data.

### Key Safety Features

| Feature | Default | Description |
|---------|---------|-------------|
| **UAT Mode** | `READ_ONLY` in production | Blocks all write operations by default |
| **Override Headers** | Required for writes | Explicit, audited override mechanism |
| **Admin Allowlist** | Required | Only designated UAT admins can enable writes |
| **Audit Logging** | Always | All write attempts logged (no payload/PII) |

---

## Preconditions

Before starting UAT on production view:

### 1. Environment Sync Verification

Staging and production must be running the **same git SHA**.

```bash
# Check staging build_sha
curl -s https://${STAGING_URL}/api/v1/meta/version | jq '.build_sha'

# Check production build_sha
curl -s https://${PROD_URL}/api/v1/meta/version | jq '.build_sha'

# Verify they match
# Expected: both return the same SHA (e.g., "ba50a2c0694869d97cd84a2cfb48a60ec2573665")
```

### 2. Health Check

```bash
# Staging
curl -s https://${STAGING_URL}/healthz  # Should return {"status": "healthy"}
curl -s https://${STAGING_URL}/readyz   # Should return {"status": "ready"}

# Production
curl -s https://${PROD_URL}/healthz
curl -s https://${PROD_URL}/readyz
```

### 3. UAT Mode Active

Production should have `UAT_MODE=READ_ONLY` environment variable set.

---

## Read-Only UAT Flows (Safe by Default)

In read-only mode, testers can safely perform all **read operations**:

### What You CAN Do

| Action | HTTP Method | Allowed? | Example |
|--------|-------------|----------|---------|
| View incidents | GET | ✅ Yes | `GET /api/v1/incidents` |
| View incident details | GET | ✅ Yes | `GET /api/v1/incidents/{id}` |
| View audits | GET | ✅ Yes | `GET /api/v1/audits` |
| View risks | GET | ✅ Yes | `GET /api/v1/risks` |
| View compliance evidence | GET | ✅ Yes | `GET /api/v1/evidence` |
| Export reports | GET | ✅ Yes | `GET /api/v1/reports/export` |
| Search/filter data | GET | ✅ Yes | `GET /api/v1/incidents?status=open` |
| View user profile | GET | ✅ Yes | `GET /api/v1/users/me` |

### What is BLOCKED

| Action | HTTP Method | Blocked? | Response |
|--------|-------------|----------|----------|
| Create incident | POST | ❌ Blocked | HTTP 409 |
| Update incident | PUT/PATCH | ❌ Blocked | HTTP 409 |
| Delete incident | DELETE | ❌ Blocked | HTTP 409 |
| Create audit | POST | ❌ Blocked | HTTP 409 |
| Submit finding | POST | ❌ Blocked | HTTP 409 |
| Approve workflow | POST | ❌ Blocked | HTTP 409 |

### Blocked Response Format

When a write is blocked, you'll receive:

```json
{
  "error_class": "UAT_WRITE_BLOCKED",
  "detail": "UAT on production is read-only by default",
  "how_to_enable": "See docs/uat/PROD_VIEW_UAT_RUNBOOK.md for override procedure"
}
```

---

## Write-Enabled UAT Procedure (Controlled Override)

For UAT scenarios that require creating or modifying data, follow this procedure.

### Prerequisites

1. **Approval**: Obtain approval from Platform Admin or QA Lead
2. **Issue Tracking**: Create a tracking issue (e.g., GOVPLAT-XXX)
3. **UAT Admin Access**: Your user ID must be in the `UAT_ADMIN_USERS` list
4. **Time-Boxed**: Set an expiry date (recommended: max 1 day)

### Override Headers

To enable writes, include ALL of these headers:

| Header | Required | Format | Example |
|--------|----------|--------|---------|
| `X-UAT-WRITE-ENABLE` | Yes | `true` | `true` |
| `X-UAT-ISSUE-ID` | Yes | Issue key | `GOVPLAT-123` |
| `X-UAT-OWNER` | Yes | Team name | `qa-team` |
| `X-UAT-EXPIRY` | Recommended | `YYYY-MM-DD` | `2026-01-29` |

### Example: Create Test Incident

```bash
curl -X POST "https://${PROD_URL}/api/v1/incidents" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-UAT-WRITE-ENABLE: true" \
  -H "X-UAT-ISSUE-ID: GOVPLAT-456" \
  -H "X-UAT-OWNER: qa-team" \
  -H "X-UAT-EXPIRY: 2026-01-29" \
  -d '{
    "title": "UAT Test Incident - DO NOT PROCESS",
    "description": "Test incident created during UAT. Safe to delete.",
    "severity": "low",
    "category": "test"
  }'
```

### What Gets Logged

All write attempts (blocked or allowed) are logged with:

- Timestamp
- User ID (non-PII identifier)
- Endpoint path
- HTTP method
- Issue ID (if provided)
- Owner (if provided)
- Result (allowed/blocked)
- Reason (if blocked)

**NOT logged**: Request/response payloads, actual data content

---

## Test Accounts

Use these test accounts for UAT (non-PII, test-only):

| Account | Role | Purpose |
|---------|------|---------|
| `uat_admin` | Admin | Full UAT admin access |
| `uat_user` | Standard User | Regular user workflows |
| `uat_auditor` | Auditor | Audit-related testing |
| `uat_readonly` | Read-Only | View-only access testing |

> **Note**: Passwords and credentials are managed separately. Contact Platform Admin.

---

## Workflow Test Scripts

### 1. Incident Lifecycle (Read-Only)

```bash
# 1. List incidents
curl -s "https://${PROD_URL}/api/v1/incidents?limit=10" \
  -H "Authorization: Bearer ${TOKEN}" | jq '.data | length'

# 2. View specific incident
curl -s "https://${PROD_URL}/api/v1/incidents/1" \
  -H "Authorization: Bearer ${TOKEN}" | jq '.title'

# 3. View incident timeline
curl -s "https://${PROD_URL}/api/v1/incidents/1/timeline" \
  -H "Authorization: Bearer ${TOKEN}" | jq '. | length'

# Expected: All return 200 with data
```

### 2. Audit Lifecycle (Read-Only)

```bash
# 1. List audits
curl -s "https://${PROD_URL}/api/v1/audits" \
  -H "Authorization: Bearer ${TOKEN}" | jq '.data | length'

# 2. View audit template
curl -s "https://${PROD_URL}/api/v1/audit-templates" \
  -H "Authorization: Bearer ${TOKEN}" | jq '.[0].name'

# Expected: All return 200 with data
```

### 3. Verify Write Block (Expected: 409)

```bash
# Attempt to create incident WITHOUT override headers
curl -s -o /dev/null -w "%{http_code}" \
  -X POST "https://${PROD_URL}/api/v1/incidents" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"title": "Should be blocked"}'

# Expected: 409
```

### 4. Verify Write Allow (With Override)

```bash
# Attempt to create incident WITH override headers (requires UAT admin)
curl -s -X POST "https://${PROD_URL}/api/v1/incidents" \
  -H "Authorization: Bearer ${UAT_ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-UAT-WRITE-ENABLE: true" \
  -H "X-UAT-ISSUE-ID: GOVPLAT-UAT-001" \
  -H "X-UAT-OWNER: qa-team" \
  -d '{"title": "UAT Test", "severity": "low"}' | jq '.id'

# Expected: 201 with new incident ID
```

---

## Capturing Defects

When reporting bugs found during UAT, include:

1. **Build SHA**: From `/api/v1/meta/version`
2. **Environment**: Staging or Production
3. **Endpoint**: Full URL path
4. **Expected vs Actual**: Behavior difference
5. **Steps to Reproduce**: Numbered list
6. **Evidence**: Screenshot or response body (redact any sensitive data)

### Bug Report Template

```markdown
## Bug Report

**Build SHA**: `ba50a2c0694869d97cd84a2cfb48a60ec2573665`
**Environment**: Production View
**UAT Issue**: GOVPLAT-456

### Summary
[Brief description]

### Steps to Reproduce
1. Navigate to...
2. Click...
3. Observe...

### Expected Behavior
[What should happen]

### Actual Behavior
[What actually happened]

### Evidence
[Screenshot or sanitized response]
```

---

## Rollback Procedure

If issues are found that require rollback:

1. **Do NOT weaken CI gates**
2. Revert the problematic commit on main:
   ```bash
   git revert <commit-sha>
   git push origin main
   ```
3. Redeploy both staging and production
4. Verify both environments return the reverted SHA

---

## FAQ

### Q: Can I accidentally modify production data?
**A**: No. In READ_ONLY mode, all write attempts are blocked with HTTP 409.

### Q: What if I need to test data modification?
**A**: Request UAT admin access and use override headers with a tracked issue.

### Q: Are my actions logged?
**A**: Yes, all write attempts are logged with metadata (no payload/PII).

### Q: What happens if my override expires?
**A**: Writes are blocked with a message indicating the expiry has passed.

### Q: Can I run UAT on staging instead?
**A**: Yes, staging has `UAT_MODE=READ_WRITE` by default for unrestricted testing.

---

## Support

- **Slack**: #platform-support
- **Issues**: Create in GOVPLAT project
- **Escalation**: Platform Admin on-call
