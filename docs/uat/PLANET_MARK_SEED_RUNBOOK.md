# Planet Mark Initial Data Seed Runbook

**Version**: 1.0.0  
**Last Updated**: 2026-01-30  
**Owner**: Release Governance Team

---

## Overview

This runbook describes how to seed initial data for the Planet Mark carbon management module in production. The module requires at least one `CarbonReportingYear` record to display the dashboard instead of the `SetupRequiredPanel`.

## Diagnosis

If the Planet Mark dashboard shows `SetupRequiredPanel` with:
- `message`: "No carbon reporting years configured"
- `next_action`: "Create a reporting year via POST /api/v1/planet-mark/years"

This indicates the database schema exists (migrations applied) but no data has been seeded.

### Verify Schema Status

```bash
# Check /years endpoint - should return 200 with empty list if schema exists
curl -s "https://${PROD_URL}/api/v1/planet-mark/years" \
  -H "Authorization: Bearer ${TOKEN}" | jq '.'

# Expected (schema exists, no data):
# {"total": 0, "years": []}

# If SETUP_REQUIRED with "migrations may need to be applied" - run alembic upgrade first
```

---

## Prerequisites

1. **Admin Access**: You must be in the `UAT_ADMIN_USERS` list
2. **Issue Tracking**: Create tracking issue (e.g., `INC-2026-01-30-PLANETMARK-SEED`)
3. **Approval**: Obtain approval from Platform Admin
4. **Token**: Valid admin bearer token

---

## Seed Procedure

### Step 1: Create First Carbon Reporting Year

Use the audited override headers to create the initial reporting year.

```bash
# Set environment variables
export PROD_URL="qgp-api-prod.azurewebsites.net"
export TOKEN="your-admin-bearer-token"
export ISSUE_ID="INC-2026-01-30-PLANETMARK-SEED"
export OWNER="release-governance"
export EXPIRY="2026-01-31"  # 24-hour window

# Create first reporting year
curl -X POST "https://${PROD_URL}/api/v1/planet-mark/years" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-UAT-WRITE-ENABLE: true" \
  -H "X-UAT-ISSUE-ID: ${ISSUE_ID}" \
  -H "X-UAT-OWNER: ${OWNER}" \
  -H "X-UAT-EXPIRY: ${EXPIRY}" \
  -d '{
    "year_label": "Year 1",
    "year_number": 1,
    "period_start": "2025-01-01T00:00:00Z",
    "period_end": "2025-12-31T23:59:59Z",
    "average_fte": 25.0,
    "organization_name": "Plantexpand Limited",
    "sites_included": ["HQ"],
    "is_baseline_year": true,
    "reduction_target_percent": 5.0
  }'
```

**Expected Response (201 Created)**:
```json
{
  "id": 1,
  "year_label": "Year 1",
  "message": "Reporting year created"
}
```

### Step 2: Verify Dashboard

```bash
# Check dashboard - should now return 200 with real data
curl -s "https://${PROD_URL}/api/v1/planet-mark/dashboard" \
  -H "Authorization: Bearer ${TOKEN}" | jq 'keys'

# Expected: ["actions", "certification", "current_year", "data_quality", ...]
# NOT: {"error_class": "SETUP_REQUIRED", ...}
```

### Step 3: Verify UI

1. Navigate to Planet Mark page in production UI
2. Confirm `SetupRequiredPanel` no longer displays
3. Confirm dashboard shows "Year 1" data with default values

---

## Idempotency

If a year already exists, do NOT create duplicates. Verify first:

```bash
curl -s "https://${PROD_URL}/api/v1/planet-mark/years" \
  -H "Authorization: Bearer ${TOKEN}" | jq '.total'

# If > 0, years already exist - do not seed again
```

---

## Rollback

If seed data needs to be removed:

1. Note: Direct DELETE is blocked by UAT safety mode
2. Contact Platform Admin for database-level cleanup
3. Alternatively, mark the year as inactive (if supported)

---

## Audit Trail

All seed operations are logged with:
- Timestamp
- User ID
- Issue ID (`X-UAT-ISSUE-ID`)
- Owner (`X-UAT-OWNER`)
- Endpoint and method
- Result (success/blocked)

---

## Related Documentation

- [PROD_VIEW_UAT_RUNBOOK.md](./PROD_VIEW_UAT_RUNBOOK.md) - General UAT procedures
- [Planet Mark API Routes](/src/api/routes/planet_mark.py) - Full API reference
