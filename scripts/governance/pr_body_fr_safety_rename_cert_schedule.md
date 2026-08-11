# Change Ledger (CL-FR-SAFETY-RENAME-CERT-SCHEDULE)

> Base: `origin/main` @ `c977c5e8` (#1726 LIVE).
> Product: rename Safety hub; Certificates become a Compliance Schedule view (not a sibling nav item).

## 1) Summary

- **Feature / Change name:** FR-SAFETY-RENAME-CERT-SCHEDULE — Safety & Investigations + Certificates-in-Schedule
- **User goal:** Sidebar says Safety & Investigations. Certificate renewals are reached inside Compliance Schedule, not as a peer menu item.
- **Problem:** “Safety & Cases” undersold investigations; Certificate shelf as a Compliance sibling still felt like a separate product.
- **In scope:**
  - i18n rename `nav.safety_cases` → Safety & Investigations (en/cy)
  - Compliance Schedule Obligations | Certificates view switcher (`?view=certificates`)
  - Extract `AssuranceCertShelfPanel`; remove Certificate shelf from Compliance/Assurance hubs
  - Redirect `/assurance/certificates` → `/compliance-schedule?view=certificates`
  - Monitoring handoff link updated
- **Out of scope:** Certificate expiry → obligation auto-create; domain filter chips (FR-CS-DOMAIN-03); Assist; Document Preview (#1727)
- **Feature flag:** None (schedule access unchanged)

## 2) Impact Map

- **Frontend:** Layout, ComplianceSchedule, AssuranceCertShelfPanel, App redirect, ComplianceAutomation link, i18n, tests
- **Backend / DB:** None

## 3) Compatibility & Data Safety

- **Compatibility:** Deep link `/assurance/certificates` redirects. Schedule URL gains optional `view`.
- **Breaking:** Certificate shelf removed from nav (intentional).
- **Rollback:** Revert merge; redeploy.

## Compliance Delta

| Control | Before | After |
| --- | --- | --- |
| Safety hub label | Safety & Cases | Safety & Investigations |
| Certificate shelf home | Compliance sibling nav | Schedule Certificates view |
| Certificate deep link | Standalone page | Redirect into Schedule |

## 4) Acceptance Criteria

- [x] **AC-01:** Hub label Safety & Investigations (en + cy)
- [x] **AC-02:** Schedule view switcher Obligations | Certificates; `?view=certificates` loads shelf panel
- [x] **AC-03:** No Certificate shelf link under Compliance or Assurance hubs
- [x] **AC-04:** `/assurance/certificates` redirects to schedule certificates view
- [x] **AC-05:** Layout + shelf panel + schedule view tests green
- [x] **AC-06:** No test skipped/loosened

## 5) Testing Evidence

- [x] Layout + AssuranceCertShelfPanel + ComplianceSchedule.certificatesView — **30 passed**
- [ ] Full CI / tip LIVE — after merge

## 6) Critical Journeys

- [x] **CUJ-01:** Expand Safety → label Investigations; cases still listed
- [x] **CUJ-02:** Compliance Schedule → Certificates view → shelf summary
- [x] **CUJ-03:** Old `/assurance/certificates` bookmark lands on schedule certificates view

## 7) Observability & Ops

- No new metrics.

## 8) Release Plan

1. Merge after #1727 LIVE (STACK_MAX) and CI green — admin-merge authorised.
2. Main CI → STG → PROD with `release_sha` = tip.
3. Spot-check hub rename + Schedule Certificates view.

## 9) Rollback Plan

- **Trigger:** Missing certificates inventory; wrong hub label; broken redirect.
- **Steps:** Revert merge; redeploy prior tip.
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack

- Vitest 30 passed
- Change Ledger: this body

---

# Gate Checklist

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Additive FE (redirect preserves deep links)
- [x] **Gate 2:** Touched tests green
- [x] **Gate 3:** Rollback = revert deploy
- [ ] **Gate 4:** CI green on PR
- [ ] **Gate 5:** Tip LIVE verified
