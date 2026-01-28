# UAT Run Log

## Session Information

| Field | Value |
|-------|-------|
| **Tester Name** | |
| **Date** | |
| **Start Time** | |
| **End Time** | |
| **Environment** | Staging |
| **Environment URL** | |
| **Build/Commit SHA** | |
| **UAT Seed Version** | 1.0.0 |
| **Manifest Path** | |

---

## Pre-Test Verification

| Check | Status | Notes |
|-------|--------|-------|
| Confirmed STAGING environment | ☐ Pass ☐ Fail | |
| UAT reset script executed | ☐ Pass ☐ Fail | |
| Seed manifest generated | ☐ Pass ☐ Fail | |
| Test accounts accessible | ☐ Pass ☐ Fail | |
| Browser/Device info | | |

---

## Test Suite 1: Incident Lifecycle

### TC-INC-001: Create Incident

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |
| Reference Created | |

**Checklist**:
- [ ] Success message displayed
- [ ] Reference number assigned
- [ ] Status is "Open"
- [ ] Timestamp correct
- [ ] Appears in list

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

### TC-INC-002: Update Incident Status

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] Status updated to "In Progress"
- [ ] Assigned To correct
- [ ] Timestamp updated
- [ ] Audit log entry

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

### TC-INC-003: Close Incident

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] Status is "Closed"
- [ ] Resolution populated
- [ ] Moved to closed list
- [ ] Read-only enforced

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

### TC-INC-004: Verify Incident in Admin View

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] Incident visible in filtered list
- [ ] Metadata correct
- [ ] Can view details
- [ ] Export works

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

### TC-INC-005: Role Restriction - Readonly Cannot Create

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] Button disabled/hidden
- [ ] OR Permission denied shown
- [ ] No incident created

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

## Test Suite 2: Audit Lifecycle

### TC-AUD-001: List Audit Templates

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] 3+ templates visible
- [ ] Names correct
- [ ] Categories shown

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

### TC-AUD-002: Schedule Audit from Template

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |
| Reference Created | |

**Checklist**:
- [ ] Reference number assigned
- [ ] Status is "Scheduled"
- [ ] Date correct
- [ ] Auditor assigned

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

### TC-AUD-003: Start and Complete Audit

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] Status progression correct
- [ ] Findings saved
- [ ] Completion date set
- [ ] Read-only after complete

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

### TC-AUD-004: View Audit in Report View

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] Audit visible in report
- [ ] Findings shown
- [ ] PDF export works

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

## Test Suite 3: Risk Workflow

### TC-RISK-001: Create Risk

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |
| Reference Created | |

**Checklist**:
- [ ] Reference assigned
- [ ] Score calculated correctly
- [ ] Status is "Open"
- [ ] Appears in register

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

### TC-RISK-002: Link Risk to Control

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] Link displayed on risk
- [ ] Risk shows on control
- [ ] Dashboard updated

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

### TC-RISK-003: Update Risk Status

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] Status updated
- [ ] Notes saved
- [ ] Dashboard metrics update
- [ ] Audit trail entry

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

### TC-RISK-004: Verify Dashboard Updates

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] Risk counts correct
- [ ] Mitigated count increased
- [ ] Matrix updated
- [ ] Trend indicators

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

## Test Suite 4: Compliance Evidence

### TC-COMP-001: View Standards

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] ISO-27001-UAT visible
- [ ] SOC2-UAT visible
- [ ] Control counts shown
- [ ] Scores displayed

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

### TC-COMP-002: Add Evidence to Control

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] Evidence attached
- [ ] Count increased
- [ ] Control shows evidenced

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

### TC-COMP-003: Verify Compliance Score Update

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] Score increased
- [ ] Evidence count updated
- [ ] Dashboard reflects change

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

### TC-COMP-004: Role Restriction - Readonly View Only

| Field | Value |
|-------|-------|
| Executed By | |
| Execution Time | |
| Status | ☐ Pass ☐ Fail ☐ Blocked ☐ Skipped |

**Checklist**:
- [ ] Can view standards
- [ ] Cannot add evidence
- [ ] Cannot modify

**Notes/Issues**:
```
[Enter any observations or issues]
```

**Defect ID** (if applicable): 

---

## Summary

### Results Overview

| Suite | Total | Pass | Fail | Blocked | Skipped |
|-------|-------|------|------|---------|---------|
| Incident Lifecycle | 5 | | | | |
| Audit Lifecycle | 4 | | | | |
| Risk Workflow | 4 | | | | |
| Compliance Evidence | 4 | | | | |
| **TOTAL** | **17** | | | | |

### Pass Rate

**Overall Pass Rate**: ____%

### Defects Summary

| Defect ID | Test Case | Severity | Summary |
|-----------|-----------|----------|---------|
| | | | |
| | | | |
| | | | |

### Blocking Issues

```
[List any issues that blocked testing]
```

### Observations / Recommendations

```
[Additional observations, usability feedback, or recommendations]
```

---

## Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Tester | | | |
| UAT Lead | | | |
| Product Owner | | | |

---

*Template Version: 1.0.0*
*Generated: 2026-01-28*
