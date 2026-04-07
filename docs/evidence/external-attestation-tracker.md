# External Attestation Tracker

**Platform:** Quality Governance Platform (QGP)
**Owner:** Platform Engineering / GRC Lead
**Last Updated:** 2026-04-07
**Review Cycle:** Quarterly

This document tracks all external attestations required to achieve CM=1.00 (direct + comprehensive evidence) across WCS dimensions that currently have CM=0.90 due to missing third-party validation.

---

## Summary Status

| ID | Dimension | Type | Status | Owner | Target Date | CM Now | CM On Completion |
|----|-----------|------|--------|-------|-------------|--------|-----------------|
| EA-01 | D03 Accessibility | WCAG 2.1 AA external audit | 🔴 Not started | UX Lead | Q3 2026 | 0.90 | 1.00 |
| EA-02 | D06 Security | External penetration test | 🟡 Scheduled | CISO | Q2 2026 | 0.90 | 1.00 |
| EA-03 | D07 Privacy | DPO sign-off on DPIAs | 🟡 In progress | DPO / Legal | Q2 2026 | 0.90 | 1.00 |
| EA-04 | D08 Compliance | ISO auditor validation of evidence tool | 🔴 Not started | Quality Lead | Q4 2026 | 0.90 | 1.00 |
| EA-05 | D23 Ops | Live on-call schedule + PagerDuty/OpsGenie config | 🟡 In progress | SRE Lead | Q2 2026 | 0.90 | 1.00 |

---

## EA-01: WCAG 2.1 AA External Accessibility Audit (D03)

**Blocking score uplift:** D03 WCS 8.6 → 9.5

**What's needed:**
- Independent third-party WCAG 2.1 AA assessment (manual testing + automated scan)
- VPAT (Voluntary Product Accessibility Template) signed by assessor
- Remediation plan for any issues rated Critical or High
- Re-test evidence after remediation

**Evidence already in place:**
- `docs/accessibility/vpat.md` (internal VPAT — needs external sign-off)
- `docs/accessibility/a11y-coverage-matrix.md` (internal coverage)
- `docs/accessibility/wcag-checklist.md`
- `lighthouserc.json` a11y ≥ 0.95 gate in CI
- Axe-core tests in `frontend/src/pages/__tests__/`

**Deliverable required:**
```
docs/evidence/a11y-external-audit-YYYY-Q?.md
  - Assessor name and accreditation
  - Assessment date and scope
  - Tool + manual testing methodology
  - Issues found: count by severity (Critical/High/Medium/Low)
  - Remediation status (each Critical/High must be closed)
  - Assessor sign-off statement
  - Next review date
```

**Suggested vendor path:** Deque Systems (axe-core authors), SSB BART Group, or equivalent.

---

## EA-02: External Penetration Test (D06)

**Blocking score uplift:** D06 WCS 8.6 → 9.5

**What's needed:**
- External pen-test by CREST-accredited or equivalent tester
- Scope: API, authentication, authorisation, injection, OWASP Top-10
- All Critical and High findings must be remediated before release
- Re-test verification for every remediated finding

**Evidence already in place:**
- `docs/security/pentest-plan.md` (scope + methodology defined)
- `docs/evidence/pentest-schedule.md` (schedule confirmed)
- `docs/security/threat-model.md`
- `docs/evidence/SECURITY_DEFENSE_IN_DEPTH.md`
- DAST (ZAP baseline) now blocking in CI (PR this session)

**Deliverable required:**
```
docs/evidence/pentest-report-YYYY-Q?.md
  - Tester name and CREST/PTES accreditation number
  - Test date(s) and scope
  - Methodology (OWASP Testing Guide, PTES, CREST)
  - Findings by severity: Critical / High / Medium / Low / Informational
  - Each Critical/High: description, CVSS score, remediation, re-test result
  - Executive summary / overall risk rating
  - Tester sign-off
```

---

## EA-03: DPO Sign-off on DPIAs (D07)

**Blocking score uplift:** D07 WCS 8.6 → 9.5

**What's needed:**
- Data Protection Officer formal review of all Data Protection Impact Assessments
- Sign-off that DPIAs are complete and residual risks are accepted
- Evidence that privacy-by-design is operationally applied (not just documented)

**Evidence already in place:**
- `docs/privacy/dpia-incidents.md` (DPIA for incidents module)
- `docs/privacy/dpia-template.md`
- `docs/privacy/data-retention-policy.md`
- `docs/privacy/data-classification.md`
- `docs/compliance/gdpr-compliance.md`
- `docs/evidence/retention-automation-evidence.md`

**Deliverable required:**
```
docs/evidence/dpo-signoff-YYYY-Q?.md
  - DPO name and role
  - Sign-off date
  - DPIAs reviewed (list each with version reviewed)
  - Residual risks accepted (each with DPO approval note)
  - Next review schedule
  - DPO signature / authorised confirmation
```

---

## EA-04: ISO Auditor Validation of Compliance Evidence Tool (D08)

**Blocking score uplift:** D08 WCS 9.0 → 9.5

**What's needed:**
- An ISO 27001 lead auditor (or equivalent) to validate that:
  - The 233-clause ISO compliance tool accurately maps to the published standard
  - The Genspark AI evidence analysis produces reliable clause-to-evidence mappings
  - The Statement of Applicability generation is audit-grade
  - The evidence linking workflow satisfies auditor expectations for Annex A control coverage

**Evidence already in place:**
- `src/domain/services/iso_compliance_service.py` (233 clauses, 5-stage AI pipeline)
- `src/domain/services/ai_models.py` (Genspark integration)
- `tests/integration/test_compliance_advanced.py` (automated test suite)
- `docs/compliance/compliance-matrix-iso.md`
- `openapi-baseline.json` + `docs/contracts/openapi.json`

**Deliverable required:**
```
docs/evidence/iso-auditor-validation-YYYY-Q?.md
  - Auditor name and ISO 27001 lead auditor certification number
  - Validation date and scope
  - Clauses reviewed (sample or full)
  - Assessment of AI clause mapping accuracy (% accurate, methods reviewed)
  - SoA generation review findings
  - Auditor recommendation: Fit for purpose / Needs improvement / Not fit
  - Sign-off statement
```

---

## EA-05: Live On-call Schedule + Alerting Tool Configuration (D23)

**Blocking score uplift:** D23 WCS 8.6 → 9.5

**What's needed:**
- Live PagerDuty or OpsGenie integration configured and verified
- Named on-call rotation schedule documented and active
- Escalation policy tested (alert → on-call → escalation path)
- Integration with Azure Monitor alerting (alerts flow to PD/OpsGenie)

**Evidence already in place:**
- `docs/ops/ON_CALL_TEMPLATE.md` (template exists)
- `docs/runbooks/OBSERVABILITY_AND_ALERTING.md`
- `docs/observability/alerting-rules.md`
- `docs/evidence/otel-alert-proof-2026-04-07.md` (OTel alert round-trip proven)

**Deliverable required:**
```
docs/evidence/on-call-config-proof.md
  - Tool: PagerDuty / OpsGenie / [other]
  - Integration: Azure Monitor → tool (webhook/API key configured)
  - On-call rotation: named schedule with at least 2 rotators
  - Escalation policy: defined and tested
  - Test alert evidence: screenshot/log of test alert triggered + resolved
  - Last tested: date
```

---

## Tracking Instructions

1. Update **Status** column monthly.
2. When an attestation is completed, move the deliverable to the target path and update this tracker.
3. Tag the completion in the next sprint's release notes.
4. Re-run the WCS scorecard after each attestation completion — expect D-score uplift of +0.9 per item.
