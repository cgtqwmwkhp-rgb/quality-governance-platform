# External Attestation Tracker

**Platform:** Quality Governance Platform (QGP)
**Owner:** Platform Engineering / GRC Lead
**Last Updated:** 2026-07-13
**Review Cycle:** Quarterly

This document tracks all external attestations required to achieve CM=1.00 (direct + comprehensive evidence) across WCS dimensions that currently have CM=0.90 due to missing third-party validation. Historical mentions of PagerDuty as a required unlock are superseded by **EA-05 Cancelled**.

---

## Summary Status

| ID | Dimension | Type | Status | Owner | Target Date | CM Now | CM On Completion |
|----|-----------|------|--------|-------|-------------|--------|-----------------|
| EA-01 | D03 Accessibility | WCAG 2.1 AA external audit | 🔴 Not started | UX Lead | Q3 2026 | 0.90 | 1.00 |
| EA-02 | D06 Security | External penetration test | 🟡 Scheduled | CISO | Q2 2026 | 0.90 | 1.00 |
| EA-03 | D07 Privacy | DPO sign-off on DPIAs | ✅ Closed 2026-07-12 | DPO / Legal | Q3 2026 | 1.00 | 1.00 |
| EA-04 | D08 Compliance | ISO auditor validation of evidence tool | 🔴 Not started | Quality Lead | Q4 2026 | 0.90 | 1.00 |
| EA-05 | D23 Ops | Live on-call schedule + PagerDuty/OpsGenie config | Cancelled — N/A | SRE Lead | — | — | Azure Monitor email |

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

**Status:** ✅ **Closed 2026-07-12**

**Blocking score uplift:** D07 WCS 8.6 → 9.5 (partial — EA-01/02/04 still open)

**Deliverable (complete):**
- `docs/evidence/dpo-signoff-2026-Q3-READY-FOR-SIGNATURE.md` — **SIGNED**
- Platform DPIA §9 completed; runtime `dpia.status=signed`

**Evidence already in place:**
- `docs/privacy/dpia-incidents.md` (DPIA for incidents module)
- `docs/compliance/dpia-ocr-ai-import.md` (OCR/AI external audit import DPIA — Path-to-10 S15)
- `docs/governance/privacy-ocr-ai-dpia.md` (governance link)
- `docs/privacy/dpia-checklist.md` (trigger + OCR completeness checklist)
- `docs/compliance/dpia-quality-governance-platform.md` (platform DPIA — §9 signed)
- `GET /api/v1/privacy/contact` → `dpia.status=signed`
- `docs/privacy/data-classification.md`
- `docs/compliance/gdpr-compliance.md`
- `docs/evidence/retention-automation-evidence.md`
- `docs/evidence/dpo-signoff-2026-Q3-READY-FOR-SIGNATURE.md`

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

**Status:** Cancelled / N/A (2026-07-13)

PagerDuty / OpsGenie app-level Events API integration is **out of product scope**.
Accepted D23 ops alerting path is **Azure Monitor → email action groups** (already documented
and active). Historical scorecards and runbooks that mention PagerDuty as a required unlock are
**superseded** by this cancellation.

**Accepted evidence path:**
- `docs/runbooks/alerting-integration.md` — Azure Monitor alert rules + email action groups
- `docs/ops/ON_CALL_TEMPLATE.md` — on-call template (email / Azure Monitor)
- `docs/runbooks/HUMAN_UNLOCK_SMTP.md` — SMTP only (PagerDuty removed from wire script)

---

## Tracking Instructions

1. Update **Status** column monthly.
2. When an attestation is completed, move the deliverable to the target path and update this tracker.
3. Tag the completion in the next sprint's release notes.
4. Re-run the WCS scorecard after each attestation completion — expect D-score uplift of +0.9 per item.
