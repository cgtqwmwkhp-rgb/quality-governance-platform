# UAT Test Script - Quality Governance Platform

**Version**: 1.0.0
**Date**: 2026-01-28
**Environment**: Staging Only

---

## Overview

This document provides step-by-step test scripts for User Acceptance Testing (UAT) of the Quality Governance Platform. Each test case includes preconditions, actions, and expected results.

**Important**: All tests use synthetic test data with no PII. Do not enter real personal information.

---

## Prerequisites

### Environment Setup

1. **Environment Check**
   - Confirm you are testing on STAGING (not production)
   - URL should be: `https://staging.governance.example.com` (or local dev)
   - Look for "STAGING" indicator in the UI

2. **UAT Data Reset**
   ```bash
   # Run before starting UAT session
   export APP_ENV=staging
   export UAT_ENABLED=true
   python scripts/uat/reset_uat.py --force
   ```

3. **Verify Reset**
   - Confirm seed manifest generated
   - Note the manifest path for reference

### Test Accounts

| Role | Username | Password | Capabilities |
|------|----------|----------|--------------|
| Admin | uat_admin | UatTestPass123! | Full access, all CRUD operations |
| User | uat_user | UatTestPass123! | Create incidents, view dashboards |
| Auditor | uat_auditor | UatTestPass123! | Create/complete audits |
| Readonly | uat_readonly | UatTestPass123! | View only, no create/edit |

---

## Test Suite 1: Incident Lifecycle

### TC-INC-001: Create Incident

**Preconditions**:
- Logged in as `uat_user`
- UAT seed data loaded

**Steps**:
1. Navigate to Incidents → New Incident
2. Enter:
   - Title: "UAT Test Incident - [Your Initials]"
   - Description: "Created during UAT testing on [date]"
   - Severity: Medium
3. Click "Submit"

**Expected Results**:
- [ ] Success message displayed
- [ ] Incident assigned reference number (INC-XXXXX)
- [ ] Status is "Open"
- [ ] Created timestamp is current
- [ ] Incident appears in incident list

**Fields to Verify**:
- Reference Number format
- Status indicator color (yellow for Open)
- Creator shown as "uat_user"

---

### TC-INC-002: Update Incident Status

**Preconditions**:
- Logged in as `uat_admin`
- Open incident exists (INC-UAT-001)

**Steps**:
1. Navigate to Incidents
2. Click on INC-UAT-001
3. Click "Assign to Me"
4. Change Status dropdown to "In Progress"
5. Click "Save"

**Expected Results**:
- [ ] Status updated to "In Progress"
- [ ] Assigned To shows "uat_admin"
- [ ] Updated timestamp reflects current time
- [ ] Audit log shows status change

**Fields to Verify**:
- Status indicator color (blue for In Progress)
- Assignment field
- Last Modified date

---

### TC-INC-003: Close Incident

**Preconditions**:
- Logged in as `uat_admin`
- In-progress incident exists (INC-UAT-002)

**Steps**:
1. Navigate to Incidents
2. Click on INC-UAT-002
3. Change Status to "Closed"
4. Enter Resolution: "Issue resolved during UAT"
5. Click "Save"

**Expected Results**:
- [ ] Status updated to "Closed"
- [ ] Resolution field is populated
- [ ] Incident moves to closed list
- [ ] Cannot be edited (read-only)

**Fields to Verify**:
- Status indicator color (green for Closed)
- Resolution text
- Closed date

---

### TC-INC-004: Verify Incident in Admin View

**Preconditions**:
- Logged in as `uat_admin`
- Closed incident exists (INC-UAT-003)

**Steps**:
1. Navigate to Admin → Incident Dashboard
2. Filter by Status = "Closed"
3. Locate INC-UAT-003

**Expected Results**:
- [ ] Closed incident visible in filtered list
- [ ] All metadata displayed correctly
- [ ] Can click to view details
- [ ] Export to CSV includes this incident

**Fields to Verify**:
- Dashboard statistics updated
- Filter working correctly
- Sort order consistent

---

### TC-INC-005: Role Restriction - Readonly Cannot Create

**Preconditions**:
- Logged in as `uat_readonly`

**Steps**:
1. Navigate to Incidents
2. Attempt to click "New Incident"

**Expected Results**:
- [ ] "New Incident" button is disabled/hidden
- [ ] OR clicking shows "Permission Denied" message
- [ ] No incident created

---

## Test Suite 2: Audit Lifecycle

### TC-AUD-001: List Audit Templates

**Preconditions**:
- Logged in as `uat_admin`
- UAT seed data loaded

**Steps**:
1. Navigate to Audits → Templates
2. Review the list

**Expected Results**:
- [ ] At least 3 templates visible:
  - Annual Compliance Review
  - Security Assessment
  - Process Audit
- [ ] Each template shows name and category

**Fields to Verify**:
- Template names
- Category badges
- Template descriptions visible on hover/click

---

### TC-AUD-002: Schedule Audit from Template

**Preconditions**:
- Logged in as `uat_auditor`
- Templates available

**Steps**:
1. Navigate to Audits → Templates
2. Click "Schedule" on "Annual Compliance Review"
3. Enter:
   - Title: "Q1 2026 Compliance Audit - UAT"
   - Scheduled Date: [Date 2 weeks from today]
4. Click "Schedule Audit"

**Expected Results**:
- [ ] Audit created with reference number (AUD-XXXXX)
- [ ] Status is "Scheduled"
- [ ] Scheduled date matches entry
- [ ] Auditor assigned automatically

**Fields to Verify**:
- Reference number format
- Template linkage visible
- Auditor assignment

---

### TC-AUD-003: Start and Complete Audit

**Preconditions**:
- Logged in as `uat_auditor`
- Scheduled audit exists (AUD-UAT-001)

**Steps**:
1. Navigate to Audits → My Audits
2. Click on AUD-UAT-001
3. Click "Start Audit"
4. (Simulate completing audit activities)
5. Enter Findings: "No issues identified during UAT audit"
6. Click "Complete Audit"

**Expected Results**:
- [ ] Status progresses: Scheduled → In Progress → Completed
- [ ] Findings are saved
- [ ] Completed Date is set
- [ ] Cannot be modified after completion

**Fields to Verify**:
- Status transitions
- Findings text
- Completion timestamp

---

### TC-AUD-004: View Audit in Report View

**Preconditions**:
- Logged in as `uat_admin`
- Completed audit exists (AUD-UAT-003)

**Steps**:
1. Navigate to Reports → Audit Reports
2. Filter by Status = "Completed"
3. Locate AUD-UAT-003

**Expected Results**:
- [ ] Completed audit visible in report
- [ ] Report shows findings summary
- [ ] Can export report to PDF

**Fields to Verify**:
- Audit details correct
- Findings displayed
- Auditor name shown

---

## Test Suite 3: Risk Workflow

### TC-RISK-001: Create Risk

**Preconditions**:
- Logged in as `uat_admin`
- UAT seed data loaded

**Steps**:
1. Navigate to Risks → New Risk
2. Enter:
   - Title: "UAT Security Risk"
   - Description: "Test risk for UAT"
   - Likelihood: 3 (Medium)
   - Impact: 4 (High)
3. Click "Create Risk"

**Expected Results**:
- [ ] Risk created with reference (RISK-XXXXX)
- [ ] Risk Score calculated = 12 (3 × 4)
- [ ] Status is "Open"
- [ ] Appears in risk register

**Fields to Verify**:
- Risk score calculation
- Risk matrix positioning
- Owner assignment

---

### TC-RISK-002: Link Risk to Control

**Preconditions**:
- Logged in as `uat_admin`
- Risk exists (RISK-UAT-001)
- Control exists (ISO-A.9.1)

**Steps**:
1. Navigate to Risks
2. Click on RISK-UAT-001
3. Click "Link Control"
4. Select "ISO-A.9.1 - Access Control Policy"
5. Set Relationship: "Mitigated By"
6. Click "Save Link"

**Expected Results**:
- [ ] Control link displayed on risk
- [ ] Risk appears on control page
- [ ] Dashboard shows linked controls

**Fields to Verify**:
- Control name and code
- Relationship type
- Two-way linkage

---

### TC-RISK-003: Update Risk Status

**Preconditions**:
- Logged in as `uat_admin`
- Open risk with linked control

**Steps**:
1. Navigate to Risks
2. Click on RISK-UAT-001
3. Change Status to "Mitigated"
4. Enter Notes: "Risk mitigated via control implementation"
5. Click "Save"

**Expected Results**:
- [ ] Status updated to "Mitigated"
- [ ] Notes saved
- [ ] Dashboard metrics update
- [ ] Audit trail shows change

**Fields to Verify**:
- Status badge color
- Mitigation notes
- Dashboard risk counts

---

### TC-RISK-004: Verify Dashboard Updates

**Preconditions**:
- Logged in as `uat_admin`
- Status change completed

**Steps**:
1. Navigate to Dashboard → Risk Overview
2. Review metrics

**Expected Results**:
- [ ] Open risk count reflects changes
- [ ] Mitigated risk count increased
- [ ] Risk matrix updated
- [ ] High-risk indicator accurate

**Fields to Verify**:
- Risk by status counts
- Risk by severity chart
- Trend indicators

---

## Test Suite 4: Compliance Evidence

### TC-COMP-001: View Standards

**Preconditions**:
- Logged in as `uat_admin`
- UAT seed data loaded

**Steps**:
1. Navigate to Compliance → Standards
2. Review list

**Expected Results**:
- [ ] ISO-27001-UAT visible
- [ ] SOC2-UAT visible
- [ ] Each shows control count
- [ ] Compliance score displayed

**Fields to Verify**:
- Standard codes
- Control counts
- Score percentages

---

### TC-COMP-002: Add Evidence to Control

**Preconditions**:
- Logged in as `uat_admin`
- Standard and control visible

**Steps**:
1. Navigate to Compliance → Standards
2. Click on "ISO-27001-UAT"
3. Expand control "ISO-A.5.1 - Information Security Policies"
4. Click "Add Evidence"
5. Enter:
   - Title: "Security Policy v2.0"
   - Type: Document
   - Description: "Current security policy document"
6. Click "Upload" (or Save for text evidence)

**Expected Results**:
- [ ] Evidence attached to control
- [ ] Evidence count increases
- [ ] Control shows "evidenced" status

**Fields to Verify**:
- Evidence title
- Evidence type icon
- Uploaded by user
- Upload date

---

### TC-COMP-003: Verify Compliance Score Update

**Preconditions**:
- Evidence added in TC-COMP-002

**Steps**:
1. Navigate to Compliance → Standards
2. Check ISO-27001-UAT score
3. Navigate to Dashboard → Compliance Overview

**Expected Results**:
- [ ] Standard compliance score increased
- [ ] Controls with evidence count increased
- [ ] Overall compliance score updated
- [ ] Dashboard charts reflect change

**Fields to Verify**:
- Score percentage
- "X of Y controls evidenced"
- Progress bar

---

### TC-COMP-004: Role Restriction - Readonly View Only

**Preconditions**:
- Logged in as `uat_readonly`

**Steps**:
1. Navigate to Compliance → Standards
2. Click on a standard
3. Attempt to add evidence

**Expected Results**:
- [ ] Can view standards and controls
- [ ] "Add Evidence" button disabled/hidden
- [ ] Cannot modify existing evidence

---

## Test Completion

### End of Session Checklist

1. [ ] All test cases executed
2. [ ] Results recorded in UAT Run Log
3. [ ] Defects logged (if any)
4. [ ] Screenshots captured for failures
5. [ ] Session end time recorded

### Data Cleanup (Optional)

```bash
# Reset UAT data for next tester
python scripts/uat/reset_uat.py --force
```

---

## Appendix: Common Issues

### Issue: Cannot Login
- Verify username/password from table above
- Check if using STAGING environment
- Ensure UAT seed data was loaded

### Issue: Missing Test Data
- Run UAT reset script
- Verify manifest was generated
- Check environment variables

### Issue: Permission Denied
- Verify logged in as correct role
- Some operations require admin
- Check role in user profile

---

*Document Version: 1.0.0*
*Last Updated: 2026-01-28*
